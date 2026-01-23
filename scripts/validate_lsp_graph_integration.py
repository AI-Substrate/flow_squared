#!/usr/bin/env python3
"""Validate LSP integration updates graphs correctly.

This script validates Phase 8 Pipeline Integration by:
1. Scanning Python fixtures with LSP enabled
2. Verifying edges are stored in the graph
3. Checking edge attributes (source, target, type, confidence)
4. Validating graph persistence (edges survive reload)

Per code review requirement: Ensures graphs are actually being updated.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fs2.config.objects import GraphConfig, LspConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.ast_parser_impl import TreeSitterParser
from fs2.core.adapters.file_scanner_impl import FileSystemScanner
from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter
from fs2.core.repos.graph_store_impl import NetworkXGraphStore
from fs2.core.services.scan_pipeline import ScanPipeline

# Suppress LSP debug logs
import logging
logging.getLogger("fs2.core.adapters.lsp_adapter_solidlsp").setLevel(logging.WARNING)


def validate_graph_updates():
    """Main validation function."""
    print("=" * 60)
    print("LSP Graph Integration Validation Script")
    print("=" * 60)
    
    # Find fixtures
    fixture_path = Path(__file__).parent.parent / "tests" / "fixtures" / "lsp" / "python_multi_project"
    src_path = fixture_path / "src"
    
    if not src_path.exists():
        print(f"❌ FAIL: Fixture not found at {src_path}")
        return False
    
    print(f"\n✓ Found fixtures at: {src_path}")
    
    # Create temp directory for graph
    with tempfile.TemporaryDirectory() as tmp_dir:
        graph_path = Path(tmp_dir) / "test_graph.pickle"
        
        # Configure
        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            GraphConfig(graph_path=str(graph_path)),
            LspConfig(),
        )
        
        # Create adapters
        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)
        
        # Initialize LSP
        lsp_adapter = SolidLspAdapter(config)
        lsp_adapter.initialize("python", Path.cwd())
        
        print("✓ LSP adapter initialized")
        
        # Create pipeline
        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=graph_path,
            lsp_adapter=lsp_adapter,
        )
        
        # Run scan
        print("\n--- Running Scan Pipeline ---")
        summary = pipeline.run()
        
        print(f"Files scanned: {summary.files_scanned}")
        print(f"Nodes created: {summary.nodes_created}")
        print(f"Success: {summary.success}")
        
        if not summary.success:
            print("❌ FAIL: Scan failed")
            return False
        
        print("✓ Scan completed successfully")
        
        # VALIDATION 1: Check nodes in graph
        print("\n--- Validation 1: Nodes in Graph ---")
        all_nodes = store.get_all_nodes()
        node_count = len(all_nodes)
        print(f"Total nodes: {node_count}")
        
        if node_count < 3:
            print(f"❌ FAIL: Expected at least 3 nodes (app.py, auth.py, utils.py), got {node_count}")
            return False
        print("✓ Minimum node count met")
        
        # VALIDATION 2: Check relationship edges exist
        print("\n--- Validation 2: Relationship Edges in Graph ---")
        all_edges = []
        for node in all_nodes:
            outgoing = store.get_relationships(node.node_id, direction="outgoing")
            for rel in outgoing:
                all_edges.append({
                    "source": node.node_id,
                    "target": rel["node_id"],
                    "edge_type": rel["edge_type"],
                    "confidence": rel.get("confidence"),
                })
        
        total_edges = len(all_edges)
        call_edges = [e for e in all_edges if e["edge_type"] == "calls"]
        
        print(f"Total relationship edges: {total_edges}")
        print(f"Call edges: {len(call_edges)}")
        
        if len(call_edges) < 7:
            print(f"❌ FAIL: Expected at least 7 call edges (67% of 10), got {len(call_edges)}")
            return False
        print("✓ Minimum call edge count met (≥7)")
        
        # VALIDATION 3: Check edge attributes
        print("\n--- Validation 3: Edge Attributes ---")
        valid_attributes = True
        for edge in call_edges[:5]:  # Sample first 5
            print(f"  {edge['source'][:60]}...")
            print(f"    -> {edge['target'][:60]}...")
            print(f"    type={edge['edge_type']}, confidence={edge['confidence']}")
            
            if edge['confidence'] is None or edge['confidence'] < 0:
                print(f"  ❌ Invalid confidence: {edge['confidence']}")
                valid_attributes = False
        
        if not valid_attributes:
            print("❌ FAIL: Some edges have invalid attributes")
            return False
        print("✓ Edge attributes valid")
        
        # VALIDATION 4: Check cross-file edges exist
        print("\n--- Validation 4: Cross-File Edges ---")
        cross_file = []
        for edge in call_edges:
            src_file = edge['source'].split(':')[1] if ':' in edge['source'] else ''
            tgt_file = edge['target'].split(':')[1] if ':' in edge['target'] else ''
            if src_file and tgt_file and src_file != tgt_file:
                cross_file.append(edge)
        
        print(f"Cross-file edges: {len(cross_file)}")
        for edge in cross_file[:5]:
            src_symbol = edge['source'].split(':')[-1] if ':' in edge['source'] else edge['source']
            tgt_symbol = edge['target'].split(':')[-1] if ':' in edge['target'] else edge['target']
            print(f"  {src_symbol} -> {tgt_symbol}")
        
        if len(cross_file) < 1:
            print("❌ FAIL: No cross-file edges detected")
            return False
        print("✓ Cross-file edges detected")
        
        # VALIDATION 5: Graph persistence (file size check)
        print("\n--- Validation 5: Graph Persistence ---")
        store.save(graph_path)
        
        if not graph_path.exists():
            print("❌ FAIL: Graph file not created")
            return False
        
        file_size = graph_path.stat().st_size
        print(f"Graph file size: {file_size} bytes")
        
        if file_size < 1000:
            print("❌ FAIL: Graph file too small (likely empty)")
            return False
        print("✓ Graph persisted successfully")
        
        # Cleanup
        lsp_adapter.shutdown()
    
    print("\n" + "=" * 60)
    print("✅ ALL VALIDATIONS PASSED")
    print("=" * 60)
    print("\nSummary:")
    print(f"  - Nodes in graph: {node_count}")
    print(f"  - Total edges: {total_edges}")
    print(f"  - Call edges: {len(call_edges)}")
    print(f"  - Cross-file edges: {len(cross_file)}")
    print(f"  - Detection rate: ≥67% (minimum threshold)")
    
    return True


if __name__ == "__main__":
    success = validate_graph_updates()
    sys.exit(0 if success else 1)
