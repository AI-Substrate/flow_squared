# Test Fixtures

This directory contains test fixtures for fs2, including pre-computed embeddings and smart content for testing the Search feature.

## Directory Structure

```
tests/fixtures/
├── README.md                 # This file
├── fixture_graph.pkl         # Pre-computed graph with embeddings and smart_content
├── samples/                  # Source code samples for fixture generation
│   ├── python/              # Python samples
│   ├── javascript/          # JS/TS/TSX samples
│   ├── go/                  # Go samples
│   ├── rust/                # Rust samples
│   ├── java/                # Java samples
│   ├── c/                   # C/C++ samples
│   ├── ruby/                # Ruby samples
│   ├── bash/                # Shell script samples
│   ├── sql/                 # SQL samples
│   ├── terraform/           # Terraform samples
│   ├── docker/              # Dockerfile samples
│   ├── yaml/                # YAML samples
│   ├── toml/                # TOML samples
│   ├── json/                # JSON samples
│   └── markdown/            # Markdown samples
└── ast_samples/              # Existing AST parser test samples
```

## Fixture Graph (`fixture_graph.pkl`)

The fixture graph contains real embeddings and AI-generated descriptions for the sample files. This enables:

- **FakeEmbeddingAdapter**: Returns real embeddings for known content
- **FakeLLMAdapter**: Returns real smart_content for known code blocks
- **FixtureIndex**: O(1) lookup by content_hash

### Generation

To regenerate the fixture graph with real embeddings:

```bash
# Set Azure OpenAI credentials
export FS2_AZURE__OPENAI__ENDPOINT="https://your-endpoint.openai.azure.com/"
export FS2_AZURE__OPENAI__KEY="your-api-key"
export FS2_AZURE__OPENAI__DEPLOYMENT_NAME="gpt-4"
export FS2_AZURE__OPENAI__EMBEDDING_DEPLOYMENT_NAME="text-embedding-ada-002"

# Generate fixtures
just generate-fixtures
```

Without credentials, the script still generates a valid graph but without embeddings or smart_content.

### Usage in Tests

```python
from fs2.core.models.fixture_index import FixtureIndex
from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

# Build index from fixture graph
# (In practice, use the pytest fixtures from conftest.py)
from fs2.core.repos import NetworkXGraphStore
from fs2.config.service import FakeConfigurationService
from fs2.config.objects import ScanConfig, GraphConfig

config = FakeConfigurationService(
    ScanConfig(scan_paths=["."]),
    GraphConfig(graph_path="tests/fixtures/fixture_graph.pkl"),
)
store = NetworkXGraphStore(config)
store.load(Path("tests/fixtures/fixture_graph.pkl"))
index = FixtureIndex.from_nodes(store.get_all_nodes())

# Use with fake adapters
embedding_adapter = FakeEmbeddingAdapter(fixture_index=index)
llm_adapter = FakeLLMAdapter(fixture_index=index)

# Embeddings: Known content returns real embeddings
embedding = await embedding_adapter.embed_text("def add(a, b): return a + b")
# Returns real embedding if content is in fixture, else deterministic fallback

# Smart content: Known code blocks return real descriptions
response = await llm_adapter.generate('''
```python
def add(a, b): return a + b
```
''')
# Returns real smart_content if code is in fixture, else placeholder
```

## Sample Files (`samples/`)

The samples directory contains realistic code samples covering 15+ file types:

| Language/Format | Files | Purpose |
|-----------------|-------|---------|
| Python | 2 | Classes, async, dataclasses |
| JavaScript/TypeScript | 3 | ES6, React, TypeScript |
| Go | 1 | HTTP server, goroutines |
| Rust | 1 | Generics, traits, lifetimes |
| Java | 1 | Records, streams, async |
| C/C++ | 2 | Algorithms, templates |
| Ruby | 1 | Rake tasks, modules |
| Bash | 1 | Deployment scripts |
| SQL | 1 | PostgreSQL schema |
| Terraform | 1 | AWS infrastructure |
| Dockerfile | 1 | Multi-stage builds |
| YAML | 1 | Kubernetes manifests |
| TOML | 1 | Application config |
| JSON | 1 | package.json |
| Markdown | 1 | README documentation |

Each sample is 70-230 lines of realistic, well-structured code.

## FixtureIndex API

```python
from fs2.core.models.fixture_index import FixtureIndex

# Create from nodes
index = FixtureIndex.from_nodes(nodes)

# Lookup by content hash
embedding = index.get_embedding(content_hash)  # Returns tuple | None
smart = index.get_smart_content(content_hash)  # Returns str | None

# Convenience: lookup by raw content
embedding = index.lookup_embedding("def add(a, b): return a + b")
smart = index.lookup_smart_content("def add(a, b): return a + b")

# Extract code from LLM prompts
code = FixtureIndex.extract_code_from_prompt(prompt)  # Returns str | None
```

## Embedding Schema

The fixture graph stores embeddings with the following schema:

### CodeNode Embedding Fields

```python
@dataclass(frozen=True)
class CodeNode:
    # ... other fields ...

    # Raw content embedding (code or documentation)
    embedding: tuple[tuple[float, ...], ...] | None
    embedding_hash: str | None  # Matches content_hash when fresh

    # AI description embedding
    smart_content_embedding: tuple[tuple[float, ...], ...] | None
```

### Embedding Format

- **Type**: `tuple[tuple[float, ...], ...]` (tuple of tuples)
- **Dimensions**: 1024 (Azure text-embedding-3-small) or 1536 (text-embedding-ada-002)
- **Multi-chunk**: Long content produces multiple vectors (one per chunk)
- **Single chunk example**: `((0.1, 0.2, ..., 0.1),)` - outer tuple with one inner tuple
- **Multi-chunk example**: `((0.1, ...), (0.2, ...), (0.3, ...))` - 3 chunks

### Graph Metadata

The graph stores embedding configuration metadata:

```python
{
    "embedding_model": "text-embedding-3-small",  # or deployment name
    "embedding_dimensions": 1024,
    "chunk_params": {
        "code": {"max_tokens": 400, "overlap_tokens": 50},
        "documentation": {"max_tokens": 800, "overlap_tokens": 120},
        "smart_content": {"max_tokens": 8000, "overlap_tokens": 0},
    },
}
```

### FakeEmbeddingAdapter Behavior

| Content Type | Behavior |
|-------------|----------|
| Known content (in fixture) | Returns real Azure embedding |
| Unknown content | Returns deterministic fallback based on content hash |
| Empty content | Skipped (no embedding) |

Deterministic fallback ensures test reproducibility without API calls.

## pytest Fixtures (conftest.py)

The following pytest fixtures are available:

```python
# Session-scoped: Loads fixture_graph.pkl once
@pytest.fixture(scope="session")
def _fixture_graph_session():
    ...

# Function-scoped: Provides FixtureGraphContext with reset adapters
@pytest.fixture
def fixture_graph(_fixture_graph_session):
    """Returns FixtureGraphContext with fixture_index, embedding_adapter, llm_adapter"""
    ...

# Individual adapters (reset before each test)
@pytest.fixture
def fixture_index(fixture_graph):
    return fixture_graph.fixture_index

@pytest.fixture
def fake_embedding_adapter(fixture_graph):
    return fixture_graph.embedding_adapter

@pytest.fixture
def fake_llm_adapter(fixture_graph):
    return fixture_graph.llm_adapter
```

### Usage Example

```python
@pytest.mark.integration
class TestEmbeddingPipeline:
    def test_known_content_returns_real_embedding(self, fixture_graph):
        """Test using fixture graph adapters."""
        adapter = fixture_graph.embedding_adapter

        # Known content from samples/python/auth_handler.py
        content = 'def is_expired(self) -> bool: ...'

        embedding = await adapter.embed_text(content)

        # Real Azure embedding (1024 dimensions)
        assert len(embedding) == 1024
```

## Maintaining Fixtures

When to regenerate:
- Adding new sample files to `samples/`
- Changing fixture file content
- After major code changes that affect hash computation

Regeneration is idempotent and safe to run anytime.

### Regeneration Command

```bash
# Full regeneration with Azure credentials
just generate-fixtures

# Or manually:
UV_CACHE_DIR=.uv_cache uv run python scripts/generate_fixtures.py
```

### CI Considerations (DYK-2)

**IMPORTANT**: CI tests MUST use fake adapters, not real API calls.

- `FakeEmbeddingAdapter` - Returns fixture embeddings or deterministic fallback
- `FakeLLMAdapter` - Returns fixture smart_content or placeholder
- No Azure/OpenAI credentials required in CI
- Tests are reproducible and fast
