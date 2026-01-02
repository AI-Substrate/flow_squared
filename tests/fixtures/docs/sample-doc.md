# Sample Documentation

This is a sample document for testing the DocsService.

## Purpose

Used in unit tests to verify:
- Document retrieval works correctly
- Metadata is properly populated
- Content loading is accurate

## Usage

```python
doc = docs_service.get_document("sample-doc")
assert doc.content.startswith("# Sample Documentation")
```
