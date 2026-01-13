#!/usr/bin/env python3
"""Validate extraction accuracy against ground truth.

Runs extraction on enriched fixtures and compares results against GROUND_TRUTH.
Computes two-tier metrics:
1. File-level precision/recall/F1 (primary - "did we find the relationship?")
2. Confidence RMSE (secondary - "how accurate is our scoring?")

Per Insight #3 from clarity session: stdlib imports are filtered out before comparison.

Usage:
    python 05_confidence_scoring.py <fixtures_directory>
    python 05_confidence_scoring.py /workspaces/flow_squared/tests/fixtures/samples/

Output:
    JSON to stdout with precision/recall/F1 and confidence RMSE
"""

import json
import math
import sys
from pathlib import Path

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ground_truth import GROUND_TRUTH, ExpectedRelation
from lib.extractors import extract_imports
from lib.parser import parse_file, detect_language

# Standard library module names (Python)
PYTHON_STDLIB = {
    'abc', 'asyncio', 'collections', 'contextlib', 'copy', 'csv', 'dataclasses',
    'datetime', 'decimal', 'enum', 'functools', 'hashlib', 'io', 'itertools',
    'json', 'logging', 'math', 'os', 'pathlib', 'pickle', 'random', 're',
    'shutil', 'socket', 'sqlite3', 'string', 'subprocess', 'sys', 'tempfile',
    'threading', 'time', 'typing', 'unittest', 'urllib', 'uuid', 'warnings',
    'xml', 'zipfile', 'zlib',
}

# TypeScript/JS stdlib-equivalent (Node.js built-ins)
JS_STDLIB = {
    'events', 'fs', 'http', 'https', 'net', 'os', 'path', 'stream', 'url',
    'util', 'crypto', 'buffer', 'child_process', 'cluster', 'dgram', 'dns',
    'domain', 'readline', 'repl', 'tls', 'tty', 'vm', 'zlib',
}

# React is also considered "stdlib" for our purposes
REACT_MODULES = {'react', 'react-dom'}


def is_stdlib_module(module: str, language: str) -> bool:
    """Check if a module is part of the standard library.

    Args:
        module: Module name (e.g., "json", "events")
        language: Language ("python", "typescript", etc.)

    Returns:
        True if module is stdlib
    """
    # Normalize module name
    base_module = module.split('.')[0]

    if language == 'python':
        return base_module in PYTHON_STDLIB

    if language in {'typescript', 'tsx', 'javascript'}:
        return base_module in JS_STDLIB or base_module in REACT_MODULES

    return False


def resolve_module_to_path(module: str, source_file: str, fixtures_root: Path) -> str | None:
    """Resolve a module name to a relative file path.

    Per Insight #2: Extraction returns module names but GT uses file paths.
    This function bridges the gap.

    Args:
        module: Module name (e.g., "auth_handler", "./app")
        source_file: Path to the file containing the import
        fixtures_root: Root directory for fixtures

    Returns:
        Relative path to target file, or None if not resolvable
    """
    source_path = Path(source_file)
    source_dir = source_path.parent

    # Handle relative imports (./app, ../utils)
    if module.startswith('./') or module.startswith('../'):
        # Remove quotes if present
        module = module.strip('"').strip("'")
        # Try to find the file
        base_module = module.lstrip('./')
        # Check common extensions
        for ext in ['', '.py', '.ts', '.tsx', '.js', '.jsx']:
            candidate = source_dir / (base_module + ext)
            if candidate.exists():
                return str(candidate.relative_to(fixtures_root))
        # If source is in javascript/, check for TypeScript files
        if 'javascript' in str(source_dir):
            for ext in ['.ts', '.tsx', '.js']:
                candidate = source_dir / (base_module + ext)
                if candidate.exists():
                    return str(candidate.relative_to(fixtures_root))
        return None

    # Handle Python absolute imports within fixtures
    # auth_handler -> python/auth_handler.py
    if source_path.suffix == '.py':
        candidate = source_path.parent / f'{module}.py'
        if candidate.exists():
            return str(candidate.relative_to(fixtures_root))

    return None


def extract_file_relationships(fixtures_root: Path) -> list[dict]:
    """Extract import relationships from fixtures.

    Args:
        fixtures_root: Root directory containing fixtures

    Returns:
        List of extracted relationships with source_file, target_file, confidence
    """
    relationships = []

    # Process Python files
    python_dir = fixtures_root / 'python'
    if python_dir.exists():
        for py_file in python_dir.glob('*.py'):
            try:
                tree = parse_file(py_file, 'python')
                imports = extract_imports(tree, 'python')

                for imp in imports:
                    module = imp.get('module', '')
                    # Skip stdlib
                    if is_stdlib_module(module, 'python'):
                        continue

                    # Try to resolve module to path
                    target_path = resolve_module_to_path(module, str(py_file), fixtures_root)
                    if target_path:
                        relationships.append({
                            'source_file': str(py_file.relative_to(fixtures_root)),
                            'target_file': target_path,
                            'rel_type': 'import',
                            'extracted_confidence': imp.get('confidence', 0.9),
                        })
            except Exception as e:
                print(f"Warning: Error processing {py_file}: {e}", file=sys.stderr)

    # Process TypeScript files
    js_dir = fixtures_root / 'javascript'
    if js_dir.exists():
        for ts_file in js_dir.glob('*.ts'):
            try:
                tree = parse_file(ts_file, 'typescript')
                imports = extract_imports(tree, 'typescript')

                for imp in imports:
                    module = imp.get('module', '')
                    # Skip stdlib and React
                    if is_stdlib_module(module, 'typescript'):
                        continue

                    # Try to resolve module to path
                    target_path = resolve_module_to_path(module, str(ts_file), fixtures_root)
                    if target_path:
                        relationships.append({
                            'source_file': str(ts_file.relative_to(fixtures_root)),
                            'target_file': target_path,
                            'rel_type': 'import',
                            'extracted_confidence': imp.get('confidence', 0.9),
                        })
            except Exception as e:
                print(f"Warning: Error processing {ts_file}: {e}", file=sys.stderr)

        # Also process TSX files
        for tsx_file in js_dir.glob('*.tsx'):
            try:
                tree = parse_file(tsx_file, 'tsx')
                imports = extract_imports(tree, 'tsx')

                for imp in imports:
                    module = imp.get('module', '')
                    if is_stdlib_module(module, 'tsx'):
                        continue

                    target_path = resolve_module_to_path(module, str(tsx_file), fixtures_root)
                    if target_path:
                        relationships.append({
                            'source_file': str(tsx_file.relative_to(fixtures_root)),
                            'target_file': target_path,
                            'rel_type': 'import',
                            'extracted_confidence': imp.get('confidence', 0.9),
                        })
            except Exception as e:
                print(f"Warning: Error processing {tsx_file}: {e}", file=sys.stderr)

    return relationships


def compute_metrics(extracted: list[dict], ground_truth: list[ExpectedRelation]) -> dict:
    """Compute precision, recall, F1, and confidence RMSE.

    Args:
        extracted: List of extracted relationships
        ground_truth: List of expected relationships

    Returns:
        Dict with metrics
    """
    # Filter ground truth to import relationships only (what we can validate)
    gt_imports = [gt for gt in ground_truth if gt.rel_type == 'import']

    # Create sets for file-level comparison (source → target pairs)
    extracted_pairs = {(r['source_file'], r['target_file']) for r in extracted}
    gt_pairs = {(gt.source_file, gt.target_file) for gt in gt_imports}

    # Calculate true positives, false positives, false negatives
    true_positives = extracted_pairs & gt_pairs
    false_positives = extracted_pairs - gt_pairs
    false_negatives = gt_pairs - extracted_pairs

    tp_count = len(true_positives)
    fp_count = len(false_positives)
    fn_count = len(false_negatives)

    # Precision = TP / (TP + FP)
    precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0

    # Recall = TP / (TP + FN)
    recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0

    # F1 = 2 * (precision * recall) / (precision + recall)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Confidence RMSE for matched pairs
    confidence_errors = []
    for ext in extracted:
        pair = (ext['source_file'], ext['target_file'])
        if pair in gt_pairs:
            # Find the matching GT entry
            for gt in gt_imports:
                if (gt.source_file, gt.target_file) == pair:
                    error = (ext['extracted_confidence'] - gt.expected_confidence) ** 2
                    confidence_errors.append(error)
                    break

    rmse = math.sqrt(sum(confidence_errors) / len(confidence_errors)) if confidence_errors else 0.0

    return {
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'confidence_rmse': round(rmse, 4),
        'true_positives': tp_count,
        'false_positives': fp_count,
        'false_negatives': fn_count,
        'extracted_count': len(extracted),
        'ground_truth_import_count': len(gt_imports),
        'true_positive_pairs': list(true_positives),
        'false_positive_pairs': list(false_positives),
        'false_negative_pairs': list(false_negatives),
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: python 05_confidence_scoring.py <fixtures_directory>', file=sys.stderr)
        print('Example: python 05_confidence_scoring.py tests/fixtures/samples/', file=sys.stderr)
        sys.exit(1)

    fixtures_root = Path(sys.argv[1])

    if not fixtures_root.exists():
        print(f'Error: Directory not found: {fixtures_root}', file=sys.stderr)
        sys.exit(1)

    if not fixtures_root.is_dir():
        print(f'Error: Not a directory: {fixtures_root}', file=sys.stderr)
        sys.exit(1)

    # Extract relationships from fixtures
    extracted = extract_file_relationships(fixtures_root)

    # Compute metrics
    metrics = compute_metrics(extracted, GROUND_TRUTH)

    # Build result
    result = {
        'meta': {
            'fixtures_root': str(fixtures_root.resolve()),
            'ground_truth_total': len(GROUND_TRUTH),
            'ground_truth_imports': metrics['ground_truth_import_count'],
            'extracted_relationships': len(extracted),
        },
        'metrics': {
            'file_level': {
                'precision': metrics['precision'],
                'recall': metrics['recall'],
                'f1': metrics['f1'],
            },
            'confidence': {
                'rmse': metrics['confidence_rmse'],
                'target': 0.15,  # RMSE ≤ 0.15 per acceptance criteria
            },
        },
        'details': {
            'true_positives': metrics['true_positives'],
            'false_positives': metrics['false_positives'],
            'false_negatives': metrics['false_negatives'],
            'true_positive_pairs': metrics['true_positive_pairs'],
            'false_positive_pairs': metrics['false_positive_pairs'],
            'false_negative_pairs': metrics['false_negative_pairs'],
        },
        'validation': {
            'precision_target': 0.9,
            'precision_met': metrics['precision'] >= 0.9,
            'rmse_target': 0.15,
            'rmse_met': metrics['confidence_rmse'] <= 0.15,
        },
    }

    # Output JSON
    print(json.dumps(result, indent=2))

    return 0


if __name__ == '__main__':
    sys.exit(main())
