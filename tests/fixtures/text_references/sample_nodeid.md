# Sample Node ID Test File

This file contains fs2 node_id patterns for testing regex extraction.
Created per didyouknow insight #4 to validate regex works before running on fixtures.

## Example References

Here are some inline node_id references:

1. The `file:src/lib/parser.py` module handles parsing
2. The main class is `class:src/lib/parser.py:Parser`
3. For language detection, see `method:src/lib/parser.py:Parser.detect_language`
4. The resolver is at `callable:src/lib/resolver.py:calculate_confidence`
5. Check `type:src/models/types.py:ImportInfo` for type definitions

## Cross-File Relationships

The `class:src/extractors.py:ImportExtractor` uses:
- `method:src/parser.py:Parser.parse_file` for parsing
- `callable:src/resolver.py:import_confidence` for scoring

See also: `file:docs/plans/022-cross-file-rels/tasks.md`

## Edge Cases

1. Nested paths: `class:src/fs2/core/adapters/log_adapter.py:LogAdapter`
2. Deep nesting: `method:src/fs2/core/repos/graph_store_impl.py:NetworkXGraphStore.save`

## Non-Matches (should NOT be captured)

These should not match:
- Regular text with colons: key:value
- URLs: https://example.com
- Time: 10:30:45
- File paths without prefix: src/lib/parser.py
