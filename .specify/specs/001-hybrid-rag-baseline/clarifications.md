# Clarifications for Hybrid RAG Specification

## Clarification Session

### Q1: Search Strategy Priority and Fallback
**Question**: When multiple strategies could apply (e.g., a query with both keywords AND hierarchical intent), what is the priority order? Should there be a fallback mechanism if the primary strategy returns no results?

**Current State**: The spec defines routing rules but doesn't specify priority when conditions overlap.

**Options**:
- A. Strict priority: hybrid_search > hirag > lightrag > pageindex
- B. Parallel execution with result fusion
- C. Primary + fallback cascade
- D. Confidence-based dynamic selection

---

### Q2: Document Processing Failure Handling
**Question**: When building multiple indexes in parallel, if one index fails (e.g., LightRAG succeeds but HiRAG fails), what should be the document status?

**Current State**: Document status is binary (COMPLETED/FAILED) per the spec.

**Considerations**:
- Should partial success be allowed?
- Should failed indexes be retried automatically?
- Should users be notified which indexes are available?

---

### Q3: Hybrid Search Index Scope
**Question**: Should Hybrid Search (BM25+Vector) index be built per-document or shared across all documents?

**Current State**: Current implementation uses per-document Qdrant collections.

**Trade-offs**:
- Per-document: Better isolation, easier deletion, but cross-doc search requires multiple queries
- Shared: Better for global semantic search, but harder to manage document lifecycle

---

### Q4: Strategy Override Behavior
**Question**: When user manually specifies a strategy but the required index doesn't exist for some documents (e.g., user asks for "hirag" but document only has PageIndex), what should happen?

**Options**:
- A. Return error: "Strategy not available for this document"
- B. Auto-fallback to available strategy
- C. Skip documents without required index
- D. Trigger background index building

---

### Q5: Query Result Limits and Pagination
**Question**: The spec mentions `top_k_documents` and `top_k_results_per_doc`, but doesn't specify:
- Maximum allowed values (API rate limiting)
- Pagination support for large result sets
- Result ordering when merging from multiple documents

**Current Implementation**: Returns top-k without pagination.

---

### Q6: Document Update Mechanism
**Question**: How should document updates/re-uploads be handled?

**Current State**: Not explicitly defined in spec.

**Scenarios**:
- Same filename, new content → Update existing or create new?
- Version history needed?
- Incremental index updates or full rebuild?

---

### Q7: LLM Provider Flexibility
**Question**: Should the system support multiple LLM providers, or is OpenAI the only supported option?

**Current State**: Code uses OpenAI API with configurable base_url.

**Considerations**:
- Support for local models (Ollama, vLLM)?
- Azure OpenAI compatibility?
- Cost/performance trade-off options?

---

### Q8: Concurrent Document Processing Limits
**Question**: Should there be limits on concurrent document processing?

**Current State**: Background tasks use FastAPI's BackgroundTasks.

**Concerns**:
- Resource exhaustion with large files
- Memory limits during embedding generation
- Queue management for multiple uploads

---

### Q9: Search Result Caching
**Question**: Should search results be cached? If so, what is the cache invalidation strategy?

**Current State**: Not mentioned in spec.

**Options**:
- No caching (current behavior)
- Per-query cache with TTL
- Index-version-based invalidation

---

### Q10: Security and Access Control
**Question**: What is the security model for the API?

**Current State**: Spec says "Single-user deployment assumed" in Out of Scope.

**Clarification needed**:
- API key authentication?
- Rate limiting?
- Document isolation (if multi-user in future)?

---

## Preliminary Answers (To Be Confirmed)

Based on current implementation and project context:

1. **Q1 Strategy Priority**: Current implementation uses heuristic-based selection with no fallback. Should implement confidence-based or allow parallel execution.

2. **Q2 Partial Success**: Currently allows partial success - document is COMPLETED if at least one index succeeds.

3. **Q3 Hybrid Scope**: Currently per-document collections. Cross-doc search done via parallel queries.

4. **Q4 Override Behavior**: Currently no validation - will error if index missing. Should implement auto-fallback.

5. **Q5 Pagination**: Not implemented. Should add max limits (e.g., top_k <= 10).

6. **Q6 Updates**: Not implemented. Currently creates new document on each upload.

7. **Q7 LLM Flexibility**: OpenAI-compatible API only. Local models via compatible endpoints.

8. **Q8 Concurrency**: No limits currently. Should add file size and concurrent processing limits.

9. **Q9 Caching**: No caching. Consider adding for repeated queries.

10. **Q10 Security**: No auth currently. API key auth recommended for production.

---

## Action Items

- [ ] Confirm or revise each clarification answer
- [ ] Update specification with clarified requirements
- [ ] Create tickets for gaps between spec and implementation
- [ ] Prioritize clarifications for immediate vs. future implementation
