# Hybrid Search Modules (`lib/`)

This directory contains hybrid search / RAG (Retrieval-Augmented Generation) module implementations integrated into the project.

## Purpose

The `lib/` directory serves as a unified location for:

1. **Git Submodules**: External open-source hybrid search projects
2. **PyPI-based Integrations**: Python packages with custom wrappers
3. **Custom Implementations**: From-scratch implementations based on research papers

## Module List

| Module | Source | Status | Description |
|--------|--------|--------|-------------|
| [pageindex](pageindex/) | Git Submodule | ✅ Active | TOC-aware tree-based RAG with reasoning-based navigation |
| [lightrag](lightrag/) | PyPI | ✅ Active | Graph-based RAG with dual-level retrieval (entities + communities) |
| hirag | Planned | 📋 Planned | Hierarchical knowledge indexing with GMM clustering |

## Directory Structure

```
lib/
├── README.md              # This file
├── pageindex/             # Git submodule: PageIndex
│   ├── pageindex/         # Core Python package
│   ├── tutorials/         # Usage examples
│   ├── tests/             # Module tests
│   └── ...
├── lightrag/              # LightRAG integration (lightrag-hku wrapper)
│   ├── __init__.py        # Module exports
│   ├── wrapper.py         # LightRAGWrapper implementation
│   └── config.yaml        # Module configuration
└── hirag/                 # HiRAG integration (to be created)
    └── ...
```

## Integration Approaches

### 1. Git Submodule (e.g., PageIndex)

**When to use**: Active external project that you want to track/update

```bash
# Add submodule
cd lib
git submodule add https://github.com/user/repo.git modulename
cd ..
git add .gitmodules lib/modulename
git commit -m "Add modulename as submodule"

# Update to latest
git submodule update --remote lib/modulename
```

**Characteristics**:
- Tracks upstream changes
- Can contribute back to original project
- Requires `git submodule update --init` on clone
- Version controlled independently

### 2. PyPI Package

**When to use**: Stable release available on PyPI

```bash
# Install via uv
uv add package-name

# Or in pyproject.toml
[project]
dependencies = [
    "package-name>=1.0.0",
]
```

**Characteristics**:
- Easy version management
- No git complexity
- May need wrapper for API adaptation

### 3. Custom Implementation

**When to use**: Research paper implementation, learning exercise, or custom needs

```bash
# Create module structure
mkdir lib/customrag
touch lib/customrag/__init__.py
# Implement core logic
```

**Characteristics**:
- Full control over implementation
- Can optimize for specific use cases
- Requires more development effort

## Wrapper Pattern

Each module should have a corresponding wrapper in `services/{module}_wrapper.py`:

```python
# services/modulename_wrapper.py

class ModuleNameWrapper:
    """
    Wrapper for ModuleName hybrid search implementation.
    
    Responsibilities:
    - Load module configuration
    - Adapt module API to project interfaces
    - Handle async/sync conversion
    - Normalize output formats
    """
    
    def __init__(self):
        self.config = self._load_config()
        self.client = self._initialize_client()
    
    async def build_index(self, document_id: str, content: str) -> IndexResult:
        """Build index for a document"""
        pass
    
    async def search(
        self, 
        document_id: str, 
        query: str,
        top_k: int = 5
    ) -> SearchResult:
        """Search within a document"""
        pass
```

## Configuration

Each module should have its own configuration file:

```yaml
# config/modulename_config.yaml

# LLM settings
llm:
  model: "gpt-4o-mini"
  temperature: 0.0

# Module-specific settings
indexing:
  param1: value1
  param2: value2

retrieval:
  top_k: 10
  strategy: "default"
```

## Adding a New Module

### Step-by-Step Guide

1. **Choose Integration Approach**
   - Git submodule (external repo)
   - PyPI package (stable release)
   - Custom implementation (from scratch)

2. **Create Module Directory**
   ```bash
   mkdir lib/modulename
   ```

3. **Initialize Module**
   - If submodule: `git submodule add <url> lib/modulename`
   - If custom: Create `__init__.py` and core modules

4. **Create Wrapper**
   - Implement `services/modulename_wrapper.py`
   - Adapt module API to project interfaces
   - Handle configuration loading

5. **Add Configuration**
   - Create `config/modulename_config.yaml`
   - Define module-specific settings

6. **Update DocumentService**
   - Add module to document processing pipeline
   - Conditionally build index based on config

7. **Update GlobalSearchService**
   - Add module to strategy selection
   - Implement module-specific retrieval logic

8. **Add Tests**
   - Create `tests/test_modulename/`
   - Unit tests for wrapper
   - Integration tests for end-to-end flow

9. **Update Documentation**
   - Update this README
   - Add module to main project README
   - Document API and configuration

## Module Comparison

| Feature | PageIndex | LightRAG | HiRAG |
|---------|-----------|----------|-------|
| **Data Structure** | Tree | Graph | Hierarchy |
| **Best For** | Single-document deep analysis | Multi-document discovery | Complex hierarchical docs |
| **Retrieval** | Reasoning-based tree navigation | Entity + Community dual-level | Multi-level traversal |
| **TOC Awareness** | ✅ Native | ⚠️ Requires preprocessing | ⚠️ Requires preprocessing |
| **Incremental Update** | ❌ | ✅ | ✅ |
| **Scalability** | <5 docs optimal | 50+ docs | 100+ docs |
| **Latency** | 5-15s (multi-doc) | <1s | <2s |

## References

- [PageIndex](https://github.com/VectifyAI/PageIndex) - TOC-aware tree RAG
- [LightRAG Paper](https://arxiv.org/abs/2410.05779) - Graph-based dual-level retrieval
- [HiRAG Paper](https://arxiv.org/abs/2503.10150) - Hierarchical knowledge indexing

## Contributing

When adding a new module:

1. Follow the wrapper pattern for consistent interfaces
2. Add comprehensive tests
3. Document configuration options
4. Update this README with module details
5. Consider performance benchmarks
