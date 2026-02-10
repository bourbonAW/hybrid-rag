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

        使用 python-docx 提取文档内容并转换为简单的 Markdown
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

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue

            # 根据样式判断标题级别
            style_name = paragraph.style.name.lower()
            if 'heading 1' in style_name:
                markdown_lines.append(f"# {text}\n")
            elif 'heading 2' in style_name:
                markdown_lines.append(f"## {text}\n")
            elif 'heading 3' in style_name:
                markdown_lines.append(f"### {text}\n")
            elif 'heading 4' in style_name:
                markdown_lines.append(f"#### {text}\n")
            elif 'heading 5' in style_name:
                markdown_lines.append(f"##### {text}\n")
            elif 'heading 6' in style_name:
                markdown_lines.append(f"###### {text}\n")
            else:
                markdown_lines.append(f"{text}\n")

        # 处理表格
        for table in doc.tables:
            markdown_lines.append("\n")
            for i, row in enumerate(table.rows):
                cells = [cell.text.strip() for cell in row.cells]
                markdown_lines.append("| " + " | ".join(cells) + " |\n")
                # 添加表格分隔线
                if i == 0:
                    markdown_lines.append("| " + " | ".join(["---"] * len(cells)) + " |\n")
            markdown_lines.append("\n")

        return "".join(markdown_lines)
