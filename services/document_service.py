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
