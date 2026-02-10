# PageIndex API Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Format-Adaptive PageIndex RAG API service supporting PDF (Vision-based) and Markdown/Text (Text-based) with FastAPI.

**Architecture:** FastAPI async service with format-specific parsers (Vision for PDF, Text for Markdown/DOCX), unified tree index structure, LLM-based reasoning retrieval, and local JSON storage.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic, OpenAI API, PyMuPDF (PDF→images), python-docx, pytest

---

## Task 1: Project Setup and Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.py`

**Step 1: Create requirements.txt**

```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.6.0
pydantic-settings==2.1.0
python-multipart==0.0.6
openai==1.12.0
pymupdf==1.23.0
python-docx==1.1.0
aiofiles==23.2.0
pytest==8.0.0
pytest-asyncio==0.23.0
httpx==0.26.0
```

**Step 2: Create .env.example**

```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
STORAGE_PATH=./storage
MAX_FILE_SIZE=104857600
```

**Step 3: Create config.py**

```python
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    storage_path: Path = Path("./storage")
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    
    class Config:
        env_file = ".env"


settings = Settings()
```

**Step 4: Verify setup**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully

**Step 5: Commit**

```bash
git add requirements.txt .env.example config.py
git commit -m "chore: add project dependencies and config"
```

---

## Task 2: Pydantic Data Models

**Files:**
- Create: `models/schemas.py`
- Test: `tests/test_schemas.py`

**Step 1: Write the test**

```python
from models.schemas import Document, DocumentStatus, TreeNode, SearchResult
from datetime import datetime


def test_document_creation():
    doc = Document(
        id="test-123",
        filename="test.pdf",
        format="pdf",
        status=DocumentStatus.PENDING
    )
    assert doc.id == "test-123"
    assert doc.format == "pdf"
    assert doc.status == DocumentStatus.PENDING


def test_tree_node_creation():
    node = TreeNode(
        id="0001",
        level=1,
        title="Introduction",
        content="This is the intro",
        page_start=1,
        page_end=2
    )
    assert node.id == "0001"
    assert node.children == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py -v`
Expected: FAIL - "models/schemas.py not found"

**Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Literal
from enum import Enum


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(BaseModel):
    id: str = Field(..., description="Document UUID")
    filename: str
    format: Literal["pdf", "md", "docx", "txt"]
    status: DocumentStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class TreeNode(BaseModel):
    id: str = Field(..., description="Node ID like '0001', '0001.001'")
    level: int = Field(..., ge=0)
    title: str
    content: str
    page_start: int
    page_end: int
    children: List["TreeNode"] = []
    summary: Optional[str] = None


TreeNode.model_rebuild()


class SearchResult(BaseModel):
    node_id: str
    title: str
    content: str
    relevance_score: float
    page_refs: List[int]
    reasoning_path: List[str]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3
    include_context: bool = True


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_nodes: int
    processing_time_ms: float
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add models/schemas.py tests/test_schemas.py
git commit -m "feat: add pydantic data models"
```

---

## Task 3: In-Memory Document Store

**Files:**
- Create: `models/document_store.py`
- Test: `tests/test_document_store.py`

**Step 1: Write the test**

```python
import pytest
from models.document_store import DocumentStore
from models.schemas import Document, DocumentStatus


@pytest.fixture
def store():
    return DocumentStore()


@pytest.mark.asyncio
async def test_create_document(store):
    doc = await store.create(filename="test.pdf", format="pdf")
    assert doc.filename == "test.pdf"
    assert doc.format == "pdf"
    assert doc.status == DocumentStatus.PENDING


@pytest.mark.asyncio
async def test_get_document(store):
    doc = await store.create(filename="test.pdf", format="pdf")
    retrieved = await store.get(doc.id)
    assert retrieved.id == doc.id


@pytest.mark.asyncio
async def test_update_status(store):
    doc = await store.create(filename="test.pdf", format="pdf")
    updated = await store.update_status(doc.id, DocumentStatus.COMPLETED)
    assert updated.status == DocumentStatus.COMPLETED
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_document_store.py -v`
Expected: FAIL - "models/document_store.py not found"

**Step 3: Write minimal implementation**

```python
import uuid
from typing import Dict, Optional
from models.schemas import Document, DocumentStatus


class DocumentStore:
    def __init__(self):
        self._documents: Dict[str, Document] = {}
    
    async def create(self, filename: str, format: str) -> Document:
        doc = Document(
            id=str(uuid.uuid4()),
            filename=filename,
            format=format,
            status=DocumentStatus.PENDING
        )
        self._documents[doc.id] = doc
        return doc
    
    async def get(self, doc_id: str) -> Optional[Document]:
        return self._documents.get(doc_id)
    
    async def update_status(
        self,
        doc_id: str,
        status: DocumentStatus,
        error_message: Optional[str] = None
    ) -> Optional[Document]:
        doc = self._documents.get(doc_id)
        if doc:
            doc.status = status
            if error_message:
                doc.error_message = error_message
            if status == DocumentStatus.COMPLETED:
                from datetime import datetime
                doc.completed_at = datetime.utcnow()
        return doc
    
    async def delete(self, doc_id: str) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_document_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add models/document_store.py tests/test_document_store.py
git commit -m "feat: add in-memory document store"
```

---

## Task 4: PDF to Images Conversion

**Files:**
- Create: `utils/pdf_to_images.py`
- Test: `tests/test_pdf_to_images.py`

**Step 1: Write the test**

```python
import pytest
from pathlib import Path
from utils.pdf_to_images import extract_pdf_pages


@pytest.mark.asyncio
async def test_extract_pdf_pages(tmp_path):
    # Create a simple test PDF using pymupdf
    import fitz
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "Test content")
    doc.save(str(pdf_path))
    doc.close()
    
    output_dir = tmp_path / "pages"
    page_images = await extract_pdf_pages(str(pdf_path), str(output_dir))
    
    assert len(page_images) == 1
    assert Path(page_images[1]).exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pdf_to_images.py -v`
Expected: FAIL - "utils/pdf_to_images.py not found"

**Step 3: Write minimal implementation**

```python
import fitz
from pathlib import Path
from typing import Dict


async def extract_pdf_pages(pdf_path: str, output_dir: str, dpi: int = 200) -> Dict[int, str]:
    """Extract PDF pages as images.
    
    Returns:
        Dict mapping page_number (1-indexed) to image path
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    page_images = {}
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Use matrix for higher resolution
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        
        image_path = output_path / f"page_{page_num + 1:04d}.jpg"
        pix.save(str(image_path))
        page_images[page_num + 1] = str(image_path)
    
    doc.close()
    return page_images
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pdf_to_images.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add utils/pdf_to_images.py tests/test_pdf_to_images.py
git commit -m "feat: add pdf to images conversion"
```

---

## Task 5: OpenAI VLM Client

**Files:**
- Create: `services/vlm_client.py`
- Test: `tests/test_vlm_client.py`

**Step 1: Write the test**

```python
import pytest
from unittest.mock import AsyncMock, patch
from services.vlm_client import VLMClient


@pytest.mark.asyncio
async def test_build_tree_from_images():
    with patch('openai.AsyncOpenAI') as mock_client:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"nodes": []}'))]
        mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
        
        client = VLMClient(api_key="test-key")
        result = await client.build_tree_from_images(["page1.jpg"], total_pages=1)
        
        assert "nodes" in result


@pytest.mark.asyncio
async def test_search_tree():
    with patch('openai.AsyncOpenAI') as mock_client:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"node_list": ["0001"]}'))]
        mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
        
        client = VLMClient(api_key="test-key")
        tree = {"nodes": [{"id": "0001", "title": "Test"}]}
        result = await client.search_tree(tree, "test query")
        
        assert "node_list" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_vlm_client.py -v`
Expected: FAIL - "services/vlm_client.py not found"

**Step 3: Write minimal implementation**

```python
import json
import base64
from typing import List, Dict, Any
from openai import AsyncOpenAI


class VLMClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def build_tree_from_images(
        self,
        image_paths: List[str],
        total_pages: int
    ) -> Dict[str, Any]:
        """Build PageIndex tree from page images."""
        
        # Build message with images
        content = [
            {"type": "text", "text": f"""Analyze this {total_pages}-page document and create a hierarchical tree structure.
            
Return a JSON object with this structure:
{{
  "nodes": [
    {{
      "id": "0001",
      "level": 0,
      "title": "Document Title",
      "content": "Brief summary",
      "page_start": 1,
      "page_end": 5,
      "children": []
    }}
  ]
}}

Requirements:
- id format: 4-digit string, use nesting for children (e.g., "0001.0001")
- level: 0 for root, increases for nesting
- page_start/page_end: 1-indexed page numbers
- Include all significant sections"""}
        ]
        
        # Add up to 10 sample images (to save tokens)
        for img_path in image_paths[:10]:
            with open(img_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=4000
        )
        
        result_text = response.choices[0].message.content
        # Extract JSON from markdown code blocks if present
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        return json.loads(result_text.strip())
    
    async def search_tree(
        self,
        tree: Dict[str, Any],
        query: str
    ) -> Dict[str, Any]:
        """Search tree for relevant nodes."""
        
        prompt = f"""Given this document tree structure and a question, find the most relevant nodes.

Document Tree:
{json.dumps(tree, indent=2)}

Question: {query}

Return JSON:
{{
  "thinking": "Your reasoning about which nodes are relevant",
  "node_list": ["0001", "0002.0001"]
}}

Return ONLY the JSON, no other text."""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        return json.loads(result_text.strip())
    
    async def answer_with_images(
        self,
        query: str,
        image_paths: List[str]
    ) -> str:
        """Generate answer from query and page images."""
        
        content = [{"type": "text", "text": f"Answer this question based on the provided document pages:\n\n{query}"}]
        
        for img_path in image_paths:
            with open(img_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_vlm_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/vlm_client.py tests/test_vlm_client.py
git commit -m "feat: add OpenAI VLM client"
```

---

## Task 6: LLM Client for Text Documents

**Files:**
- Create: `services/llm_client.py`
- Test: `tests/test_llm_client.py`

**Step 1: Write the test**

```python
import pytest
from unittest.mock import AsyncMock, patch
from services.llm_client import LLMClient


@pytest.mark.asyncio
async def test_build_tree_from_markdown():
    with patch('openai.AsyncOpenAI') as mock_client:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"nodes": []}'))]
        mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
        
        client = LLMClient(api_key="test-key")
        md_content = "# Title\n\n## Section 1\nContent"
        result = await client.build_tree_from_markdown(md_content)
        
        assert "nodes" in result


@pytest.mark.asyncio
async def test_search_tree_text():
    with patch('openai.AsyncOpenAI') as mock_client:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"node_list": ["0001"]}'))]
        mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
        
        client = LLMClient(api_key="test-key")
        tree = {"nodes": [{"id": "0001", "title": "Test"}]}
        result = await client.search_tree(tree, "test query")
        
        assert "node_list" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_client.py -v`
Expected: FAIL - "services/llm_client.py not found"

**Step 3: Write minimal implementation**

```python
import json
from typing import Dict, Any
from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def build_tree_from_markdown(
        self,
        content: str
    ) -> Dict[str, Any]:
        """Build PageIndex tree from markdown text."""
        
        prompt = f"""Analyze this markdown document and create a hierarchical tree structure.

Document Content:
```markdown
{content[:8000]}  # Limit content length
```

Return a JSON object with this structure:
{{
  "nodes": [
    {{
      "id": "0001",
      "level": 0,
      "title": "Document Title",
      "content": "Brief summary of this section",
      "page_start": 1,
      "page_end": 1,
      "children": []
    }}
  ]
}}

Requirements:
- id format: 4-digit string, use nesting for children
- level: 0 for root/h1, increases for nested headers
- page_start/page_end: use line numbers approximated as "page" numbers
- Preserve the markdown header hierarchy (#=level 0, ##=level 1, etc.)

Return ONLY the JSON, no other text."""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=4000
        )
        
        result_text = response.choices[0].message.content
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        return json.loads(result_text.strip())
    
    async def search_tree(
        self,
        tree: Dict[str, Any],
        query: str
    ) -> Dict[str, Any]:
        """Search tree for relevant nodes."""
        
        prompt = f"""Given this document tree structure and a question, find the most relevant nodes.

Document Tree:
{json.dumps(tree, indent=2)}

Question: {query}

Return JSON:
{{
  "thinking": "Your reasoning about which nodes are relevant",
  "node_list": ["0001", "0002.0001"]
}}

Return ONLY the JSON, no other text."""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        return json.loads(result_text.strip())
    
    async def answer_with_text(
        self,
        query: str,
        context: str
    ) -> str:
        """Generate answer from query and text context."""
        
        prompt = f"""Answer this question based on the provided document context.

Context:
```
{context}
```

Question: {query}

Provide a clear, concise answer based only on the context."""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/llm_client.py tests/test_llm_client.py
git commit -m "feat: add OpenAI LLM client for text documents"
```

---

## Task 7: Document Processing Service

**Files:**
- Create: `services/document_service.py`
- Test: `tests/test_document_service.py`

**Step 1: Write the test**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.document_service import DocumentService
from models.schemas import DocumentStatus


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.create = AsyncMock(return_value=MagicMock(
        id="test-id",
        filename="test.pdf",
        format="pdf",
        status=DocumentStatus.PENDING
    ))
    store.update_status = AsyncMock()
    return store


@pytest.mark.asyncio
async def test_process_pdf(mock_store, tmp_path):
    with patch('services.document_service.extract_pdf_pages') as mock_extract, \
         patch('services.document_service.VLMClient') as mock_vlm:
        
        mock_extract.return_value = {1: "page1.jpg"}
        mock_vlm.return_value.build_tree_from_images = AsyncMock(return_value={
            "nodes": [{"id": "0001", "title": "Test"}]
        })
        
        service = DocumentService(mock_store, "test-key")
        
        # Create a test PDF
        import fitz
        pdf_path = tmp_path / "test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((100, 100), "Test")
        doc.save(str(pdf_path))
        doc.close()
        
        result = await service.process_document("test-id", str(pdf_path), "pdf")
        
        assert result is True
        mock_store.update_status.assert_called()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_document_service.py -v`
Expected: FAIL - "services/document_service.py not found"

**Step 3: Write minimal implementation**

```python
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
        self.vlm = VLMClient(api_key, settings.openai_model)
        self.llm = LLMClient(api_key, settings.openai_model)
    
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_document_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/document_service.py tests/test_document_service.py
git commit -m "feat: add document processing service"
```

---

## Task 8: Search Service

**Files:**
- Create: `services/search_service.py`
- Test: `tests/test_search_service.py`

**Step 1: Write the test**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.search_service import SearchService


@pytest.fixture
def mock_clients():
    vlm = MagicMock()
    llm = MagicMock()
    return vlm, llm


@pytest.mark.asyncio
async def test_search_pdf(mock_clients):
    vlm, llm = mock_clients
    vlm.search_tree = AsyncMock(return_value={
        "thinking": "Found relevant section",
        "node_list": ["0001"]
    })
    vlm.answer_with_images = AsyncMock(return_value="The answer is 42")
    
    service = SearchService(vlm, llm)
    
    tree = {
        "nodes": [
            {"id": "0001", "title": "Section 1", "page_start": 1, "page_end": 1}
        ]
    }
    
    with patch('services.search_service.Path.exists', return_value=True):
        result = await service.search("test query", tree, "pdf", "/storage/test")
    
    assert result.query == "test query"
    assert len(result.results) > 0


@pytest.mark.asyncio
async def test_search_markdown(mock_clients):
    vlm, llm = mock_clients
    llm.search_tree = AsyncMock(return_value={
        "thinking": "Found relevant section",
        "node_list": ["0001"]
    })
    llm.answer_with_text = AsyncMock(return_value="The answer is 42")
    
    service = SearchService(vlm, llm)
    
    tree = {
        "nodes": [
            {"id": "0001", "title": "Section 1", "content": "Test content"}
        ]
    }
    
    result = await service.search("test query", tree, "md", "/storage/test")
    
    assert result.query == "test query"
    assert len(result.results) > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_search_service.py -v`
Expected: FAIL - "services/search_service.py not found"

**Step 3: Write minimal implementation**

```python
import time
from pathlib import Path
from typing import List, Dict, Any
from models.schemas import SearchResponse, SearchResult
from services.vlm_client import VLMClient
from services.llm_client import LLMClient


class SearchService:
    def __init__(self, vlm: VLMClient, llm: LLMClient):
        self.vlm = vlm
        self.llm = llm
    
    async def search(
        self,
        query: str,
        tree: Dict[str, Any],
        doc_format: str,
        storage_path: str,
        top_k: int = 3
    ) -> SearchResponse:
        """Perform reasoning-based search."""
        start_time = time.time()
        
        # Use VLM for PDF, LLM for text formats
        if doc_format == "pdf":
            search_result = await self.vlm.search_tree(tree, query)
            results = await self._get_pdf_results(
                query, search_result, tree, storage_path, top_k
            )
        else:
            search_result = await self.llm.search_tree(tree, query)
            results = await self._get_text_results(
                query, search_result, tree, storage_path, top_k
            )
        
        processing_time = (time.time() - start_time) * 1000
        
        return SearchResponse(
            query=query,
            results=results,
            total_nodes=len(results),
            processing_time_ms=processing_time
        )
    
    async def _get_pdf_results(
        self,
        query: str,
        search_result: Dict,
        tree: Dict,
        storage_path: str,
        top_k: int
    ) -> List[SearchResult]:
        """Get results for PDF (with page images)."""
        node_list = search_result.get("node_list", [])[:top_k]
        thinking = search_result.get("thinking", "")
        
        results = []
        node_map = self._build_node_map(tree["nodes"])
        
        for node_id in node_list:
            node = node_map.get(node_id)
            if not node:
                continue
            
            # Get page images for this node
            page_images = []
            pages_dir = Path(storage_path) / "pages"
            for page_num in range(node["page_start"], node["page_end"] + 1):
                img_path = pages_dir / f"page_{page_num:04d}.jpg"
                if img_path.exists():
                    page_images.append(str(img_path))
            
            # Generate answer using VLM with images
            if page_images:
                answer = await self.vlm.answer_with_images(query, page_images)
            else:
                answer = "No visual content available"
            
            results.append(SearchResult(
                node_id=node_id,
                title=node["title"],
                content=answer,
                relevance_score=1.0,
                page_refs=list(range(node["page_start"], node["page_end"] + 1)),
                reasoning_path=[thinking]
            ))
        
        return results
    
    async def _get_text_results(
        self,
        query: str,
        search_result: Dict,
        tree: Dict,
        storage_path: str,
        top_k: int
    ) -> List[SearchResult]:
        """Get results for text documents."""
        node_list = search_result.get("node_list", [])[:top_k]
        thinking = search_result.get("thinking", "")
        
        results = []
        node_map = self._build_node_map(tree["nodes"])
        
        # Load full content
        content_path = Path(storage_path) / "content.txt"
        full_content = ""
        if content_path.exists():
            with open(content_path, "r") as f:
                full_content = f.read()
        
        for node_id in node_list:
            node = node_map.get(node_id)
            if not node:
                continue
            
            # Use node content or extract from full content
            context = node.get("content", "") or full_content[:2000]
            answer = await self.llm.answer_with_text(query, context)
            
            results.append(SearchResult(
                node_id=node_id,
                title=node["title"],
                content=answer,
                relevance_score=1.0,
                page_refs=[node.get("page_start", 1)],
                reasoning_path=[thinking]
            ))
        
        return results
    
    def _build_node_map(self, nodes: List[Dict], prefix: str = "") -> Dict[str, Dict]:
        """Flatten tree to node_id -> node mapping."""
        result = {}
        for node in nodes:
            node_id = node["id"]
            result[node_id] = node
            if "children" in node and node["children"]:
                result.update(self._build_node_map(node["children"]))
        return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_search_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/search_service.py tests/test_search_service.py
git commit -m "feat: add search service with reasoning retrieval"
```

---

## Task 9: FastAPI Application

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the test**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def client():
    with patch('main.DocumentStore') as mock_store, \
         patch('main.DocumentService') as mock_service, \
         patch('main.SearchService') as mock_search:
        
        # Setup mocks
        mock_store_instance = MagicMock()
        mock_store_instance.create = AsyncMock(return_value=MagicMock(
            id="test-id",
            filename="test.pdf",
            format="pdf",
            status="pending"
        ))
        mock_store_instance.get = AsyncMock(return_value=MagicMock(
            id="test-id",
            filename="test.pdf",
            format="pdf",
            status="completed"
        ))
        mock_store.return_value = mock_store_instance
        
        from main import app
        return TestClient(app)


def test_upload_document(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", b"fake pdf content", "application/pdf")}
    )
    assert response.status_code == 202
    assert "document_id" in response.json()


def test_get_document_status(client):
    response = client.get("/api/v1/documents/test-id/status")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL - "main.py not found"

**Step 3: Write minimal implementation**

```python
import shutil
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from config import settings
from models.schemas import DocumentStatus, SearchRequest, SearchResponse
from models.document_store import DocumentStore
from services.document_service import DocumentService
from services.search_service import SearchService
from services.vlm_client import VLMClient
from services.llm_client import LLMClient

# Global instances
doc_store: DocumentService = None
doc_service: DocumentService = None
search_service: SearchService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global doc_store, doc_service, search_service
    
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    
    doc_store = DocumentStore()
    doc_service = DocumentService(doc_store, settings.openai_api_key)
    vlm = VLMClient(settings.openai_api_key, settings.openai_model)
    llm = LLMClient(settings.openai_api_key, settings.openai_model)
    search_service = SearchService(vlm, llm)
    
    yield
    
    # Cleanup if needed


app = FastAPI(
    title="PageIndex API Service",
    description="Format-Adaptive PageIndex RAG API",
    version="1.0.0",
    lifespan=lifespan
)


def get_format_from_filename(filename: str) -> str:
    """Extract format from filename."""
    ext = Path(filename).suffix.lower()
    format_map = {
        ".pdf": "pdf",
        ".md": "md",
        ".markdown": "md",
        ".txt": "txt",
        ".docx": "docx"
    }
    return format_map.get(ext)


@app.post("/api/v1/documents/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Upload a document for processing."""
    file_format = get_format_from_filename(file.filename)
    if not file_format:
        raise HTTPException(400, f"Unsupported file format: {file.filename}")
    
    # Create document record
    doc = await doc_store.create(filename=file.filename, format=file_format)
    
    # Save uploaded file temporarily
    temp_path = settings.storage_path / f"temp_{doc.id}_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Process in background
    background_tasks.add_task(
        doc_service.process_document,
        doc.id,
        str(temp_path),
        file_format
    )
    
    return {
        "document_id": doc.id,
        "status": doc.status.value,
        "message": "Document uploaded and processing started"
    }


@app.get("/api/v1/documents/{doc_id}/status")
async def get_document_status(doc_id: str):
    """Get document processing status."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    
    return {
        "document_id": doc.id,
        "status": doc.status.value,
        "filename": doc.filename,
        "format": doc.format,
        "created_at": doc.created_at.isoformat(),
        "completed_at": doc.completed_at.isoformat() if doc.completed_at else None,
        "error_message": doc.error_message
    }


@app.get("/api/v1/documents/{doc_id}/tree")
async def get_document_tree(doc_id: str):
    """Get document tree structure."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    
    if doc.status != DocumentStatus.COMPLETED:
        raise HTTPException(400, f"Document processing not completed: {doc.status.value}")
    
    tree = doc_service.get_tree(doc_id)
    if not tree:
        raise HTTPException(404, "Tree structure not found")
    
    return {"document_id": doc_id, "tree": tree}


@app.post("/api/v1/documents/{doc_id}/search", response_model=SearchResponse)
async def search_document(doc_id: str, request: SearchRequest):
    """Search within a document."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    
    if doc.status != DocumentStatus.COMPLETED:
        raise HTTPException(400, f"Document processing not completed: {doc.status.value}")
    
    tree = doc_service.get_tree(doc_id)
    if not tree:
        raise HTTPException(404, "Tree structure not found")
    
    storage_path = settings.storage_path / doc_id
    
    result = await search_service.search(
        query=request.query,
        tree=tree,
        doc_format=doc.format,
        storage_path=str(storage_path),
        top_k=request.top_k
    )
    
    return result


@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and its index."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    
    # Delete from store
    await doc_store.delete(doc_id)
    
    # Delete storage
    storage_dir = settings.storage_path / doc_id
    if storage_dir.exists():
        shutil.rmtree(storage_dir)
    
    return {"message": "Document deleted successfully"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "pageindex-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add FastAPI application"
```

---

## Task 10: Integration Test and README

**Files:**
- Create: `tests/test_integration.py`
- Create: `README.md`

**Step 1: Write integration test**

```python
import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.integration
class TestIntegration:
    """Integration tests for the full flow."""
    
    @pytest.fixture
    def client(self):
        with patch('services.vlm_client.VLMClient') as mock_vlm, \
             patch('services.llm_client.LLMClient') as mock_llm:
            
            # Setup VLM mock
            mock_vlm_instance = MagicMock()
            mock_vlm_instance.build_tree_from_images = AsyncMock(return_value={
                "nodes": [
                    {
                        "id": "0001",
                        "level": 0,
                        "title": "Test Document",
                        "content": "Test content",
                        "page_start": 1,
                        "page_end": 1,
                        "children": []
                    }
                ]
            })
            mock_vlm_instance.search_tree = AsyncMock(return_value={
                "thinking": "Found relevant node",
                "node_list": ["0001"]
            })
            mock_vlm_instance.answer_with_images = AsyncMock(return_value="Test answer")
            mock_vlm.return_value = mock_vlm_instance
            
            # Setup LLM mock
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance
            
            from main import app
            return TestClient(app)
    
    def test_full_pdf_flow(self, client, tmp_path):
        """Test complete PDF upload -> process -> search flow."""
        import fitz
        
        # Create test PDF
        pdf_path = tmp_path / "test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((100, 100), "This is a test document about AI technology.")
        doc.save(str(pdf_path))
        doc.close()
        
        # Upload
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        assert response.status_code == 202
        doc_id = response.json()["document_id"]
        
        # Check status (will be pending/processing since it's background)
        response = client.get(f"/api/v1/documents/{doc_id}/status")
        assert response.status_code == 200
        
        print(f"Integration test passed! Document ID: {doc_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Step 2: Create README.md**

```markdown
# PageIndex API Service

Format-Adaptive PageIndex RAG API service supporting PDF (Vision-based) and Markdown/Text (Text-based).

## Features

- 📄 **Multi-format support**: PDF, Markdown, TXT
- 🧠 **Vision-based RAG**: PDF → page images → VLM understanding
- 📝 **Text-based RAG**: Markdown/TXT → direct text parsing → LLM
- 🌳 **Tree Index**: Hierarchical document structure
- 🔍 **Reasoning Retrieval**: LLM-based tree search
- 🚀 **Async processing**: Background document indexing

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your OpenAI API key

# Run server
uvicorn main:app --reload
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/documents/upload` | POST | Upload document (PDF/MD/TXT) |
| `/api/v1/documents/{id}/status` | GET | Check processing status |
| `/api/v1/documents/{id}/tree` | GET | Get document tree structure |
| `/api/v1/documents/{id}/search` | POST | Search document |
| `/api/v1/documents/{id}` | DELETE | Delete document |

## Example Usage

```bash
# Upload PDF
curl -X POST -F "file=@document.pdf" http://localhost:8000/api/v1/documents/upload

# Search document
curl -X POST http://localhost:8000/api/v1/documents/{id}/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the main topic?"}'
```

## Architecture

```
PDF → Page Images → VLM → Tree Index
MD/TXT → Text → LLM → Tree Index
              ↓
        Tree Search (LLM reasoning)
              ↓
        Answer Generation
```
```

**Step 3: Run integration test**

Run: `pytest tests/test_integration.py -v --integration`
Expected: PASS (with mocked LLM calls)

**Step 4: Commit**

```bash
git add tests/test_integration.py README.md
git commit -m "test: add integration tests and documentation"
```

---

## Summary

This plan implements a complete Format-Adaptive PageIndex RAG API service with:

1. **10 tasks** covering all components
2. **TDD approach** - tests written before implementation
3. **Clear file paths** for each task
4. **Exact commands** with expected outputs
5. **Frequent commits** after each task

**Next Steps:**
- Execute plan using `superpowers:executing-plans`
- Or use `superpowers:subagent-driven-development` for subagent execution
