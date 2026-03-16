# Hybrid RAG - Implementation Tasks

**Plan Version**: 1.0.0  
**Generated**: 2025-03-15  
**Status**: Ready for Implementation

---

## Task Summary

| Priority | Category | Tasks | Est. Time |
|----------|----------|-------|-----------|
| 🔴 High | Database | 1 | 2h |
| 🔴 High | Core Features | 6 | 12h |
| 🟡 Medium | API & Integration | 3 | 4h |
| 🟢 Low | Testing | 3 | 4h |
| **Total** | | **13** | **~22h** |

**Legend**: [P] = Parallelizable | [D] = Depends on | → = Next task

---

## Phase 1: Foundation (Database & Models)

### Task 1.1: Database Migration
**Priority**: 🔴 HIGH  
**Estimated**: 2h  
**Files**: `models/document_store.py`, Alembic migration

**Description**: Add new columns to documents table for hash deduplication and index tracking.

**Steps**:
1. [ ] Add `content_hash: Mapped[str | None]` column (VARCHAR(64), unique, nullable)
2. [ ] Add `available_indexes: Mapped[list[str]]` column (JSON, default=[])
3. [ ] Add `failed_indexes: Mapped[dict[str, str]]` column (JSON, default={})
4. [ ] Add `file_size: Mapped[int | None]` column (INTEGER, nullable)
5. [ ] Create database migration script (if using Alembic) or update init script
6. [ ] Test migration on existing database (backward compatibility check)

**Acceptance Criteria**:
- [ ] New columns exist in database schema
- [ ] Existing documents still work (NULL values acceptable)
- [ ] Unique index on content_hash (with NULL exclusion)
- [ ] Migration runs without data loss

**Validation**:
```bash
sqlite3 data/documents.db ".schema documents"
# Should show: content_hash, available_indexes, failed_indexes, file_size
```

---

### Task 1.2: Update Pydantic Schemas [D:1.1]
**Priority**: 🔴 HIGH  
**Estimated**: 1h  
**Files**: `models/schemas.py`

**Description**: Update API request/response models with new fields.

**Steps**:
1. [ ] Update `DocumentUploadResponse`:
   - Add `is_duplicate: bool = False`
   - Add `original_document_id: str | None = None`
2. [ ] Update `DocumentStatusResponse`:
   - Add `content_hash: str | None`
   - Add `available_indexes: list[str]`
   - Add `failed_indexes: dict[str, str]`
   - Add `file_size: int | None`
3. [ ] Update `GlobalSearchResponse`:
   - Add `strategy_used: dict[str, str]`  # doc_id → strategy
   - Add `fallback_reasons: list[str]`
4. [ ] Run mypy to verify type correctness

**Acceptance Criteria**:
- [ ] All new fields have proper type hints
- [ ] Default values set for backward compatibility
- [ ] mypy passes without errors

---

## Phase 2: Core Features (Can Parallelize)

### Task 2.1: Content Hash Calculation [D:1.1] [P]
**Priority**: 🔴 HIGH  
**Estimated**: 2h  
**Files**: `services/document_service.py`

**Description**: Implement SHA-256 hash calculation for content deduplication.

**Steps**:
1. [ ] Import hashlib at module level
2. [ ] Implement `calculate_content_hash(content: bytes) -> str` function:
   ```python
   def calculate_content_hash(content: bytes) -> str:
       """Calculate SHA-256 hash of normalized content."""
       # Normalize line endings: \r\n → \n, \r → \n
       normalized = content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
       return hashlib.sha256(normalized).hexdigest()
   ```
3. [ ] Add `find_by_hash()` method to DocumentStore:
   ```python
   async def find_by_hash(self, content_hash: str) -> Document | None:
       result = await self.session.execute(
           select(Document).where(Document.content_hash == content_hash)
       )
       return result.scalar_one_or_none()
   ```
4. [ ] Add unit test for hash calculation

**Acceptance Criteria**:
- [ ] Same content → same hash (regardless of line endings)
- [ ] Different content → different hash (with high probability)
- [ ] Hash is 64-character hex string
- [ ] Unit tests pass

**Test Case**:
```python
def test_hash_normalization():
    content1 = b"line1\r\nline2\r\n"
    content2 = b"line1\nline2\n"
    assert calculate_content_hash(content1) == calculate_content_hash(content2)
```

---

### Task 2.2: Duplicate Detection on Upload [D:2.1] [P]
**Priority**: 🔴 HIGH  
**Estimated**: 2h  
**Files**: `main.py`, `services/document_service.py`

**Description**: Check for duplicate content before processing new upload.

**Steps**:
1. [ ] Modify `upload_document()` endpoint in `main.py`:
   - Read file content into memory
   - Calculate hash before saving
   - Check if hash exists in database
2. [ ] If duplicate found:
   - Return existing document_id
   - Set `is_duplicate=true`
   - Set `original_document_id` to existing doc
   - Skip background processing
3. [ ] If not duplicate:
   - Proceed with normal upload flow
   - Store hash in document record
4. [ ] Update API response to include new fields

**Acceptance Criteria**:
- [ ] Uploading same file twice returns same document_id
- [ ] Second upload sets `is_duplicate=true`
- [ ] Second upload returns within 100ms (no reprocessing)
- [ ] Different files get different document_ids

**Edge Cases**:
- [ ] Handle hash collision (extremely rare) - compare actual bytes
- [ ] Handle concurrent uploads of same file (race condition)

---

### Task 2.3: File Size Validation Middleware [P]
**Priority**: 🔴 HIGH  
**Estimated**: 2h  
**Files**: `middleware/file_size_limit.py` (new), `main.py`, `config.py`

**Description**: Create FastAPI middleware to validate file sizes before processing.

**Steps**:
1. [ ] Create `middleware/file_size_limit.py`:
   ```python
   from fastapi import HTTPException, Request
   
   MAX_FILE_SIZES = {
       "pdf": 100 * 1024 * 1024,   # 100MB
       "docx": 50 * 1024 * 1024,   # 50MB
       "md": 20 * 1024 * 1024,     # 20MB
       "txt": 20 * 1024 * 1024,    # 20MB
   }
   
   async def file_size_validation(request: Request, call_next):
       # Check Content-Length header or read body
       # Validate against format-specific limits
       # Raise HTTPException(413) if too large
   ```
2. [ ] Add size limits to `config.py` Settings class
3. [ ] Register middleware in `main.py`:
   ```python
   app.add_middleware(file_size_limit)
   ```
4. [ ] Include file size in upload response (for analytics)

**Acceptance Criteria**:
- [ ] PDF >100MB returns HTTP 413
- [ ] DOCX >50MB returns HTTP 413
- [ ] TXT >20MB returns HTTP 413
- [ ] Valid sizes pass through normally
- [ ] Error message includes max size and actual size

**Test**:
```bash
curl -X POST -F "file=@huge.pdf" http://localhost:8000/api/v1/documents/upload
# Should return: {"detail": "File too large", "max_size_mb": 100, "actual_size_mb": 150}
```

---

### Task 2.4: Partial Index Failure Handling [D:1.1] [P]
**Priority**: 🔴 HIGH  
**Estimated**: 3h  
**Files**: `services/document_service.py`

**Description**: Track per-index success/failure, allow partial completion.

**Steps**:
1. [ ] Modify `_build_pageindex()`, `_build_lightrag()`, `_build_hirag()`, `_build_hybrid_search()`:
   - Wrap in try/except
   - Return success indicator or raise exception
2. [ ] Rewrite `process_document()` parallel execution:
   ```python
   available_indexes = []
   failed_indexes = {}
   
   for name, builder in index_builders:
       try:
           await builder(doc_id, text)
           available_indexes.append(name)
       except Exception as e:
           failed_indexes[name] = str(e)
           logger.warning(f"Index {name} failed: {e}")
   
   # Update document with results
   await store.update_indexes(doc_id, available_indexes, failed_indexes)
   
   if available_indexes:
       await store.update_status(doc_id, COMPLETED)
   else:
       await store.update_status(doc_id, FAILED, "All indexes failed")
   ```
3. [ ] Add `update_indexes()` method to DocumentStore
4. [ ] Update Document model with helper methods

**Acceptance Criteria**:
- [ ] If 1/4 indexes fail, document is COMPLETED
- [ ] `available_indexes` contains only successful indexes
- [ ] `failed_indexes` contains error messages
- [ ] If all indexes fail, document is FAILED
- [ ] Error logs contain which index failed and why

**Test Scenario**:
1. Upload document
2. Force LightRAG to fail (mock or break config)
3. Verify document is COMPLETED
4. Verify `available_indexes` doesn't include LightRAG
5. Verify `failed_indexes['lightrag']` has error message

---

### Task 2.5: Strategy Fallback Mechanism [D:1.2] [P]
**Priority**: 🔴 HIGH  
**Estimated**: 3h  
**Files**: `services/global_search_service.py`

**Description**: Implement transparent fallback when requested strategy unavailable.

**Steps**:
1. [ ] Create helper function `_check_strategy_available(doc, strategy) -> bool`
2. [ ] Modify `_search_hirag()`, `_search_lightrag()`, `_search_pageindex()`:
   - Check if requested strategy in `doc.available_indexes`
   - If not available, fallback to `_search_hybrid_search()`
   - Track fallback in response metadata
3. [ ] Update `search()` main entry point:
   ```python
   strategy_map = {}  # doc_id -> actual_strategy_used
   fallback_reasons = []
   
   for doc in candidates:
       actual = strategy
       if strategy not in doc.available_indexes:
           actual = "hybrid_search"
           fallback_reasons.append(
               f"{strategy} not available for {doc.id}, using {actual}"
           )
       strategy_map[doc.id] = actual
   ```
4. [ ] Update GlobalSearchResult to include `strategy_map` and `fallback_reasons`
5. [ ] Update API response serialization

**Acceptance Criteria**:
- [ ] Requesting hirag on doc without HiRAG falls back to hybrid_search
- [ ] Response includes `strategy_used` with actual strategies
- [ ] Response includes `fallback_reasons` explaining why
- [ ] No errors thrown for missing indexes
- [ ] Manual strategy=hybrid_search never falls back (it's the fallback)

**Test**:
```python
# Document has only pageindex and hybrid_search
response = await search(query="test", strategy="hirag")
assert response.strategy_used["doc_123"] == "hybrid_search"
assert "HiRAG not available" in response.fallback_reasons[0]
```

---

## Phase 3: API Integration

### Task 3.1: Update Status Endpoint [D:2.4, 2.5]
**Priority**: 🟡 MEDIUM  
**Estimated**: 1h  
**Files**: `main.py`

**Description**: Include new fields in document status response.

**Steps**:
1. [ ] Modify `get_document_status()` endpoint
2. [ ] Include `content_hash`, `available_indexes`, `failed_indexes`, `file_size` in response
3. [ ] Handle None values gracefully (for backward compatibility)

**Acceptance Criteria**:
- [ ] Status response includes all new fields
- [ ] NULL fields shown as null in JSON
- [ ] Empty arrays shown as [] (not null)

---

### Task 3.2: Update Upload Response [D:2.2]
**Priority**: 🟡 MEDIUM  
**Estimated**: 30m  
**Files**: `main.py`

**Description**: Include duplicate detection fields in upload response.

**Steps**:
1. [ ] Ensure `upload_document()` returns `is_duplicate` and `original_document_id`
2. [ ] Set appropriate HTTP status (200 for duplicate, 202 for new)

**Acceptance Criteria**:
- [ ] Duplicate upload: `is_duplicate=true`, `original_document_id=<existing>`
- [ ] New upload: `is_duplicate=false`, `original_document_id=null`

---

### Task 3.3: Update Search Response [D:2.5]
**Priority**: 🟡 MEDIUM  
**Estimated**: 30m  
**Files**: `services/global_search_service.py`, `models/schemas.py`

**Description**: Wire up strategy tracking to API response.

**Steps**:
1. [ ] Ensure GlobalSearchService returns strategy information
2. [ ] Verify FastAPI serializes new response fields correctly

**Acceptance Criteria**:
- [ ] Search response includes `strategy_used` mapping
- [ ] Search response includes `fallback_reasons` array

---

## Phase 4: Testing

### Task 4.1: Unit Tests for Core Functions
**Priority**: 🟢 LOW  
**Estimated**: 2h  
**Files**: `tests/test_content_hash.py`, `tests/test_fallback.py`

**Description**: Test individual functions in isolation.

**Test Cases**:
1. [ ] Hash calculation with various line endings
2. [ ] Hash collision handling (mock)
3. [ ] File size validation boundaries
4. [ ] Strategy availability checking
5. [ ] Fallback decision logic

**Mock Strategy**:
- Use MagicMock for DocumentStore
- Use pytest fixtures for test data
- Parametrize tests for boundary values

---

### Task 4.2: Integration Tests for Workflows
**Priority**: 🟢 LOW  
**Estimated**: 2h  
**Files**: `tests/test_deduplication.py`, `tests/test_file_limits.py`

**Description**: Test complete user workflows.

**Test Cases**:
1. [ ] Duplicate upload returns same document_id
2. [ ] Large file upload returns 413
3. [ ] Partial index failure marks document COMPLETED
4. [ ] Strategy fallback works end-to-end
5. [ ] Status endpoint shows all new fields

**Setup**:
- Use test database (SQLite in-memory or temp file)
- Clean up files after tests
- Mock external services (OpenAI, etc.)

---

### Task 4.3: API Contract Tests
**Priority**: 🟢 LOW  
**Estimated**: 1h  
**Files**: `tests/test_api_contract.py`

**Description**: Verify API response schemas match specification.

**Test Cases**:
1. [ ] Upload response has all required fields
2. [ ] Status response has all required fields
3. [ ] Search response has all required fields
4. [ ] Field types match schema (string, array, object)
5. [ ] Backward compatibility (old clients still work)

**Validation**:
- Use Pydantic model validation
- Check response schemas against OpenAPI spec

---

## Task Dependencies Graph

```
Task 1.1 (DB Migration)
    ↓
    ├──→ Task 1.2 (Schemas) → Task 2.5 (Fallback) → Task 3.3 (Search Response)
    │
    ├──→ Task 2.1 (Hash Calc) → Task 2.2 (Deduplication) → Task 3.2 (Upload Response)
    │
    ├──→ Task 2.3 (File Size) → Task 4.2 (Integration Tests)
    │
    └──→ Task 2.4 (Partial Failure) → Task 3.1 (Status Endpoint)
    
All Phase 2 tasks can run in parallel after 1.1
All Phase 3 tasks depend on their respective Phase 2 tasks
Phase 4 tests should run after all implementation complete
```

---

## Implementation Order Recommendation

### Week 1: Foundation + Core Features

**Day 1-2: Database & Schemas**
- [ ] Task 1.1: Database Migration
- [ ] Task 1.2: Update Schemas

**Day 3-4: Parallel Implementation [P]**
- [ ] Task 2.1: Content Hash (并行)
- [ ] Task 2.3: File Size Middleware (并行)
- [ ] Task 2.4: Partial Failure (并行)

**Day 5: Integration**
- [ ] Task 2.2: Duplicate Detection
- [ ] Task 2.5: Strategy Fallback

### Week 2: API & Testing

**Day 1-2: API Updates**
- [ ] Task 3.1: Status Endpoint
- [ ] Task 3.2: Upload Response
- [ ] Task 3.3: Search Response

**Day 3-5: Testing & Polish**
- [ ] Task 4.1: Unit Tests
- [ ] Task 4.2: Integration Tests
- [ ] Task 4.3: API Contract Tests
- [ ] Bug fixes and refactoring

---

## Pre-Implementation Checklist

- [ ] Review all tasks with team
- [ ] Set up feature branch: `feat/content-dedup-and-fallback`
- [ ] Ensure test environment has sample documents
- [ ] Verify database backup strategy
- [ ] Confirm file size limits with product owner

---

## Post-Implementation Verification

- [ ] All acceptance criteria met
- [ ] All tests passing (unit + integration)
- [ ] Code review completed
- [ ] API documentation updated
- [ ] Migration tested on staging data
- [ ] Performance benchmarks acceptable

---

**Ready for Implementation** ✅

**Next Step**: `/speckit.implement` to execute all tasks
