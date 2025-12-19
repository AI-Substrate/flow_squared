"""Integration tests for ScanPipeline with real adapters.

Purpose: Verifies end-to-end pipeline with FileSystemScanner, TreeSitterParser,
         and NetworkXGraphStore.
Quality Contribution: Ensures all components work together correctly.

Per Phase 5 Tasks:
- T021: Full pipeline with real adapters
- T022: AC1 config loading verification
- T023: AC5 hierarchy verification
- T024: AC7 node ID format verification
- T025: AC8 persistence verification
- T026: AC10 error handling verification
"""

import pytest
from pathlib import Path

from fs2.config.objects import ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.file_scanner_impl import FileSystemScanner
from fs2.core.adapters.ast_parser_impl import TreeSitterParser
from fs2.core.repos.graph_store_impl import NetworkXGraphStore
from fs2.core.services.scan_pipeline import ScanPipeline


@pytest.fixture
def simple_python_project(tmp_path: Path) -> Path:
    """Create a simple Python project structure for testing."""
    src = tmp_path / "src"
    src.mkdir()

    # Main module with class and methods
    calculator = src / "calculator.py"
    calculator.write_text('''"""Calculator module."""


class Calculator:
    """A basic calculator class."""

    def __init__(self, value: int = 0):
        self.value = value

    def add(self, x: int) -> int:
        """Add x to current value."""
        self.value += x
        return self.value

    def subtract(self, x: int) -> int:
        """Subtract x from current value."""
        self.value -= x
        return self.value
''')

    # Utils module with standalone function
    utils = src / "utils.py"
    utils.write_text('''"""Utility functions."""


def format_number(n: int) -> str:
    """Format a number with commas."""
    return f"{n:,}"
''')

    return tmp_path


@pytest.fixture
def config_service_for(tmp_path: Path):
    """Factory for creating config service with specific scan paths."""
    def _create(scan_paths: list[str]) -> FakeConfigurationService:
        return FakeConfigurationService(
            ScanConfig(scan_paths=scan_paths, respect_gitignore=True)
        )
    return _create


class TestFullPipelineWithRealAdapters:
    """T021: Integration tests with real adapters."""

    def test_given_real_adapters_when_scanning_then_produces_summary(
        self, simple_python_project: Path, config_service_for
    ):
        """
        Purpose: Verifies full pipeline works with real adapters.
        Quality Contribution: End-to-end validation.
        Acceptance Criteria: ScanSummary returned with correct counts.
        """
        config = config_service_for([str(simple_python_project / "src")])

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
        )

        summary = pipeline.run()

        assert summary.success is True
        assert summary.files_scanned == 2  # calculator.py, utils.py
        assert summary.nodes_created > 0
        assert summary.errors == []


class TestConfigLoadingAC1:
    """T022: AC1 - Config loading from context."""

    def test_given_scan_config_when_running_then_uses_scan_paths(
        self, simple_python_project: Path, config_service_for
    ):
        """
        Purpose: Verifies AC1 - config is used correctly.
        Quality Contribution: Ensures config drives behavior.
        Acceptance Criteria: Only configured paths are scanned.
        """
        # Only scan the src directory, not root
        config = config_service_for([str(simple_python_project / "src")])

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
        )

        summary = pipeline.run()

        # Should only find files in src/
        assert summary.files_scanned == 2


class TestHierarchyAC5:
    """T023: AC5 - File → Class → Method hierarchy."""

    def test_given_python_class_when_scanned_then_hierarchy_extracted(
        self, simple_python_project: Path, config_service_for, tmp_path: Path
    ):
        """
        Purpose: Verifies AC5 - hierarchy is correctly extracted.
        Quality Contribution: Ensures graph structure is correct.
        Acceptance Criteria: File → Class → Method edges exist.
        """
        config = config_service_for([str(simple_python_project / "src")])

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
        )

        summary = pipeline.run()

        # Verify hierarchy exists
        # Find the Calculator class node
        class_nodes = [n for n in store.get_all_nodes() if n.category == "type" and n.name == "Calculator"]
        assert len(class_nodes) == 1

        class_node = class_nodes[0]

        # Calculator should have methods as children
        children = store.get_children(class_node.node_id)
        method_names = {n.name for n in children}
        assert "__init__" in method_names
        assert "add" in method_names
        assert "subtract" in method_names


class TestNodeIDFormatAC7:
    """T024: AC7 - Node ID format verification."""

    def test_given_nodes_when_scanned_then_ids_follow_format(
        self, simple_python_project: Path, config_service_for
    ):
        """
        Purpose: Verifies AC7 - node IDs follow {category}:{path}:{symbol} format.
        Quality Contribution: Ensures consistent ID scheme.
        Acceptance Criteria: All node IDs match expected format.
        """
        config = config_service_for([str(simple_python_project / "src")])

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
        )

        pipeline.run()

        nodes = store.get_all_nodes()

        for node in nodes:
            # File nodes: file:{path}
            if node.category == "file":
                assert node.node_id.startswith("file:")
                assert ".py" in node.node_id

            # Type nodes: type:{path}:{qualified_name}
            elif node.category == "type":
                assert node.node_id.startswith("type:")
                parts = node.node_id.split(":")
                assert len(parts) >= 3

            # Callable nodes: callable:{path}:{qualified_name}
            elif node.category == "callable":
                assert node.node_id.startswith("callable:")
                parts = node.node_id.split(":")
                assert len(parts) >= 3


class TestPersistenceAC8:
    """T025: AC8 - Graph persistence and recovery."""

    def test_given_scan_complete_when_loaded_then_all_nodes_recovered(
        self, simple_python_project: Path, config_service_for, tmp_path: Path
    ):
        """
        Purpose: Verifies AC8 - graph can be saved and loaded.
        Quality Contribution: Ensures data durability.
        Acceptance Criteria: All nodes recoverable after save/load.
        """
        graph_path = tmp_path / "test_graph.pickle"
        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(simple_python_project / "src")])
        )

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        # First, run pipeline and save
        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
        )

        summary = pipeline.run()
        original_node_count = summary.nodes_created

        # Force save to specific path (StorageStage already saved to default)
        store.save(graph_path)

        # Create new store and load
        new_store = NetworkXGraphStore(config)
        new_store.load(graph_path)

        # Verify all nodes recovered
        recovered_nodes = new_store.get_all_nodes()
        assert len(recovered_nodes) == original_node_count


class TestErrorHandlingAC10:
    """T026: AC10 - Graceful error handling."""

    def test_given_binary_file_when_scanning_then_continues_without_crash(
        self, simple_python_project: Path, config_service_for
    ):
        """
        Purpose: Verifies AC10 - binary files don't crash the pipeline.
        Quality Contribution: Ensures robustness.
        Acceptance Criteria: Pipeline completes, binary skipped.
        """
        # Add a binary file
        binary_file = simple_python_project / "src" / "sample.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")

        config = config_service_for([str(simple_python_project / "src")])

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
        )

        summary = pipeline.run()

        # Should complete despite binary file
        assert summary.files_scanned >= 2  # At least calculator.py, utils.py
        # Binary file is scanned but produces no nodes (empty result)
        # This is success - pipeline didn't crash

    def test_given_parse_error_when_scanning_then_other_files_processed(
        self, simple_python_project: Path, config_service_for
    ):
        """
        Purpose: Verifies parse errors don't stop other files.
        Quality Contribution: Ensures partial success is possible.
        Acceptance Criteria: Good files still processed.
        """
        # Add a file with syntax error
        bad_file = simple_python_project / "src" / "broken.py"
        bad_file.write_text("def broken(\n    # Missing close paren")

        config = config_service_for([str(simple_python_project / "src")])

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
        )

        summary = pipeline.run()

        # Still should have nodes from good files
        assert summary.nodes_created > 0

        # Should have Calculator class
        nodes = store.get_all_nodes()
        class_names = [n.name for n in nodes if n.category == "type"]
        assert "Calculator" in class_names


class TestGitignoreIntegration:
    """Additional tests for gitignore handling in integration."""

    def test_given_gitignore_when_scanning_then_respects_patterns(
        self, simple_python_project: Path, config_service_for
    ):
        """
        Purpose: Verifies gitignore patterns are respected.
        Quality Contribution: Ensures only relevant files scanned.
        Acceptance Criteria: Ignored files not in results.
        """
        # Create gitignore
        gitignore = simple_python_project / ".gitignore"
        gitignore.write_text("*.log\n__pycache__/\n")

        # Create files that should be ignored
        log_file = simple_python_project / "src" / "debug.log"
        log_file.write_text("debug info")

        pycache = simple_python_project / "src" / "__pycache__"
        pycache.mkdir()
        cache_file = pycache / "calculator.cpython-312.pyc"
        cache_file.write_bytes(b"fake bytecode")

        config = config_service_for([str(simple_python_project / "src")])

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
        )

        summary = pipeline.run()

        # Should only have Python files, not log or cache
        file_nodes = [n for n in store.get_all_nodes() if n.category == "file"]
        file_names = [n.name for n in file_nodes]

        assert "calculator.py" in file_names
        assert "utils.py" in file_names
        assert "debug.log" not in file_names
        assert "calculator.cpython-312.pyc" not in file_names


# ===========================================================================
# T009: Smart Content Integration Tests (Phase 6)
# ===========================================================================


class TestSmartContentIntegration:
    """T009: Integration tests for smart content pipeline metrics.

    Per Phase 6 Tasks:
    - Verifies SmartContentService.process_batch() is called
    - Verifies metrics (enriched, preserved, errors) are recorded
    - Verifies hash-based preservation works

    NOTE: Due to NetworkXGraphStore module-level state, these tests verify
    metrics rather than inspecting store.get_all_nodes() which may include
    stale data from prior test runs.
    """

    def test_given_smart_content_service_when_scanning_then_metrics_recorded(
        self, tmp_path: Path
    ):
        """
        Purpose: Verifies pipeline records smart content metrics.
        Quality Contribution: End-to-end metric validation.
        Acceptance Criteria: smart_content_enriched > 0, errors == 0.

        Why: Metrics prove SmartContentService was called and succeeded.
        Contract: scan with service → metrics show enrichment count.
        """
        from fs2.config.objects import SmartContentConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
        from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
        from fs2.core.services.llm_service import LLMService
        from fs2.core.services.smart_content.smart_content_service import (
            SmartContentService,
        )
        from fs2.core.services.smart_content.template_service import TemplateService

        # Create isolated project
        src = tmp_path / "src"
        src.mkdir()
        (src / "calc.py").write_text("def add(a, b):\n    '''Add two numbers together and return the result.'''\n    return a + b")
        (src / "utils.py").write_text("def helper():\n    '''A helper function that performs utility operations.'''\n    pass")

        # Create config
        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src)], respect_gitignore=True),
            SmartContentConfig(max_workers=2),
        )

        # Create fake LLM adapter
        llm_adapter = FakeLLMAdapter()
        llm_adapter.set_response("Test summary.")

        # Build SmartContentService
        llm_service = LLMService(config, llm_adapter)
        template_service = TemplateService(config)
        token_counter = FakeTokenCounterAdapter(config)
        smart_service = SmartContentService(
            config=config,
            llm_service=llm_service,
            template_service=template_service,
            token_counter=token_counter,
        )

        # Create adapters and pipeline
        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            smart_content_service=smart_service,
        )

        summary = pipeline.run()

        # Verify success and metrics
        assert summary.success is True
        assert summary.files_scanned == 2
        assert summary.metrics.get("smart_content_enriched", 0) > 0, \
            "Expected smart_content_enriched > 0"
        assert summary.metrics.get("smart_content_errors", 0) == 0, \
            "Expected smart_content_errors == 0"

        # Verify LLM was actually called
        assert len(llm_adapter.call_history) > 0, "Expected LLM to be called"

    def test_given_second_scan_when_files_unchanged_then_preservation_metrics(
        self, tmp_path: Path
    ):
        """
        Purpose: Verifies hash-based preservation works via metrics.
        Quality Contribution: Cost optimization validation.
        Acceptance Criteria: Second scan shows preserved > 0.

        Why: Hash-based skip is critical for cost control.
        Contract: Unchanged files → preserved metric increases.
        """
        from fs2.config.objects import SmartContentConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
        from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
        from fs2.core.services.llm_service import LLMService
        from fs2.core.services.smart_content.smart_content_service import (
            SmartContentService,
        )
        from fs2.core.services.smart_content.template_service import TemplateService

        # Create isolated project
        src = tmp_path / "src"
        src.mkdir()
        (src / "stable.py").write_text("def stable():\n    '''A stable function that does not change between scans.'''\n    return True")

        graph_path = tmp_path / "graph.pickle"

        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src)]),
            SmartContentConfig(max_workers=2),
        )

        llm_adapter = FakeLLMAdapter()
        llm_adapter.set_response("First scan summary.")

        llm_service = LLMService(config, llm_adapter)
        template_service = TemplateService(config)
        token_counter = FakeTokenCounterAdapter(config)
        smart_service = SmartContentService(
            config=config,
            llm_service=llm_service,
            template_service=template_service,
            token_counter=token_counter,
        )

        # First scan
        store1 = NetworkXGraphStore(config)
        pipeline1 = ScanPipeline(
            config=config,
            file_scanner=FileSystemScanner(config),
            ast_parser=TreeSitterParser(config),
            graph_store=store1,
            smart_content_service=smart_service,
        )

        summary1 = pipeline1.run()
        first_call_count = len(llm_adapter.call_history)

        # Save graph
        store1.save(graph_path)

        # Reset LLM adapter
        llm_adapter.reset()
        llm_adapter.set_response("Second scan - should not see.")

        # Second scan with loaded graph
        store2 = NetworkXGraphStore(config)
        store2.load(graph_path)

        pipeline2 = ScanPipeline(
            config=config,
            file_scanner=FileSystemScanner(config),
            ast_parser=TreeSitterParser(config),
            graph_store=store2,
            smart_content_service=smart_service,
        )

        summary2 = pipeline2.run()
        second_call_count = len(llm_adapter.call_history)

        # Verify preservation metrics
        assert summary2.metrics.get("smart_content_preserved", 0) > 0, \
            "Expected preservation on second scan"
        # Fewer LLM calls on second scan
        assert second_call_count < first_call_count, \
            f"Expected fewer LLM calls on second scan ({second_call_count} vs {first_call_count})"

    def test_given_no_smart_service_when_scanning_then_zero_metrics(
        self, tmp_path: Path
    ):
        """
        Purpose: Verifies metrics are zero when no service configured.
        Quality Contribution: --no-smart-content mode validation.
        Acceptance Criteria: enriched=0, preserved=0, errors=0.

        Why: No service means no smart content processing.
        Contract: smart_content_service=None → all metrics 0.
        """
        from fs2.config.service import FakeConfigurationService

        # Create fresh project
        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text('def hello(): return "world"')

        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src)], respect_gitignore=True)
        )

        pipeline = ScanPipeline(
            config=config,
            file_scanner=FileSystemScanner(config),
            ast_parser=TreeSitterParser(config),
            graph_store=NetworkXGraphStore(config),
            smart_content_service=None,
        )

        summary = pipeline.run()

        # Verify success
        assert summary.success is True
        assert summary.files_scanned == 1
        assert summary.nodes_created > 0

        # Verify zero smart content metrics
        assert summary.metrics.get("smart_content_enriched", 0) == 0
        assert summary.metrics.get("smart_content_preserved", 0) == 0
        assert summary.metrics.get("smart_content_errors", 0) == 0
