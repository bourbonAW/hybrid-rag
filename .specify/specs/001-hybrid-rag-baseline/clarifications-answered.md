# Clarifications - ANSWERED

**Status**: ✅ Confirmed by Product Owner  
**Date**: 2025-03-15

---

## Q1: Strategy Fallback Mechanism ✅

**Decision**: Option B - Automatic fallback to `hybrid_search`

**Behavior**:
1. User requests specific strategy (e.g., `strategy=hirag`)
2. System checks if requested index exists for each document
3. For documents WITHOUT requested index: fallback to `hybrid_search`
4. For documents WITH requested index: use requested strategy
5. Return response with `strategy_used` field indicating actual strategies per document

**API Response Update**:
```json
{
  "final_answer": "...",
  "strategy_used": {
    "doc_123": "hirag",
    "doc_456": "hybrid_search"  // fallback
  },
  "fallback_reason": "HiRAG index not available for doc_456"
}
```

---

## Q2: Partial Index Failure ✅

**Decision**: Option B - Mark COMPLETED with available indexes recorded

**Behavior**:
1. Parallel index building continues even if one fails
2. Document status = COMPLETED if at least ONE index succeeds
3. Store `available_indexes` array in document metadata
4. Failed indexes logged for debugging but don't block completion

**Document Metadata Update**:
```json
{
  "id": "doc_123",
  "status": "COMPLETED",
  "available_indexes": ["pageindex", "hybrid_search"],
  "failed_indexes": ["lightrag"],
  "index_errors": {
    "lightrag": "timeout during entity extraction"
  }
}
```

---

## Q3: Pagination ✅

**Decision**: Option A - Not implemented in current version

**Rationale**: Keep API simple for initial release

**Future Consideration**: Add pagination when:
- Average documents per user > 100
- Average results per query > 50
- User feedback indicates need

---

## Q4: Document Update Mechanism ✅

**Decision**: Custom - Content-based deduplication using SHA-256 hash

**Design**:

### 4.1 Content Hash Calculation
```python
import hashlib

def calculate_content_hash(file_content: bytes) -> str:
    """Calculate SHA-256 hash of normalized file content."""
    # Normalize: remove BOM, standardize line endings
    normalized = file_content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return hashlib.sha256(normalized).hexdigest()
```

### 4.2 Upload Flow
```
User Upload
    ↓
Calculate SHA-256 hash
    ↓
Check if hash exists in database
    ├─→ YES: Return existing document_id (deduplication)
    └─→ NO: Create new document, store hash
```

### 4.3 Database Schema Update
```sql
ALTER TABLE documents ADD COLUMN content_hash VARCHAR(64) UNIQUE;
CREATE INDEX idx_content_hash ON documents(content_hash);
```

### 4.4 API Response
```json
{
  "document_id": "doc_123",
  "status": "COMPLETED",
  "is_duplicate": true,
  "original_document_id": "doc_001",
  "message": "Document already exists, returning existing document"
}
```

### 4.5 Edge Cases
- **Same content, different filename**: Deduplicate (return existing)
- **Same filename, different content**: Create new document
- **Hash collision (extremely rare)**: Compare actual content bytes

---

## Q5: Concurrent Processing Limits ✅

**Decision**: Option B - Add file size limit

**Specification**:

### 5.1 File Size Limits
| Format | Max Size | Rationale |
|--------|----------|-----------|
| PDF | 100 MB | PDF processing memory intensive |
| DOCX | 50 MB | Word XML parsing overhead |
| Markdown/TXT | 20 MB | Text processing limits |

### 5.2 Size Check Implementation
```python
MAX_FILE_SIZES = {
    "pdf": 100 * 1024 * 1024,    # 100 MB
    "docx": 50 * 1024 * 1024,    # 50 MB
    "md": 20 * 1024 * 1024,      # 20 MB
    "txt": 20 * 1024 * 1024,     # 20 MB
}

async def upload_document(file: UploadFile):
    content = await file.read()
    file_format = get_format_from_filename(file.filename)
    
    if len(content) > MAX_FILE_SIZES.get(file_format, 20 * 1024 * 1024):
        raise HTTPException(
            413, 
            f"File too large. Max size for {file_format}: {MAX_FILE_SIZES[file_format] // (1024*1024)}MB"
        )
```

### 5.3 Future Enhancement (Out of Scope)
- Concurrent document processing queue
- Rate limiting per user/IP
- Background job priority levels

---

## Summary of Changes Required

### Specification Updates
- [ ] Update US-1 with content hash deduplication
- [ ] Update US-2 with strategy fallback behavior
- [ ] Update FR-1.2 with partial failure handling
- [ ] Add FR-1.4: Content Hash Deduplication
- [ ] Add NFR-5: File Size Limits

### API Changes
- [ ] Add `content_hash` field to document metadata
- [ ] Add `available_indexes` field to status response
- [ ] Add `strategy_used` field to search response
- [ ] Add `is_duplicate` field to upload response

### Implementation Tasks
- [ ] Implement SHA-256 content hash calculation
- [ ] Add database index on content_hash
- [ ] Implement strategy fallback logic
- [ ] Update document status logic for partial failures
- [ ] Add file size validation middleware

---

**Next Step**: Update specification with these clarifications → `/speckit.plan`
