# Code Review Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all Critical and Important issues found in the code review, plus selected Minor issues that are low-risk, single-line fixes.

**Architecture:** Issues are grouped so each task is independently testable. Critical fixes unblock startup and API correctness. Important fixes address correctness, performance, and cleanup. Minor fixes are low-risk cleanups.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0, asyncio, pytest-asyncio, Pydantic v2

---

## File Map

| File | Change |
|------|--------|
| `lib/hybrid_search/config.yaml` | **Create** — restore deleted config (Critical #1) |
| `models/schemas.py` | **Modify** — make `DocumentSource` accept hybrid chunk fields (Critical #2) |
| `tests/test_document_service.py` | **Rewrite** — test against current `DocumentService` API (Critical #3a) |
| `tests/test_main.py` | **Modify** — add `find_by_hash` to mock_store (Critical #3b) |
| `tests/test_search_service.py` | **Modify** — make `llm.search_tree` an `AsyncMock` (Critical #3c) |
| `lib/hirag_wrapper/wrapper.py` | **Modify** — wrap `insert` in `run_in_executor` (Critical #4) |
| `main.py` | **Modify** — cleanup temp file after processing; fix DELETE to clean backends; fix `getattr` (Important #5, #7, Minor #16) |
| `services/document_service.py` | **Modify** — make index building truly parallel; fix `_build_pageindex_wrapper` indirection; fix DOCX title dedup (Important #6, #12, Minor #17) |
| `services/global_search_service.py` | **Modify** — fix hardcoded storage path (Minor #14) |
| `models/database.py` | **Modify** — fix deprecated SQLAlchemy import; remove `JSONEncodedDict` dead code (Important #10, Minor #15) |
| `lib/pageindex_wrapper/wrapper.py` | **Modify** — replace `get_event_loop()` with `get_running_loop()` (Important #9) |
| `lib/hirag_wrapper/wrapper.py` | **Modify** — replace `get_event_loop()` with `get_running_loop()` in `search()` (Important #9, same file as Critical #4) |
| `services/llm_client.py` | **Modify** — remove Python comment from f-string (Minor #13) |

---

## Task 1: Restore missing `lib/hybrid_search/config.yaml` (Critical)

**Files:**
- Create: `lib/hybrid_search/config.yaml`

- [ ] **Step 1: Create config file**

```yaml
# Hybrid Search 配置 (BM25 + Vector)
# 基于 Qdrant 实现原生 Hybrid Search

enabled: true

# 存储配置
storage:
  path: "./storage/hybrid_search"
  collection_name_template: "doc_{document_id}"

# Chunking 配置
chunking:
  chunk_size: 512
  chunk_overlap: 50
  separators: ["\n\n", "\n", ". ", " "]

# Embedding 配置
embedding:
  model: "BAAI/bge-small-en-v1.5"
  dimensions: 384
  batch_size: 32

# Sparse/BM25 配置
sparse:
  enabled: true

# Hybrid 融合配置
fusion:
  method: "rrf"
  rrf_k: 60

# 检索配置
retrieval:
  top_k_sparse: 20
  top_k_dense: 20
  final_top_k: 10
```

- [ ] **Step 2: Verify the file is found by wrapper**

```bash
python3 -c "
from pathlib import Path
p = Path('lib/hybrid_search/config.yaml')
import yaml
cfg = yaml.safe_load(p.read_text())
print('OK:', cfg['storage'])
"
```

Expected output: `OK: {'path': './storage/hybrid_search', 'collection_name_template': 'doc_{document_id}'}`

- [ ] **Step 3: Commit**

```bash
git add lib/hybrid_search/config.yaml
git commit -m "fix: restore missing lib/hybrid_search/config.yaml (was deleted from config/)"
```

---

## Task 2: Fix `DocumentSource` schema mismatch for `hybrid_search` strategy (Critical)

The `_synthesize_hybrid_answer` method in `global_search_service.py:540-546` returns dicts with keys `chunk_index`, `score`, `text_preview`. But `GlobalSearchResponse.sources` is typed as `list[DocumentSource]` which requires `section_title`, `page_refs`, `node_id`. This causes a Pydantic `ValidationError` at the API boundary when `hybrid_search` strategy is used.

**Fix:** Make the three missing `DocumentSource` fields optional and add the three hybrid-specific fields as optional too, so one model handles both shapes.

**Files:**
- Modify: `models/schemas.py`

- [ ] **Step 1: Update `DocumentSource` model**

Replace lines 122–129 in `models/schemas.py`:

Old:
```python
class DocumentSource(BaseModel):
    """Document source reference model."""

    document_id: str
    document_name: str
    section_title: str
    page_refs: list[int]
    node_id: str
```

New:
```python
class DocumentSource(BaseModel):
    """Document source reference model.

    PageIndex strategy fills: section_title, page_refs, node_id.
    Hybrid Search strategy fills: chunk_index, score, text_preview.
    All strategy-specific fields are optional.
    """

    document_id: str
    document_name: str
    # PageIndex fields
    section_title: str | None = None
    page_refs: list[int] = Field(default_factory=list)
    node_id: str | None = None
    # Hybrid Search fields
    chunk_index: int | None = None
    score: float | None = None
    text_preview: str | None = None
```

- [ ] **Step 2: Verify schema accepts both shapes**

```bash
python3 -c "
from models.schemas import DocumentSource, GlobalSearchResponse
# PageIndex shape
s1 = DocumentSource(document_id='d1', document_name='f.pdf', section_title='Intro', page_refs=[1,2], node_id='0001')
# Hybrid shape
s2 = DocumentSource(document_id='d2', document_name='f2.pdf', chunk_index=3, score=0.85, text_preview='...')
resp = GlobalSearchResponse(query='q', final_answer='a', sources=[s1, s2],
    document_selection_reasoning='r', total_documents_searched=2, processing_time_ms=100.0)
print('OK, sources:', len(resp.sources))
"
```

Expected: `OK, sources: 2`

- [ ] **Step 3: Commit**

```bash
git add models/schemas.py
git commit -m "fix: make DocumentSource fields optional to support both PageIndex and HybridSearch shapes"
```

---

## Task 3: Fix broken tests (Critical)

### 3a — Rewrite `test_document_service.py`

The test patches `extract_pdf_pages` and `VLMClient` which no longer exist in `document_service.py`. The current `DocumentService.__init__` takes `(store, pageindex_wrapper, lightrag_wrapper, hirag_wrapper, hybrid_search_wrapper)`.

**Files:**
- Modify: `tests/test_document_service.py`

- [ ] **Step 1: Rewrite the test file**

```python
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.schemas import DocumentStatus
from services.document_service import DocumentService


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.update_status = AsyncMock()
    store.update_indexes = AsyncMock()
    return store


@pytest.fixture
def mock_pageindex():
    wrapper = MagicMock()
    wrapper.build_tree_from_pdf = AsyncMock(
        return_value={"nodes": [{"id": "0001", "title": "Test", "content": "c",
                                  "page_start": 1, "page_end": 1, "level": 0, "children": []}]}
    )
    wrapper.build_tree_from_markdown = AsyncMock(
        return_value={"nodes": [{"id": "0001", "title": "Test", "content": "c",
                                  "page_start": 1, "page_end": 1, "level": 0, "children": []}]}
    )
    return wrapper


@pytest.mark.asyncio
async def test_process_pdf_success(mock_store, mock_pageindex, tmp_path):
    """PageIndex succeeds → doc marked COMPLETED with pageindex in available_indexes."""
    # Create a minimal real PDF using fitz
    import fitz
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "Test Document")
    doc.save(str(pdf_path))
    doc.close()

    service = DocumentService(store=mock_store, pageindex_wrapper=mock_pageindex)

    with patch("services.document_service.settings") as mock_settings:
        mock_settings.storage_path = tmp_path
        success, available, failed = await service.process_document("test-id", str(pdf_path), "pdf")

    assert success is True
    assert "pageindex" in available
    mock_store.update_status.assert_called_with("test-id", DocumentStatus.COMPLETED)


@pytest.mark.asyncio
async def test_process_md_success(mock_store, mock_pageindex, tmp_path):
    """Markdown processing succeeds."""
    md_path = tmp_path / "test.md"
    md_path.write_text("# Hello\n\nWorld content.")

    service = DocumentService(store=mock_store, pageindex_wrapper=mock_pageindex)

    with patch("services.document_service.settings") as mock_settings:
        mock_settings.storage_path = tmp_path
        success, available, failed = await service.process_document("test-id", str(md_path), "md")

    assert success is True
    assert "pageindex" in available


@pytest.mark.asyncio
async def test_process_all_indexes_fail_marks_failed(mock_store, tmp_path):
    """All indexes fail → doc marked FAILED."""
    bad_pageindex = MagicMock()
    bad_pageindex.build_tree_from_pdf = AsyncMock(side_effect=RuntimeError("API error"))

    import fitz
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    service = DocumentService(store=mock_store, pageindex_wrapper=bad_pageindex)

    with patch("services.document_service.settings") as mock_settings:
        mock_settings.storage_path = tmp_path
        success, available, failed = await service.process_document("test-id", str(pdf_path), "pdf")

    assert success is False
    assert "pageindex" in failed
    mock_store.update_status.assert_called_with("test-id", DocumentStatus.FAILED, "All indexes failed")
```

- [ ] **Step 2: Run test to verify it passes**

```bash
uv run pytest tests/test_document_service.py -v
```

Expected: 3 PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/test_document_service.py
git commit -m "fix: rewrite test_document_service to match current DocumentService API"
```

### 3b — Fix `test_main.py`: add `find_by_hash` to mock_store

**Files:**
- Modify: `tests/test_main.py`

- [ ] **Step 4: Add `find_by_hash` to mock_store fixture**

In `tests/test_main.py`, in the `client` fixture, after the line `mock_store_instance.create = AsyncMock(...)`, add:

```python
    mock_store_instance.find_by_hash = AsyncMock(return_value=None)
```

The fixture body after the fix:

```python
@pytest.fixture
def client():
    import main

    mock_store_instance = MagicMock()
    mock_store_instance.create = AsyncMock(
        return_value=MagicMock(
            id="test-id", filename="test.pdf", format="pdf", status=DocumentStatus.PENDING
        )
    )
    mock_store_instance.find_by_hash = AsyncMock(return_value=None)
    mock_store_instance.get = AsyncMock(
        return_value=MagicMock(
            id="test-id",
            filename="test.pdf",
            format="pdf",
            status=DocumentStatus.COMPLETED,
            created_at=MagicMock(isoformat=lambda: "2025-01-01T00:00:00"),
            completed_at=MagicMock(isoformat=lambda: "2025-01-01T00:01:00"),
            error_message=None,
        )
    )

    main.doc_store = mock_store_instance
    main.doc_service = MagicMock()
    main.search_service = MagicMock()

    from main import app
    return TestClient(app)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_main.py -v
```

Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
git add tests/test_main.py
git commit -m "fix: add find_by_hash AsyncMock to test_main mock_store"
```

### 3c — Fix `test_search_service.py`: make `llm.search_tree` an `AsyncMock`

**Files:**
- Modify: `tests/test_search_service.py`

- [ ] **Step 7: Fix `test_search_pdf` — make `llm.search_tree` an `AsyncMock`**

The `test_search_pdf` test uses `vlm.search_tree = AsyncMock(...)` which is correct. But `llm` is a plain `MagicMock()` with no `search_tree` attribute set. The `SearchService.search` calls `await self.llm.search_tree(...)` for PDF format (when vlm is None). Looking at the test: it passes `vlm` for PDF, so `vlm.search_tree` is used. The issue is `llm` must also have `search_tree` as `AsyncMock` because the service might call it.

Replace the fixture and test to be explicit:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.search_service import SearchService


@pytest.fixture
def mock_vlm():
    vlm = MagicMock()
    vlm.search_tree = AsyncMock(
        return_value={"thinking": "Found relevant section", "node_list": ["0001"]}
    )
    vlm.answer_with_images = AsyncMock(return_value="The answer is 42")
    return vlm


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.search_tree = AsyncMock(
        return_value={"thinking": "Found relevant section", "node_list": ["0001"]}
    )
    llm.answer_with_text = AsyncMock(return_value="The answer is 42")
    return llm


@pytest.mark.asyncio
async def test_search_pdf(mock_vlm, mock_llm):
    service = SearchService(mock_vlm, mock_llm)

    tree = {"nodes": [{"id": "0001", "title": "Section 1", "page_start": 1, "page_end": 1}]}

    with patch("services.search_service.Path.exists", return_value=True):
        result = await service.search("test query", tree, "pdf", "/storage/test")

    assert result.query == "test query"
    assert len(result.results) > 0


@pytest.mark.asyncio
async def test_search_markdown(mock_vlm, mock_llm):
    service = SearchService(mock_vlm, mock_llm)

    tree = {"nodes": [{"id": "0001", "title": "Section 1", "content": "Test content"}]}

    result = await service.search("test query", tree, "md", "/storage/test")

    assert result.query == "test query"
    assert len(result.results) > 0
```

- [ ] **Step 8: Run test to verify it passes**

```bash
uv run pytest tests/test_search_service.py -v
```

Expected: 2 PASSED

- [ ] **Step 9: Commit**

```bash
git add tests/test_search_service.py
git commit -m "fix: make llm.search_tree an AsyncMock in test_search_service"
```

---

## Task 4: Fix HiRAG `index_document` blocking event loop (Critical)

`lib/hirag_wrapper/wrapper.py:243` calls `self._rag.insert(text)` synchronously inside an `async def`. This freezes the FastAPI event loop for the duration of the insert. The fix mirrors how `query` is handled on line 293–294.

**Files:**
- Modify: `lib/hirag_wrapper/wrapper.py`

- [ ] **Step 1: Wrap `insert` in `run_in_executor` and fix deprecated `get_event_loop()` in same method**

Find the `index_document` method. Replace the blocking call and update both deprecated `get_event_loop()` calls in the file.

In `index_document` (around line 243), change:
```python
        self._rag.insert(text)
```
to:
```python
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._rag.insert, text)
```

In `search` (around line 293), change:
```python
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._rag.query, query, param)
```
to:
```python
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._rag.query, query, param)
```

- [ ] **Step 2: Verify no `get_event_loop` remains in hirag wrapper**

```bash
grep -n "get_event_loop" lib/hirag_wrapper/wrapper.py
```

Expected: no output

- [ ] **Step 3: Run hirag tests**

```bash
uv run pytest tests/test_hirag_wrapper.py -v
```

Expected: tests pass (or skip if no qdrant/hirag available)

- [ ] **Step 4: Commit**

```bash
git add lib/hirag_wrapper/wrapper.py
git commit -m "fix: wrap HiRAG insert() in run_in_executor to avoid blocking event loop; replace deprecated get_event_loop()"
```

---

## Task 5: Fix temp file leak and PageIndex wrapper indirection (Important)

**Files:**
- Modify: `main.py`
- Modify: `services/document_service.py`

### 5a — Delete temp file after copying to storage

In `main.py`, after `background_tasks.add_task(...)` is called, the temp file is never cleaned up. The right place to delete it is inside `DocumentService.process_document` after `shutil.copy`.

In `services/document_service.py`, after line 119 (`shutil.copy(file_path, original_path)`), add:

```python
            # Delete temp upload file now that it has been copied
            temp = Path(file_path)
            if temp.exists() and temp.name.startswith("temp_"):
                temp.unlink()
```

- [ ] **Step 1: Add temp file cleanup in `document_service.py`**

The section after `shutil.copy` should look like:

```python
            # Copy original file
            original_path = storage_dir / f"original.{file_format}"
            shutil.copy(file_path, original_path)

            # Delete temp upload file now that it has been copied
            temp = Path(file_path)
            if temp.exists() and temp.name.startswith("temp_"):
                temp.unlink()

            # 提取文本（根据格式）
            text = await self._extract_text(original_path, file_format)
```

### 5b — Remove `_build_pageindex_wrapper` one-line indirection

In `services/document_service.py`, the `_build_pageindex_wrapper` method (lines 171–175) is a one-liner that just calls `_build_pageindex`. Update the reference in `process_document` to call `_build_pageindex` directly and remove `_build_pageindex_wrapper`.

In `process_document`, change:
```python
                index_builders.append(
                    ("pageindex", self._build_pageindex_wrapper(doc_id, original_path, file_format, storage_dir))
                )
```
to:
```python
                index_builders.append(
                    ("pageindex", self._build_pageindex(doc_id, original_path, file_format, storage_dir))
                )
```

Then delete the `_build_pageindex_wrapper` method entirely.

- [ ] **Step 2: Run tests to verify no regression**

```bash
uv run pytest tests/test_document_service.py -v
```

Expected: 3 PASSED

- [ ] **Step 3: Commit**

```bash
git add services/document_service.py
git commit -m "fix: cleanup temp upload file after copy; remove one-line _build_pageindex_wrapper indirection"
```

---

## Task 6: Make index building truly parallel (Important)

In `services/document_service.py` lines 142–150, the comment says "并行构建索引" but implementation is a sequential `for` loop with `await`. Replace with `asyncio.gather`.

**Files:**
- Modify: `services/document_service.py`

- [ ] **Step 1: Replace sequential loop with `asyncio.gather`**

Find and replace the sequential execution block. The current code:

```python
            # 执行所有索引构建，跟踪成功/失败
            for index_name, builder_coro in index_builders:
                try:
                    await builder_coro
                    available_indexes.append(index_name)
                    print(f"[DocumentService] {index_name} index built successfully for {doc_id}")
                except Exception as e:
                    error_msg = str(e)
                    failed_indexes[index_name] = error_msg
                    print(f"[DocumentService] {index_name} index failed for {doc_id}: {error_msg}")
```

Replace with:

```python
            # 并行执行所有索引构建，跟踪成功/失败
            if index_builders:
                names = [name for name, _ in index_builders]
                coros = [coro for _, coro in index_builders]
                results = await asyncio.gather(*coros, return_exceptions=True)
                for index_name, result in zip(names, results):
                    if isinstance(result, Exception):
                        error_msg = str(result)
                        failed_indexes[index_name] = error_msg
                        print(f"[DocumentService] {index_name} index failed for {doc_id}: {error_msg}")
                    else:
                        available_indexes.append(index_name)
                        print(f"[DocumentService] {index_name} index built successfully for {doc_id}")
```

Also add `import asyncio` if not already present at top of `document_service.py`. (Check: it's not currently imported.)

- [ ] **Step 2: Add asyncio import to `document_service.py`**

Add at top of file after the existing imports:
```python
import asyncio
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_document_service.py -v
```

Expected: 3 PASSED

- [ ] **Step 4: Commit**

```bash
git add services/document_service.py
git commit -m "fix: make index building truly parallel using asyncio.gather instead of sequential await loop"
```

---

## Task 7: Fix DELETE endpoint to clean backend indexes (Important)

When a document is deleted via `DELETE /api/v1/documents/{doc_id}`, only the SQLite record and `./storage/{doc_id}/` are removed. LightRAG, HiRAG, and HybridSearch each maintain separate storage. Fix the endpoint to call `delete_document` on each backend that was used.

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update DELETE endpoint**

Replace the `delete_document` endpoint (lines 301–316) with:

```python
@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and its index from all backends."""
    doc = await doc_store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    available = doc.available_indexes or []

    # Delete from store (SQLite)
    await doc_store.delete(doc_id)

    # Delete file storage
    storage_dir = settings.storage_path / doc_id
    if storage_dir.exists():
        shutil.rmtree(storage_dir)

    # Delete from backend indexes that were built for this document
    if "lightrag" in available and lightrag_wrapper:
        try:
            await lightrag_wrapper.delete_document(doc_id)
        except Exception as e:
            print(f"[Delete] LightRAG cleanup failed for {doc_id}: {e}")

    if "hirag" in available and hirag_wrapper:
        try:
            await hirag_wrapper.delete_document(doc_id)
        except Exception as e:
            print(f"[Delete] HiRAG cleanup failed for {doc_id}: {e}")

    if "hybrid_search" in available and hybrid_search_wrapper:
        try:
            await hybrid_search_wrapper.delete_document(doc_id)
        except Exception as e:
            print(f"[Delete] HybridSearch cleanup failed for {doc_id}: {e}")

    return {"message": "Document deleted successfully"}
```

- [ ] **Step 2: Verify LightRAG and HiRAG wrappers have `delete_document` method**

```bash
grep -n "def delete_document" lib/lightrag/wrapper.py lib/hirag_wrapper/wrapper.py lib/hybrid_search/wrapper.py
```

If `delete_document` is missing from lightrag or hirag wrapper, add a stub that prints a warning:

For `lib/lightrag/wrapper.py`, if missing, add:
```python
    async def delete_document(self, document_id: str) -> bool:
        """Delete document from LightRAG index (best-effort)."""
        print(f"[LightRAGWrapper] delete_document not supported by lightrag-hku: {document_id}")
        return False
```

For `lib/hirag_wrapper/wrapper.py`, if missing, add:
```python
    async def delete_document(self, document_id: str) -> bool:
        """Delete document from HiRAG index (best-effort)."""
        print(f"[HiRAGWrapper] delete_document not supported: {document_id}")
        return False
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_main.py -v
```

Expected: 2 PASSED

- [ ] **Step 4: Commit**

```bash
git add main.py lib/lightrag/wrapper.py lib/hirag_wrapper/wrapper.py
git commit -m "fix: DELETE endpoint now cleans backend indexes (LightRAG/HiRAG/HybridSearch)"
```

---

## Task 8: Fix deprecated SQLAlchemy import and remove dead code (Important + Minor)

**Files:**
- Modify: `models/database.py`

- [ ] **Step 1: Fix deprecated import**

In `models/database.py` line 11, change:
```python
from sqlalchemy.ext.declarative import declarative_base
```
to:
```python
from sqlalchemy.orm import declarative_base
```

- [ ] **Step 2: Remove unused `JSONEncodedDict` class**

Delete lines 18–49 (the entire `JSONEncodedDict` class definition). It is defined but never used — columns use plain `String` with manual `json.loads/dumps`.

- [ ] **Step 3: Verify database still works**

```bash
python3 -c "
from models.database import Base, DocumentRecord, init_db
import tempfile, os
with tempfile.TemporaryDirectory() as d:
    engine = init_db(f'sqlite:///{d}/test.db')
    print('DB init OK, tables:', list(Base.metadata.tables.keys()))
"
```

Expected: `DB init OK, tables: ['documents']` (no deprecation warnings)

- [ ] **Step 4: Run store tests**

```bash
uv run pytest tests/test_document_store.py -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add models/database.py
git commit -m "fix: use sqlalchemy.orm.declarative_base (SQLAlchemy 2.0); remove unused JSONEncodedDict"
```

---

## Task 9: Fix remaining deprecations and minor cleanups (Important + Minor)

**Files:**
- Modify: `lib/pageindex_wrapper/wrapper.py`
- Modify: `services/global_search_service.py`
- Modify: `services/llm_client.py`
- Modify: `main.py`

- [ ] **Step 1: Fix deprecated `get_event_loop()` in `pageindex_wrapper/wrapper.py`**

```bash
grep -n "get_event_loop" lib/pageindex_wrapper/wrapper.py
```

Change all occurrences of `asyncio.get_event_loop()` to `asyncio.get_running_loop()`.

- [ ] **Step 2: Fix hardcoded storage path in `global_search_service.py:636`**

Change:
```python
            storage_path = f"./storage/{candidate.doc_id}"
```
to:
```python
            from config import settings
            storage_path = str(settings.storage_path / candidate.doc_id)
```

- [ ] **Step 3: Remove Python comment from LLM f-string in `llm_client.py:21`**

The prompt template has:
```python
{content[:8000]}  # Limit content length
```

The `# Limit content length` comment is inside the f-string and will be sent to the LLM. Change it to:
```python
{content[:8000]}
```

- [ ] **Step 4: Remove unnecessary `getattr` in `main.py:338`**

Change:
```python
    strategy = getattr(request, "strategy", "auto")
```
to:
```python
    strategy = request.strategy
```

- [ ] **Step 5: Fix DOCX title deduplication in `document_service.py`**

In `_convert_docx_to_markdown`, the title-skipping logic at line 359 is:
```python
                if has_title and text == markdown_lines[0].strip("# \n"):
                    continue
```

This breaks when the first paragraph has a Heading 1 style (emits twice). Fix: track the first paragraph text directly instead of comparing against `markdown_lines[0]`.

Replace the entire title tracking block. Change:

```python
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
            if "heading 1" in style_name:
                markdown_lines.append(f"# {text}\n\n")
            elif "heading 2" in style_name:
                markdown_lines.append(f"## {text}\n\n")
            elif "heading 3" in style_name:
                markdown_lines.append(f"### {text}\n\n")
            elif "heading 4" in style_name:
                markdown_lines.append(f"#### {text}\n\n")
            elif "heading 5" in style_name:
                markdown_lines.append(f"##### {text}\n\n")
            elif "heading 6" in style_name:
                markdown_lines.append(f"###### {text}\n\n")
            else:
                # 跳过已经作为标题的段落
                if has_title and text == markdown_lines[0].strip("# \n"):
                    continue
                markdown_lines.append(f"{text}\n\n")
```

With:

```python
        # 找到第一个非空段落文本，作为文档标题（仅当它不是已有标题样式时）
        injected_title_text: str | None = None
        for paragraph in doc.paragraphs[:5]:
            text = paragraph.text.strip()
            if text:
                style_name = paragraph.style.name.lower()
                # 如果第一段已经是标题样式，不需要额外注入
                if not any(f"heading {i}" in style_name for i in range(1, 7)):
                    markdown_lines.append(f"# {text}\n\n")
                    injected_title_text = text
                break

        # 处理段落
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue

            # 根据样式判断标题级别
            style_name = paragraph.style.name.lower()
            if "heading 1" in style_name:
                markdown_lines.append(f"# {text}\n\n")
            elif "heading 2" in style_name:
                markdown_lines.append(f"## {text}\n\n")
            elif "heading 3" in style_name:
                markdown_lines.append(f"### {text}\n\n")
            elif "heading 4" in style_name:
                markdown_lines.append(f"#### {text}\n\n")
            elif "heading 5" in style_name:
                markdown_lines.append(f"##### {text}\n\n")
            elif "heading 6" in style_name:
                markdown_lines.append(f"###### {text}\n\n")
            else:
                # 跳过已经手动注入为标题的段落
                if injected_title_text is not None and text == injected_title_text:
                    injected_title_text = None  # 只跳过一次
                    continue
                markdown_lines.append(f"{text}\n\n")
```

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest -v -m "not integration"
```

Expected: all passing, no errors

- [ ] **Step 7: Commit**

```bash
git add lib/pageindex_wrapper/wrapper.py services/global_search_service.py services/llm_client.py main.py services/document_service.py
git commit -m "fix: replace deprecated get_event_loop(); fix hardcoded storage path; remove comment from LLM prompt; fix DOCX title dedup; simplify getattr"
```

---

## Task 10: Final validation

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest -v 2>&1 | tail -20
```

Expected: 0 errors, 0 failures. Integration tests may be skipped if external services not available — that is acceptable.

- [ ] **Step 2: Verify service imports cleanly**

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from config import settings
from models.database import Base, DocumentRecord
from models.schemas import DocumentSource, GlobalSearchResponse
from services.document_service import DocumentService
from services.global_search_service import GlobalSearchService
print('All imports OK')
"
```

Expected: `All imports OK` with no warnings

- [ ] **Step 3: Final commit summary**

```bash
git log --oneline -10
```

Review that all 9 commits are present and messages are clear.
