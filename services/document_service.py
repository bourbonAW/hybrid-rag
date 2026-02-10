import json
import shutil
from pathlib import Path
from typing import Optional
from models.schemas import DocumentStatus, TreeNode
from models.document_store import DocumentStore
from utils.pdf_to_images import extract_pdf_pages
from services.vlm_client import VLMClient
from services.llm_client import LLMClient
from config import settings


class DocumentService:
    def __init__(self, store: DocumentStore, api_key: str):
        self.store = store
        self.vlm = VLMClient(api_key, settings.openai_model, settings.openai_base_url)
        self.llm = LLMClient(api_key, settings.openai_model, settings.openai_base_url)

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

            if file_format == "pdf":
                tree = await self._process_pdf(doc_id, file_path, storage_dir)
            elif file_format in ["md", "txt"]:
                tree = await self._process_text(doc_id, file_path, storage_dir)
            else:
                raise ValueError(f"Unsupported format: {file_format}")

            # Save tree to JSON
            tree_path = storage_dir / "tree.json"
            with open(tree_path, "w") as f:
                json.dump(tree, f, indent=2)

            await self.store.update_status(doc_id, DocumentStatus.COMPLETED)
            return True

        except Exception as e:
            await self.store.update_status(doc_id, DocumentStatus.FAILED, str(e))
            return False

    async def _process_pdf(
        self,
        doc_id: str,
        file_path: str,
        storage_dir: Path
    ) -> dict:
        """Process PDF using Vision-based approach."""
        pages_dir = storage_dir / "pages"
        page_images = await extract_pdf_pages(file_path, str(pages_dir))

        tree_result = await self.vlm.build_tree_from_images(
            list(page_images.values()),
            len(page_images)
        )

        return tree_result

    async def _process_text(
        self,
        doc_id: str,
        file_path: str,
        storage_dir: Path
    ) -> dict:
        """Process text document using Text-based approach."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree_result = await self.llm.build_tree_from_markdown(content)

        # Save content for retrieval
        content_path = storage_dir / "content.txt"
        with open(content_path, "w") as f:
            f.write(content)

        return tree_result

    def get_tree(self, doc_id: str) -> Optional[dict]:
        """Load tree structure from storage."""
        tree_path = settings.storage_path / doc_id / "tree.json"
        if tree_path.exists():
            with open(tree_path, "r") as f:
                return json.load(f)
        return None
