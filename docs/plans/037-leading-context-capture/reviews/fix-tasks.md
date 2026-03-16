# Fix Tasks: Leading Context Capture

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Hash the actual embedding payload
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py`
- **Issue**: `_chunk_content()` embeds `leading_context + "\n" + content`, but `_should_skip()` and final `embedding_hash` assignment hash `content + leading_context`. That mismatch makes `embedding_hash` an unreliable freshness key.
- **Fix**: Extract or reuse one helper that builds the exact raw-embedding payload, use it both when chunking and when computing `expected_hash` / `embedding_hash`, and update the tests to assert against the real payload path through `EmbeddingService`.
- **Patch hint**:
  ```diff
  - if node.leading_context:
  -     expected_hash = compute_content_hash(node.content + node.leading_context)
  + raw_text = "\n".join([node.leading_context, node.content]) if node.leading_context else node.content
  + expected_hash = compute_content_hash(raw_text)
  ...
  - embedding_hash=(compute_content_hash(node.content + node.leading_context) if node.leading_context else node.content_hash)
  + embedding_hash=(compute_content_hash(raw_text) if node.leading_context else node.content_hash)
  ```

### FT-002: Stop overclaiming all-language coverage
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_leading_context.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.fltplan.md`
- **Issue**: The phase claims AC13 is satisfied for all 13 languages, but the committed evidence only covers 8 languages.
- **Fix**: Add parser tests or equivalent concrete fixture-scan evidence for TSX, JavaScript, C++, Ruby, and Bash, then update the plan/log/flight-plan status text to cite the actual artifacts.
- **Patch hint**:
  ```diff
  + class TestTSXLeadingContext:
  +     def test_tsx_comment_capture(self, parser): ...
  +
  + class TestJavaScriptLeadingContext:
  +     def test_js_comment_capture(self, parser): ...
  +
  + class TestCppLeadingContext:
  +     def test_cpp_comment_capture(self, parser): ...
  +
  + class TestRubyLeadingContext:
  +     def test_ruby_comment_capture(self, parser): ...
  +
  + class TestBashLeadingContext:
  +     def test_bash_comment_capture(self, parser): ...
  ```

## Medium / Low Fixes

### FT-003: Add direct AC08 / AC09 evidence
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py`
- **Issue**: The review scope shows code wiring for semantic-search and smart-content changes, but there is no direct verification artifact proving those behaviors.
- **Fix**: Add one deterministic embedding-path test that asserts the chunked text starts with `leading_context`, and add one deterministic smart-content test (context or rendered template) that proves developer comments are present in prompt input.
- **Patch hint**:
  ```diff
  + def test_chunk_content_prepends_leading_context(...):
  +     chunks = service._chunk_content(node, is_smart_content=False)
  +     assert chunks[0].text.startswith("# important comment\n")
  +
  + def test_build_context_includes_leading_context(...):
  +     context = service._build_context(node, node.content)
  +     assert context["leading_context"] == "# important comment"
  ```

### FT-004: Reconcile artifact path drift
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.md`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.fltplan.md`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py`
- **Issue**: Review artifacts expect `tests/unit/services/search/test_leading_context_search.py`, but the committed file is `tests/unit/services/test_leading_context_integration.py`.
- **Fix**: Either move/rename the file to the planned path or update every plan/task artifact so the approved file manifest matches the actual repo change.
- **Patch hint**:
  ```diff
  - | `tests/unit/services/search/test_leading_context_search.py` | tests | internal | Tests for search integration |
  + | `tests/unit/services/test_leading_context_integration.py` | tests | internal | Tests for search / embedding / output integration |
  ```

### FT-005: Make lint evidence reproducible
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md`
- **Issue**: The new integration test file fails Ruff due to import ordering and unused imports, yet the execution log says `Zero ruff violations`.
- **Fix**: Remove unused imports, sort the import block, rerun Ruff, and record the actual lint command/output in the execution log.
- **Patch hint**:
  ```diff
   import regex
  -import pytest
  -from fs2.core.models.content_type import ContentType
   from fs2.core.models.code_node import CodeNode
   from fs2.core.utils.hash import compute_content_hash
  ...
  -from fs2.core.services.search.regex_matcher import FieldMatch, RegexMatcher
  +from fs2.core.services.search.regex_matcher import RegexMatcher
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md` and achieve zero HIGH/CRITICAL
