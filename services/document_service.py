import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from models.schemas import DocumentStatus
from models.document_store import DocumentStore
from services.pageindex_wrapper import PageIndexWrapper
from config import settings


class DocumentService:
    def __init__(self, store: DocumentStore):
        self.store = store
        self.pageindex = PageIndexWrapper()

    async def process_document(
        self,
        doc_id: str,
        file_path: str,
        file_format: str
    ) -> bool:
        """Process document and build tree index."""
        try:
            await self.store.update_status(doc_id, DocumentStatus.PROCESSING)

            storage_dir = settings.storage_path / doc_id
            storage_dir.mkdir(parents=True, exist_ok=True)

            # Copy original file
            original_path = storage_dir / f"original.{file_format}"
            shutil.copy(file_path, original_path)

            # 根据格式路由到 PageIndex 不同函数
            if file_format == "pdf":
                tree = await self.pageindex.build_tree_from_pdf(
                    str(original_path),
                    storage_dir
                )
            elif file_format == "docx":
                # 将 DOCX 转换为 Markdown
                md_content = self._convert_docx_to_markdown(original_path)
                temp_md = storage_dir / "temp.md"
                with open(temp_md, "w", encoding="utf-8") as f:
                    f.write(md_content)
                tree = await self.pageindex.build_tree_from_markdown(
                    str(temp_md),
                    storage_dir
                )
                temp_md.unlink()  # 删除临时文件
            elif file_format in ["md", "txt"]:
                # 对于 txt 文件，先转换为临时 markdown 文件
                # 因为 md_to_tree 需要 .md 扩展名
                if file_format == "txt":
                    temp_md = storage_dir / "temp.md"
                    shutil.copy(original_path, temp_md)
                    tree = await self.pageindex.build_tree_from_markdown(
                        str(temp_md),
                        storage_dir
                    )
                    temp_md.unlink()  # 删除临时文件
                else:
                    tree = await self.pageindex.build_tree_from_markdown(
                        str(original_path),
                        storage_dir
                    )
            else:
                raise ValueError(f"Unsupported format: {file_format}")

            # Save tree to JSON
            tree_path = storage_dir / "tree.json"
            with open(tree_path, "w", encoding="utf-8") as f:
                json.dump(tree, f, indent=2, ensure_ascii=False)

            await self.store.update_status(doc_id, DocumentStatus.COMPLETED)
            return True

        except Exception as e:
            await self.store.update_status(doc_id, DocumentStatus.FAILED, str(e))
            return False

    def get_tree(self, doc_id: str) -> Optional[dict]:
        """Load tree structure from storage."""
        tree_path = settings.storage_path / doc_id / "tree.json"
        if tree_path.exists():
            with open(tree_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _convert_docx_to_markdown(self, docx_path: Path) -> str:
        """
        将 DOCX 文件转换为 Markdown 格式

        使用 python-docx 提取文档内容并转换为简单的 Markdown。
        对于大表格，会尝试按内容分组以提高可搜索性。
        """
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "python-docx is required for DOCX support. "
                "Install it with: pip install python-docx"
            )

        doc = Document(docx_path)
        markdown_lines = []

        # 提取文档标题（如果有）
        has_title = False
        for paragraph in doc.paragraphs[:5]:  # 检查前5个段落
            text = paragraph.text.strip()
            if text and not has_title:
                # 将第一个非空段落作为文档标题
                markdown_lines.append(f"# {text}\n\n")
                has_title = True
                break

        # 处理段落
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue

            # 根据样式判断标题级别
            style_name = paragraph.style.name.lower()
            if 'heading 1' in style_name:
                markdown_lines.append(f"# {text}\n\n")
            elif 'heading 2' in style_name:
                markdown_lines.append(f"## {text}\n\n")
            elif 'heading 3' in style_name:
                markdown_lines.append(f"### {text}\n\n")
            elif 'heading 4' in style_name:
                markdown_lines.append(f"#### {text}\n\n")
            elif 'heading 5' in style_name:
                markdown_lines.append(f"##### {text}\n\n")
            elif 'heading 6' in style_name:
                markdown_lines.append(f"###### {text}\n\n")
            else:
                # 跳过已经作为标题的段落
                if has_title and text == markdown_lines[0].strip("# \n"):
                    continue
                markdown_lines.append(f"{text}\n\n")

        # 处理表格
        for table_idx, table in enumerate(doc.tables):
            # 为每个表格添加一个标题（如果文档中没有明确的表格标题）
            if len(doc.tables) > 1:
                markdown_lines.append(f"## 表格 {table_idx + 1}\n\n")

            # 尝试智能分组大表格（如果表格有"区域"或类似的分组列）
            if len(table.rows) > 10:
                grouped_content = self._try_group_table(table)
                if grouped_content:
                    markdown_lines.extend(grouped_content)
                    continue

            # 标准表格转换
            for i, row in enumerate(table.rows):
                cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
                markdown_lines.append("| " + " | ".join(cells) + " |\n")
                # 添加表格分隔线
                if i == 0:
                    markdown_lines.append("| " + " | ".join(["---"] * len(cells)) + " |\n")
            markdown_lines.append("\n")

        return "".join(markdown_lines)

    def _try_group_table(self, table) -> list:
        """
        尝试按某一列的值对表格进行分组（例如按区域分组）
        返回分组后的 Markdown 行列表，如果无法分组则返回 None
        """
        if not table.rows or len(table.rows) < 2:
            return None

        # 获取表头
        header_row = table.rows[0]
        headers = [cell.text.strip() for cell in header_row.cells]

        # 查找可能的分组列（包含"区"、"地区"、"区域"等关键词）
        group_col_idx = None
        for i, header in enumerate(headers):
            if any(keyword in header for keyword in ["区", "地区", "区域", "类别", "分类"]):
                group_col_idx = i
                break

        if group_col_idx is None:
            return None

        # 按分组列的值分组
        groups = {}
        for row in table.rows[1:]:  # 跳过表头
            cells = [cell.text.strip() for cell in row.cells]
            if len(cells) <= group_col_idx:
                continue

            group_key = cells[group_col_idx]
            if not group_key:
                group_key = "其他"

            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(cells)

        # 如果分组太少（<3个）或太多（>20个），不分组
        if len(groups) < 3 or len(groups) > 20:
            return None

        # 生成分组后的 Markdown
        markdown_lines = []
        for group_name, rows in sorted(groups.items()):
            markdown_lines.append(f"### {group_name}\n\n")

            # 表头
            markdown_lines.append("| " + " | ".join(headers) + " |\n")
            markdown_lines.append("| " + " | ".join(["---"] * len(headers)) + " |\n")

            # 数据行
            for cells in rows:
                escaped_cells = [cell.replace("|", "\\|") for cell in cells]
                markdown_lines.append("| " + " | ".join(escaped_cells) + " |\n")

            markdown_lines.append("\n")

        return markdown_lines
