# Hybrid RAG - Technical Implementation Plan

**Spec Version**: 1.0.0 (with clarifications)  
**Plan Version**: 1.0.0  
**Date**: 2025-03-15  
**Status**: Draft

---

## 1. Tech Stack Confirmation

### 1.1 Current Stack (Confirmed)

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| **Language** | Python | 3.13+ | Keep current |
| **Web Framework** | FastAPI | 0.109+ | Async-native, good choice |
| **Package Manager** | uv | latest | Fast, modern |
| **Database** | SQLite + SQLAlchemy | 2.0+ | Async via aiosqlite |
| **Vector DB** | Qdrant (embedded) | 1.17+ | For hybrid search |
| **LLM Client** | OpenAI SDK | 1.12+ | With base_url config |
| **RAG Backends** | PageIndex, LightRAG, HiRAG | latest | Git submodules |

### 1.2 New Dependencies Required

```toml
# pyproject.toml additions (already present)
[project]
dependencies = [
    # ... existing deps ...
    "qdrant-client[fastembed]>=1.12.0",  # Hybrid Search
]
```

**No new major dependencies needed** - implementation uses existing stack.

---

## 2. Architecture Decisions

### 2.1 Content Hash Deduplication

**Decision**: Calculate SHA-256 hash on upload, store in database with UNIQUE constraint

**Rationale**:
- SHA-256 provides collision resistance suitable for content deduplication
- 64-character hex string is storage-efficient
- Normalization (line endings) ensures cross-platform consistency

**Implementation**:
```python
# services/document_service.py
def calculate_content_hash(content: bytes) -> str:
    """Calculate normalized SHA-256 hash."""
    normalized = content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return hashlib.sha256(normalized).hexdigest()
```

### 2.2 Partial Index Failure Strategy

**Decision**: Track per-index status, mark COMPLETED if ≥1 index succeeds

**State Machine**:
```
PENDING → PROCESSING → [INDEX_BUILDING]
                          ↓
            ┌─→ SUCCESS ─┼─→ COMPLETED (if any succeed)
            └─→ FAILURE ─┘
                          ↓
                    FAILED (if all fail)
```

**Storage**:
```json
{
  "available_indexes": ["pageindex", "hybrid_search"],
  "failed_indexes": {
    "lightrag": "timeout during entity extraction"
  }
}
```

### 2.3 Strategy Fallback Mechanism

**Decision**: Transparent fallback with response annotation

**Fallback Chain**:
```
hirag → hybrid_search
lightrag → hybrid_search
pageindex → hybrid_search (if tree unavailable)
hybrid_search → error (no fallback, core strategy)
```

**API Response**:
```json
{
  "strategy_used": {
    "doc_123": "hirag",
    "doc_456": "hybrid_search"
  },
  "fallback_reasons": ["HiRAG index not available for doc_456"]
}
```

### 2.4 File Size Validation

**Decision**: FastAPI middleware for early validation (fail fast)

**Limits**:
- PDF: 100MB (images + text)
- DOCX: 50MB (XML overhead)
- MD/TXT: 20MB (text processing)

**Rationale**: Protect against memory exhaustion during:
- PDF text extraction (PyMuPDF)
- DOCX parsing (python-docx)
- Embedding generation (FastEmbed)

---

## 3. Database Migration Plan

### 3.1 Schema Changes

```sql
-- Migration: 001_add_content_hash_and_index_tracking.sql
-- Generated: 2025-03-15

-- Add content hash for deduplication
ALTER TABLE documents 
ADD COLUMN content_hash VARCHAR(64) NULL;

-- Add index availability tracking
ALTER TABLE documents 
ADD COLUMN available_indexes JSON DEFAULT '[]';

ALTER TABLE documents 
ADD COLUMN failed_indexes JSON DEFAULT '{}';

-- Add file size for analytics
ALTER TABLE documents 
ADD COLUMN file_size INTEGER NULL;

-- Create unique index on content_hash (allow NULLs for backward compat)
CREATE UNIQUE INDEX idx_content_hash 
ON documents(content_hash) 
WHERE content_hash IS NOT NULL;

-- Create index for status queries
CREATE INDEX idx_status_available 
ON documents(status, available_indexes);
```

### 3.2 Backward Compatibility

- `content_hash`: NULLABLE - existing documents remain valid
- `available_indexes`: DEFAULT '[]' - empty array for existing docs
- `file_size`: NULLABLE - optional field

### 3.3 Migration Script

```python
# scripts/migrate_database.py
async def migrate():
    """Run database migrations."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
            -- ... etc
        """))
```

---

## 4. API Changes

### 4.1 Request/Response Models

```python
# models/schemas.py

class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    message: str
    is_duplicate: bool = False          # NEW
    original_document_id: str | None = None  # NEW

class DocumentStatusResponse(BaseModel):
    document_id: str
    status: str
    filename: str
    format: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    content_hash: str | None            # NEW
    available_indexes: list[str] = []   # NEW
    failed_indexes: dict[str, str] = {} # NEW
    file_size: int | None = None        # NEW

class GlobalSearchResponse(BaseModel):
    query: str
    final_answer: str
    sources: list[DocumentSource]
    document_selection_reasoning: str
    total_documents_searched: int
    processing_time_ms: float
    strategy_used: dict[str, str] = {}  # NEW: doc_id -> strategy
    fallback_reasons: list[str] = []    # NEW
```

### 4.2 Error Responses

**413 Payload Too Large** (NEW):
```json
{
  "detail": "File too large",
  "file_format": "pdf",
  "max_size_mb": 100,
  "actual_size_mb": 150
}
```

---

## 5. Implementation Details

### 5.1 Document Upload Flow (Updated)

```
POST /api/v1/documents/upload
    ↓
[Middleware] File size validation
    ↓
Read file content
    ↓
Calculate SHA-256 hash (normalized)
    ↓
Check if hash exists in DB
    ├─→ YES → Return existing document (is_duplicate=true)
    └─→ NO  → Create new document record
                  ↓
           Save original file
                  ↓
           Start background processing
                  ↓
           Return 202 Accepted
```

### 5.2 Background Processing (Updated)

```python
async def process_document(doc_id, file_path, file_format):
    await store.update_status(doc_id, PROCESSING)
    
    text = await _extract_text(file_path, file_format)
    content_hash = calculate_content_hash(text.encode())
    
    # Parallel index building with individual error handling
    indexes = [
        ("pageindex", _build_pageindex),
        ("lightrag", _build_lightrag),
        ("hirag", _build_hirag),
        ("hybrid_search", _build_hybrid_search),
    ]
    
    available = []
    failed = {}
    
    for name, builder in indexes:
        try:
            await builder(doc_id, text)
            available.append(name)
        except Exception as e:
            failed[name] = str(e)
            logger.warning(f"Index {name} failed for {doc_id}: {e}")
    
    # Update document with results
    await store.update_indexes(doc_id, available, failed)
    await store.update_hash(doc_id, content_hash)
    
    if available:
        await store.update_status(doc_id, COMPLETED)
    else:
        await store.update_status(doc_id, FAILED, "All indexes failed")
```

### 5.3 Strategy Fallback (Updated)

```python
async def search(query, strategy, ...):
    if strategy == "auto":
        strategy = _select_strategy(query)
    
    # Get documents with availability check
    candidates = await _select_documents(query)
    
    # Group by available strategy
    strategy_map = {}
    fallback_reasons = []
    
    for doc in candidates:
        requested = strategy
        actual = strategy
        
        if strategy not in doc.available_indexes:
            # Fallback to hybrid_search (always available)
            actual = "hybrid_search"
            fallback_reasons.append(
                f"{requested} not available for {doc.id}, using {actual}"
            )
        
        strategy_map[doc.id] = actual
    
    # Execute search with actual strategies
    results = await _execute_search(query, strategy_map)
    
    return GlobalSearchResponse(
        ...,
        strategy_used=strategy_map,
        fallback_reasons=fallback_reasons
    )
```

---

## 6. File Structure

```
.
├── models/
│   ├── schemas.py              # Update response models
│   └── document_store.py       # Add new columns
├── services/
│   ├── document_service.py     # Add hash calc, partial failure
│   └── global_search_service.py # Add fallback logic
├── middleware/
│   └── file_size_limit.py      # NEW: Size validation
├── scripts/
│   └── migrate_database.py     # NEW: Migration script
└── tests/
    ├── test_deduplication.py   # NEW
    ├── test_fallback.py        # NEW
    └── test_file_limits.py     # NEW
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

| Component | Test Cases | Mock Strategy |
|-----------|-----------|---------------|
| Hash Calculation | Same content → same hash, different line endings | BytesIO |
| Size Validation | Boundary values (99MB pass, 101MB fail) | UploadFile |
| Fallback Logic | Missing index → fallback triggered | Mock DocumentStore |
| Partial Failure | 2/4 indexes fail → COMPLETED | Mock builders |

### 7.2 Integration Tests

| Scenario | Test Steps |
|----------|-----------|
| Duplicate Upload | Upload file → Upload same file → Verify same ID returned |
| Strategy Fallback | Request hirag on doc without HiRAG → Verify hybrid_search used |
| Partial Index | Cause LightRAG to fail → Verify doc COMPLETED with available indexes |
| Size Limit | Upload 150MB PDF → Verify 413 error |

### 7.3 API Contract Tests

```python
# tests/test_api_contract.py
def test_upload_response_has_duplicate_fields():
    response = client.post("/api/v1/documents/upload", ...)
    assert "is_duplicate" in response.json()
    assert "original_document_id" in response.json()

def test_search_response_has_strategy_used():
    response = client.post("/api/v1/search", ...)
    assert "strategy_used" in response.json()
```

---

## 8. Performance Considerations

### 8.1 Hash Calculation

- **Time**: SHA-256 on 100MB file ~50ms (acceptable)
- **Memory**: Streaming read to avoid loading entire file
- **Optimization**: Calculate hash during file read (single pass)

### 8.2 Database Queries

- **Deduplication check**: Single SELECT by hash (indexed)
- **Index availability**: JSON field query (SQLite JSON1 extension)

### 8.3 API Response Size

- `strategy_used`: O(n) where n = number of documents (small, typically <10)
- `fallback_reasons`: Only populated when fallback occurs

---

## 9. Security Considerations

### 9.1 Hash Collision

- SHA-256 collision probability: ~1 in 2^256 (cryptographically negligible)
- Mitigation: Store full content comparison on collision detection

### 9.2 File Size DoS

- Middleware validation prevents memory exhaustion
- Limits are configurable per deployment

### 9.3 Data Exposure

- `content_hash` doesn't expose file content
- `failed_indexes` may expose internal errors - sanitize error messages

---

## 10. Deployment Checklist

### Pre-deployment
- [ ] Run database migration script
- [ ] Update API documentation
- [ ] Verify backward compatibility
- [ ] Run full test suite

### Post-deployment
- [ ] Monitor error rates for new endpoints
- [ ] Check duplicate detection rate (should increase)
- [ ] Verify file size limits working
- [ ] Monitor database size growth

### Rollback Plan
- [ ] Database migration is backward compatible (nullable columns)
- [ ] API changes are additive (new optional fields)
- [ ] Can rollback by reverting code, DB schema remains compatible

---

## Appendix: Configuration

```python
# config.py additions
class Settings(BaseSettings):
    # ... existing settings ...
    
    # File size limits (bytes)
    MAX_FILE_SIZE_PDF: int = 100 * 1024 * 1024    # 100MB
    MAX_FILE_SIZE_DOCX: int = 50 * 1024 * 1024    # 50MB
    MAX_FILE_SIZE_TEXT: int = 20 * 1024 * 1024    # 20MB
    
    # Feature flags
    ENABLE_CONTENT_DEDUP: bool = True
    ENABLE_STRATEGY_FALLBACK: bool = True
    ENABLE_PARTIAL_FAILURE: bool = True
```

---

**Plan Complete** ✅

**Next Step**: `/speckit.tasks` - Generate actionable task list from this plan
