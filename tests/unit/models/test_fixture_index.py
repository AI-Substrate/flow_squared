"""Tests for FixtureIndex model.

FixtureIndex provides O(1) lookup of embeddings and smart_content by content_hash.
Used by FakeEmbeddingAdapter and FakeLLMAdapter for fixture-backed testing.

Per DYK-1: FakeLLMAdapter needs extract_code_from_prompt() helper.
Per DYK-2: Embeddings are tuple[tuple[float, ...], ...], adapter converts to list[float].
"""

import pytest

from fs2.core.utils.hash import compute_content_hash


class TestFixtureIndexFromGraphStore:
    """Tests for FixtureIndex.from_graph_store() factory method.

    Purpose: Validates FixtureIndex correctly builds lookup indexes from GraphStore.
    Quality Contribution: Ensures O(1) lookup is available after initialization.
    Acceptance Criteria: All nodes with content_hash are indexed.
    """

    def test_from_graph_store_builds_index(self):
        """Index contains all nodes from the graph store."""
        from fs2.core.models.fixture_index import FixtureIndex
        from fs2.core.models.code_node import CodeNode

        # Create a mock graph store with nodes
        nodes = [
            CodeNode.create_file(
                file_path="test.py",
                language="python",
                ts_kind="module",
                start_byte=0,
                end_byte=100,
                start_line=1,
                end_line=10,
                content="def hello(): pass",
                smart_content="A simple hello function",
                embedding=((0.1, 0.2, 0.3),),
            ),
            CodeNode.create_callable(
                file_path="test.py",
                language="python",
                ts_kind="function_definition",
                name="hello",
                qualified_name="hello",
                start_line=1,
                end_line=1,
                start_column=0,
                end_column=17,
                start_byte=0,
                end_byte=17,
                content="def hello(): pass",
                signature="def hello():",
                smart_content="Says hello",
                embedding=((0.4, 0.5, 0.6),),
            ),
        ]

        # Create fixture index
        index = FixtureIndex.from_nodes(nodes)

        # Verify both nodes are indexed
        assert index.node_count == 2

    def test_from_graph_store_empty_graph(self):
        """Empty graph produces empty index."""
        from fs2.core.models.fixture_index import FixtureIndex

        index = FixtureIndex.from_nodes([])

        assert index.node_count == 0

    def test_from_graph_store_skips_nodes_without_embeddings(self):
        """Nodes without embeddings are indexed but return None for get_embedding."""
        from fs2.core.models.fixture_index import FixtureIndex
        from fs2.core.models.code_node import CodeNode

        node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="x = 1",
            # No embedding, no smart_content
        )

        index = FixtureIndex.from_nodes([node])

        # Node is indexed (for smart_content lookup)
        assert index.node_count == 1
        # But get_embedding returns None
        content_hash = compute_content_hash("x = 1")
        assert index.get_embedding(content_hash) is None


class TestFixtureIndexGetEmbedding:
    """Tests for FixtureIndex.get_embedding() method.

    Purpose: Validates O(1) embedding lookup by content hash.
    Quality Contribution: Ensures FakeEmbeddingAdapter can find real embeddings.
    Acceptance Criteria: Known hash returns embedding, unknown returns None.
    """

    @pytest.fixture
    def fixture_index(self):
        """Create a fixture index with sample nodes."""
        from fs2.core.models.fixture_index import FixtureIndex
        from fs2.core.models.code_node import CodeNode

        nodes = [
            CodeNode.create_file(
                file_path="test.py",
                language="python",
                ts_kind="module",
                start_byte=0,
                end_byte=100,
                start_line=1,
                end_line=10,
                content="def add(a, b): return a + b",
                smart_content="Adds two numbers",
                embedding=((0.1, 0.2, 0.3, 0.4),),
            ),
        ]
        return FixtureIndex.from_nodes(nodes)

    def test_get_embedding_known_hash(self, fixture_index):
        """Known content hash returns the embedding tuple."""
        content = "def add(a, b): return a + b"
        content_hash = compute_content_hash(content)

        result = fixture_index.get_embedding(content_hash)

        assert result is not None
        assert result == ((0.1, 0.2, 0.3, 0.4),)
        assert isinstance(result, tuple)
        assert isinstance(result[0], tuple)

    def test_get_embedding_unknown_hash(self, fixture_index):
        """Unknown content hash returns None."""
        unknown_hash = compute_content_hash("completely unknown content xyz123")

        result = fixture_index.get_embedding(unknown_hash)

        assert result is None

    def test_get_embedding_returns_tuple_of_tuples(self, fixture_index):
        """Embedding is returned as tuple[tuple[float, ...], ...]."""
        content = "def add(a, b): return a + b"
        content_hash = compute_content_hash(content)

        result = fixture_index.get_embedding(content_hash)

        assert isinstance(result, tuple)
        assert len(result) > 0
        assert isinstance(result[0], tuple)
        assert all(isinstance(x, float) for x in result[0])


class TestFixtureIndexGetSmartContent:
    """Tests for FixtureIndex.get_smart_content() method.

    Purpose: Validates O(1) smart_content lookup by content hash.
    Quality Contribution: Ensures FakeLLMAdapter can find pre-computed responses.
    Acceptance Criteria: Known hash returns smart_content, unknown returns None.
    """

    @pytest.fixture
    def fixture_index(self):
        """Create a fixture index with sample nodes."""
        from fs2.core.models.fixture_index import FixtureIndex
        from fs2.core.models.code_node import CodeNode

        nodes = [
            CodeNode.create_file(
                file_path="test.py",
                language="python",
                ts_kind="module",
                start_byte=0,
                end_byte=100,
                start_line=1,
                end_line=10,
                content="def multiply(x, y): return x * y",
                smart_content="Multiplies two numbers together and returns the result.",
                embedding=((0.5, 0.6),),
            ),
        ]
        return FixtureIndex.from_nodes(nodes)

    def test_get_smart_content_known_hash(self, fixture_index):
        """Known content hash returns the smart_content string."""
        content = "def multiply(x, y): return x * y"
        content_hash = compute_content_hash(content)

        result = fixture_index.get_smart_content(content_hash)

        assert result is not None
        assert result == "Multiplies two numbers together and returns the result."
        assert isinstance(result, str)

    def test_get_smart_content_unknown_hash(self, fixture_index):
        """Unknown content hash returns None."""
        unknown_hash = compute_content_hash("unknown content")

        result = fixture_index.get_smart_content(unknown_hash)

        assert result is None


class TestFixtureIndexExtractCodeFromPrompt:
    """Tests for FixtureIndex.extract_code_from_prompt() helper.

    Per DYK-1: FakeLLMAdapter receives prompts with templates/instructions,
    not raw code. We need to extract the code block from markdown fences
    to compute the content hash for lookup.

    Purpose: Validates extraction of code content from markdown prompts.
    Quality Contribution: Enables smart_content lookup for LLM adapter.
    Acceptance Criteria: Correctly extracts code from various fence formats.
    """

    def test_extract_single_code_block(self):
        """Extracts code from a single markdown code block."""
        from fs2.core.models.fixture_index import FixtureIndex

        prompt = """Please analyze this code:

```python
def add(a, b):
    return a + b
```

Provide a summary of what it does."""

        result = FixtureIndex.extract_code_from_prompt(prompt)

        assert result is not None
        assert result.strip() == "def add(a, b):\n    return a + b"

    def test_extract_code_block_without_language(self):
        """Extracts code from a code block without language specifier."""
        from fs2.core.models.fixture_index import FixtureIndex

        prompt = """Here is the code:

```
x = 1 + 2
```"""

        result = FixtureIndex.extract_code_from_prompt(prompt)

        assert result is not None
        assert result.strip() == "x = 1 + 2"

    def test_extract_first_code_block_when_multiple(self):
        """Returns the first code block when prompt has multiple."""
        from fs2.core.models.fixture_index import FixtureIndex

        prompt = """Compare these functions:

```python
def first():
    pass
```

and

```python
def second():
    pass
```"""

        result = FixtureIndex.extract_code_from_prompt(prompt)

        assert result is not None
        assert "first" in result
        assert "second" not in result

    def test_extract_returns_none_when_no_code_block(self):
        """Returns None when prompt has no code blocks."""
        from fs2.core.models.fixture_index import FixtureIndex

        prompt = "What is the capital of France?"

        result = FixtureIndex.extract_code_from_prompt(prompt)

        assert result is None

    def test_extract_handles_empty_code_block(self):
        """Handles empty code blocks gracefully."""
        from fs2.core.models.fixture_index import FixtureIndex

        prompt = """Empty block:

```python
```"""

        result = FixtureIndex.extract_code_from_prompt(prompt)

        # Empty code block returns empty string or None
        assert result is None or result.strip() == ""


class TestFixtureIndexLookupByContent:
    """Tests for convenience lookup by raw content (not hash).

    Purpose: Provides a simpler API when content is already available.
    Quality Contribution: Reduces boilerplate in adapter implementations.
    """

    @pytest.fixture
    def fixture_index(self):
        """Create a fixture index with sample nodes."""
        from fs2.core.models.fixture_index import FixtureIndex
        from fs2.core.models.code_node import CodeNode

        nodes = [
            CodeNode.create_file(
                file_path="test.py",
                language="python",
                ts_kind="module",
                start_byte=0,
                end_byte=100,
                start_line=1,
                end_line=10,
                content="class Foo:\n    pass",
                smart_content="An empty class named Foo.",
                embedding=((0.7, 0.8, 0.9),),
            ),
        ]
        return FixtureIndex.from_nodes(nodes)

    def test_lookup_embedding_by_content(self, fixture_index):
        """Lookup embedding by raw content (computes hash internally)."""
        content = "class Foo:\n    pass"

        result = fixture_index.lookup_embedding(content)

        assert result is not None
        assert result == ((0.7, 0.8, 0.9),)

    def test_lookup_smart_content_by_content(self, fixture_index):
        """Lookup smart_content by raw content."""
        content = "class Foo:\n    pass"

        result = fixture_index.lookup_smart_content(content)

        assert result == "An empty class named Foo."
