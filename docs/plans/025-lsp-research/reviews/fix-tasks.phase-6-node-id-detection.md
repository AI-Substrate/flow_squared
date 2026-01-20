# Fix Tasks: Phase 6 - Node ID and Filename Detection

**Review**: [review.phase-6-node-id-detection.md](review.phase-6-node-id-detection.md)  
**Created**: 2026-01-20  
**Verdict**: REQUEST_CHANGES (6 blocking issues)

---

## Priority Order

Fixes ordered by severity: CRITICAL → HIGH → MEDIUM → LOW

**Testing Approach**: Full TDD (write test first for each fix)

---

## CRITICAL Fixes (Must Fix Before Merge)

### FIX-001 [CRITICAL]: Add hyphen support to NODE_ID_PATTERN regex

**Issue**: SEM-001 - NODE_ID_PATTERN excludes hyphens, truncates paths like `file:docs/plans/022-cross-file-rels/tasks.md` to `file:docs/plans/022`

**File**: `src/fs2/core/services/relationship_extraction/nodeid_detector.py:36`

**Impact**: Data loss in production when scanning real documentation with hyphenated paths (common in Python packages, npm packages, project directories)

**Testing Approach**: TDD - Write failing test first

#### Step 1: Write Failing Test (RED)

**File**: `tests/unit/services/test_nodeid_detector.py`

Add new test method to `TestNodeIdDetector` class:

```python
def test_given_hyphenated_path_when_detect_then_full_path_captured(self):
    """
    Purpose: Proves hyphenated paths work correctly
    Quality Contribution: Regression-prone - hyphenated paths common in real projects
    Acceptance Criteria: Full path with hyphens captured, not truncated
    """
    content = "See file:docs/plans/022-cross-file-rels/tasks.md for details"
    detector = NodeIdDetector()
    
    edges = detector.detect("file:README.md", content)
    
    assert len(edges) == 1
    assert edges[0].target_node_id == "file:docs/plans/022-cross-file-rels/tasks.md"
    assert edges[0].confidence == 1.0
    
def test_given_hyphenated_package_name_when_detect_then_matches(self):
    """
    Purpose: Proves Python package names with hyphens work
    Quality Contribution: Edge case - npm/pip packages often have hyphens
    Acceptance Criteria: Packages like my-cool-lib captured correctly
    """
    content = "Import from callable:src/my-cool-lib/handler.py:process"
    detector = NodeIdDetector()
    
    edges = detector.detect("file:app.py", content)
    
    assert len(edges) == 1
    assert edges[0].target_node_id == "callable:src/my-cool-lib/handler.py:process"
```

**Run test** (should FAIL):
```bash
pytest tests/unit/services/test_nodeid_detector.py::TestNodeIdDetector::test_given_hyphenated_path_when_detect_then_full_path_captured -v

# Expected: FAIL with assertion error
# AssertionError: assert 'file:docs/plans/022' == 'file:docs/plans/022-cross-file-rels/tasks.md'
```

#### Step 2: Fix Implementation (GREEN)

**File**: `src/fs2/core/services/relationship_extraction/nodeid_detector.py`

**Patch**:
```diff
--- a/src/fs2/core/services/relationship_extraction/nodeid_detector.py
+++ b/src/fs2/core/services/relationship_extraction/nodeid_detector.py
@@ -33,9 +33,10 @@ class NodeIdDetector:
     # Node ID regex pattern per 022 experiment Finding 10
     # Matches: file:path, callable:path:name, type:path:name, class:path:name, method:path:name
     # Word boundaries (\b) prevent matching URLs or other colon-separated text
+    # Path segment includes hyphens for package names like my-cool-lib
     NODE_ID_PATTERN = re.compile(
-        r'\b(file|callable|type|class|method):[\w./]+(?::[\w.]+)?\b'
+        r'\b(file|callable|type|class|method):[\w./-]+(?::[\w.]+)?\b'
     )
 
     def detect(self, source_file: str, content: str) -> list[CodeEdge]:
```

**Run test** (should PASS):
```bash
pytest tests/unit/services/test_nodeid_detector.py::TestNodeIdDetector::test_given_hyphenated_path_when_detect_then_full_path_captured -v

# Expected: PASS ✅
```

#### Step 3: Verify All Tests Pass

```bash
pytest tests/unit/services/test_nodeid_detector.py -v
# Expected: 13/13 passing (11 original + 2 new)

pytest tests/integration/test_text_reference_integration.py -v
# Expected: 4/4 passing
```

#### Step 4: Run Quality Gates

```bash
ruff check src/fs2/core/services/relationship_extraction/nodeid_detector.py
mypy src/fs2/core/services/relationship_extraction/nodeid_detector.py --strict
```

**Acceptance Criteria**:
- [ ] New tests fail before fix (RED) ✅
- [ ] New tests pass after fix (GREEN) ✅
- [ ] All existing tests still pass ✅
- [ ] Ruff clean ✅
- [ ] Mypy clean ✅

---

### FIX-002 [CRITICAL]: Add input validation for `content` parameter in NodeIdDetector

**Issue**: COR-001 - No validation, crashes with `AttributeError` if content is None

**File**: `src/fs2/core/services/relationship_extraction/nodeid_detector.py:40`

**Impact**: Unhandled crash when content is None or non-string

**Testing Approach**: TDD - Write failing test first

#### Step 1: Write Failing Test (RED)

**File**: `tests/unit/services/test_nodeid_detector.py`

Add new test methods:

```python
def test_given_none_content_when_detect_then_raises_type_error(self):
    """
    Purpose: Proves None content raises meaningful TypeError
    Quality Contribution: Critical path - prevents obscure AttributeError crashes
    Acceptance Criteria: TypeError raised with clear message
    """
    detector = NodeIdDetector()
    
    with pytest.raises(TypeError, match="content must be string"):
        detector.detect("file:README.md", None)  # type: ignore

def test_given_int_content_when_detect_then_raises_type_error(self):
    """
    Purpose: Proves non-string content raises TypeError
    Quality Contribution: Edge case - catch type mistakes early
    """
    detector = NodeIdDetector()
    
    with pytest.raises(TypeError, match="content must be string"):
        detector.detect("file:README.md", 123)  # type: ignore
```

**Run test** (should FAIL):
```bash
pytest tests/unit/services/test_nodeid_detector.py::TestNodeIdDetector::test_given_none_content_when_detect_then_raises_type_error -v

# Expected: FAIL - AttributeError instead of TypeError
```

#### Step 2: Fix Implementation (GREEN)

**File**: `src/fs2/core/services/relationship_extraction/nodeid_detector.py`

**Patch**:
```diff
--- a/src/fs2/core/services/relationship_extraction/nodeid_detector.py
+++ b/src/fs2/core/services/relationship_extraction/nodeid_detector.py
@@ -62,6 +62,12 @@ class NodeIdDetector:
             >>> edges[0].confidence
             1.0
         """
+        # Validate inputs
+        if not isinstance(source_file, str):
+            raise TypeError(f'source_file must be string, got {type(source_file).__name__}')
+        if not isinstance(content, str):
+            raise TypeError(f'content must be string, got {type(content).__name__}')
+        
         edges: list[CodeEdge] = []
 
         # Split content into lines for line number tracking
```

**Run test** (should PASS):
```bash
pytest tests/unit/services/test_nodeid_detector.py::TestNodeIdDetector::test_given_none_content_when_detect_then_raises_type_error -v
# Expected: PASS ✅
```

#### Step 3: Verify All Tests Pass

```bash
pytest tests/unit/services/test_nodeid_detector.py -v
# Expected: 15/15 passing (13 from FIX-001 + 2 new)
```

**Acceptance Criteria**:
- [ ] New tests fail before fix (RED) ✅
- [ ] New tests pass after fix (GREEN) ✅
- [ ] All existing tests still pass ✅
- [ ] Ruff clean ✅
- [ ] Mypy clean ✅

**Note**: This fix also addresses **COR-003 [HIGH]** (source_file validation) in the same patch.

---

### FIX-003 [CRITICAL]: Add input validation for `content` parameter in RawFilenameDetector

**Issue**: COR-002 - No validation, crashes with `AttributeError` or `TypeError` if content is None

**File**: `src/fs2/core/services/relationship_extraction/raw_filename_detector.py:62`

**Impact**: Unhandled crash when content is None or non-string

**Testing Approach**: TDD - Write failing test first

#### Step 1: Write Failing Test (RED)

**File**: `tests/unit/services/test_raw_filename_detector.py`

Add new test methods to `TestRawFilenameDetector` class:

```python
def test_given_none_content_when_detect_then_raises_type_error(self):
    """
    Purpose: Proves None content raises meaningful TypeError
    Quality Contribution: Critical path - prevents obscure crashes
    Acceptance Criteria: TypeError raised with clear message
    """
    detector = RawFilenameDetector()
    
    with pytest.raises(TypeError, match="content must be string"):
        detector.detect("file:README.md", None)  # type: ignore

def test_given_list_content_when_detect_then_raises_type_error(self):
    """
    Purpose: Proves non-string content raises TypeError
    Quality Contribution: Edge case - catch type mistakes early
    """
    detector = RawFilenameDetector()
    
    with pytest.raises(TypeError, match="content must be string"):
        detector.detect("file:README.md", ["not", "a", "string"])  # type: ignore
```

**Run test** (should FAIL):
```bash
pytest tests/unit/services/test_raw_filename_detector.py::TestRawFilenameDetector::test_given_none_content_when_detect_then_raises_type_error -v

# Expected: FAIL - AttributeError or TypeError (wrong message)
```

#### Step 2: Fix Implementation (GREEN)

**File**: `src/fs2/core/services/relationship_extraction/raw_filename_detector.py`

**Patch**:
```diff
--- a/src/fs2/core/services/relationship_extraction/raw_filename_detector.py
+++ b/src/fs2/core/services/relationship_extraction/raw_filename_detector.py
@@ -86,6 +86,12 @@ class RawFilenameDetector:
             0.5
         """
+        # Validate inputs
+        if not isinstance(source_file, str):
+            raise TypeError(f'source_file must be string, got {type(source_file).__name__}')
+        if not isinstance(content, str):
+            raise TypeError(f'content must be string, got {type(content).__name__}')
+        
         edges: list[CodeEdge] = []
 
         # Pre-filter to remove URLs/domains (DYK-6)
```

**Also update** `_filter_urls()` method for defensive programming:

```diff
@@ -133,6 +139,10 @@ class RawFilenameDetector:
     def _filter_urls(self, content: str) -> str:
         """Pre-filter to remove URLs and domains before filename detection."""
+        # Defensive check (already validated in detect(), but safe)
+        if not isinstance(content, str):
+            return ""
+        
         # Remove full URLs (http://, https://, ftp://)
         content = self.URL_PATTERN.sub('', content)
```

**Run test** (should PASS):
```bash
pytest tests/unit/services/test_raw_filename_detector.py::TestRawFilenameDetector::test_given_none_content_when_detect_then_raises_type_error -v
# Expected: PASS ✅
```

#### Step 3: Verify All Tests Pass

```bash
pytest tests/unit/services/test_raw_filename_detector.py -v
# Expected: 14/14 passing (12 original + 2 new)
```

**Acceptance Criteria**:
- [ ] New tests fail before fix (RED) ✅
- [ ] New tests pass after fix (GREEN) ✅
- [ ] All existing tests still pass ✅
- [ ] Ruff clean ✅
- [ ] Mypy clean ✅

**Note**: This fix also addresses **COR-004 [HIGH]** (source_file validation) in the same patch.

---

## HIGH Fixes (Must Fix Before Merge)

### FIX-004 [HIGH]: Align hyphen support in both detectors

**Issue**: SEM-002 - Pattern inconsistency between NodeIdDetector and RawFilenameDetector

**Files**:
- `src/fs2/core/services/relationship_extraction/nodeid_detector.py:36`
- `src/fs2/core/services/relationship_extraction/raw_filename_detector.py:46`

**Impact**: Asymmetric behavior - hyphenated paths work for raw filenames but fail for explicit node_ids

**Fix**: Already addressed by FIX-001 (NODE_ID_PATTERN now includes hyphens)

#### Verification Test

Add test to verify both detectors handle hyphens consistently:

**File**: `tests/unit/services/test_text_reference_extractor.py`

```python
def test_given_hyphenated_path_both_formats_when_extract_then_consistent(self):
    """
    Purpose: Proves both detectors handle hyphens consistently
    Quality Contribution: Regression-prone - pattern symmetry across detectors
    Acceptance Criteria: Both node_id and raw filename formats work with hyphens
    """
    extractor = TextReferenceExtractor()
    
    # Test explicit node_id format with hyphens
    nodeid_content = "See file:src/my-cool-lib/handler.py for details"
    nodeid_edges = extractor.extract("file:README.md", nodeid_content)
    assert len(nodeid_edges) == 1
    assert nodeid_edges[0].target_node_id == "file:src/my-cool-lib/handler.py"
    assert nodeid_edges[0].confidence == 1.0
    
    # Test raw filename format with hyphens
    filename_content = "Check `src/my-cool-lib/handler.py` for implementation"
    filename_edges = extractor.extract("file:README.md", filename_content)
    assert len(filename_edges) == 1
    assert "my-cool-lib/handler.py" in filename_edges[0].target_node_id
    assert filename_edges[0].confidence == 0.5  # backtick quoted
```

**Run test**:
```bash
pytest tests/unit/services/test_text_reference_extractor.py::TestTextReferenceExtractor::test_given_hyphenated_path_both_formats_when_extract_then_consistent -v
# Expected: PASS ✅ (FIX-001 already fixed this)
```

**Acceptance Criteria**:
- [ ] Test passes with FIX-001 applied ✅
- [ ] Both detectors use `[\w./-]+` for path segments ✅

---

## MEDIUM Fixes (Can Be Follow-Up)

### FIX-005 [MEDIUM]: Add metadata backlinks to execution log

**Issue**: LINK-001, LINK-002 - Missing `**Dossier Task**` and `**Plan Task**` metadata (16 violations across 8 tasks)

**File**: `docs/plans/025-lsp-research/tasks/phase-6-node-id-detection/execution.log.md`

**Impact**: Cannot navigate from execution log to tasks.md or plan

**Fix**: Manual update - add metadata to each task entry

#### Template

For each task entry (T001-T008), add metadata after the `**Status**` line:

```markdown
## Task TXXX: [Task Description]

**Started**: YYYY-MM-DD HH:MM
**Status**: ✅ Complete
**Dossier Task**: [TXXX](tasks.md#task-txxx)
**Plan Task**: 6.XXX

### What I Did
...
```

#### Task Mapping

| Task ID | Dossier Link | Plan Task |
|---------|--------------|-----------|
| T001 | [T001](tasks.md#task-t001) | 6.001 |
| T002 | [T002](tasks.md#task-t002) | 6.002 |
| T003 | [T003](tasks.md#task-t003) | 6.003 |
| T004 | [T004](tasks.md#task-t004) | 6.004 |
| T005 | [T005](tasks.md#task-t005) | 6.005 |
| T006 | [T006](tasks.md#task-t006) | 6.006 |
| T007 | [T007](tasks.md#task-t007) | 6.007 |
| T008 | [T008](tasks.md#task-t008) | 6.008 |

#### Acceptance Criteria

- [ ] All 8 task entries updated ✅
- [ ] Markdown links valid ✅
- [ ] Plan task IDs match plan § Phase 6 ✅

---

### FIX-006 [MEDIUM]: Expand DOMAIN_PATTERN TLD coverage

**Issue**: SEM-003 - Only 9 TLDs covered, missing .uk, .de, .fr, .cn, .ru, .jp, .au, .info, .xyz

**File**: `src/fs2/core/services/relationship_extraction/raw_filename_detector.py:166-169`

**Impact**: Incomplete URL filtering for domains with non-covered TLDs

**Testing Approach**: TDD - Write failing test first

#### Step 1: Write Failing Test (RED)

**File**: `tests/unit/services/test_raw_filename_detector.py`

```python
def test_given_international_domain_when_detect_then_skips(self):
    """
    Purpose: Proves international TLDs are filtered correctly
    Quality Contribution: Edge case - international domains common in docs
    Acceptance Criteria: .uk, .de, .fr, .cn, .jp domains filtered out
    """
    detector = RawFilenameDetector()
    
    test_cases = [
        "example.uk",
        "example.de",
        "example.fr",
        "example.cn",
        "example.jp",
        "example.au",
        "example.info",
    ]
    
    for domain in test_cases:
        edges = detector.detect("file:README.md", f"Visit {domain} for details")
        assert len(edges) == 0, f"Domain {domain} should be filtered out"
```

**Run test** (should FAIL):
```bash
pytest tests/unit/services/test_raw_filename_detector.py::TestRawFilenameDetector::test_given_international_domain_when_detect_then_skips -v

# Expected: FAIL - some domains not filtered
```

#### Step 2: Fix Implementation (GREEN)

**Patch**:
```diff
--- a/src/fs2/core/services/relationship_extraction/raw_filename_detector.py
+++ b/src/fs2/core/services/relationship_extraction/raw_filename_detector.py
@@ -24,7 +24,8 @@ class RawFilenameDetector:
     # Domain pattern to filter out URLs
     # Matches common TLDs to prevent false positives like 'github.com' → 'github.c'
     DOMAIN_PATTERN = re.compile(
-        r'\b[\w.-]+\.(com|org|net|edu|gov|io|co|dev|app|ai)\b',
+        r'\b[\w.-]+\.(com|org|net|edu|gov|io|co|dev|app|ai|'
+        r'uk|de|fr|cn|ru|jp|au|ca|br|in|info|xyz|tech|me|tv)\b',
         re.IGNORECASE
     )
```

**Run test** (should PASS):
```bash
pytest tests/unit/services/test_raw_filename_detector.py::TestRawFilenameDetector::test_given_international_domain_when_detect_then_skips -v
# Expected: PASS ✅
```

#### Acceptance Criteria

- [ ] New test fails before fix (RED) ✅
- [ ] New test passes after fix (GREEN) ✅
- [ ] All existing tests still pass ✅

---

## LOW Fixes (Optional Improvements)

### FIX-007 [LOW]: Expand integration test validation

**Issue**: INT-001 - Integration test validates only 5/11 patterns, masking regex bug

**File**: `tests/integration/test_text_reference_integration.py:1031-1076`

**Impact**: Silent failure - bug SEM-001 was not caught during development

**Fix**: Add assertions for all 11 expected patterns from fixture

#### Implementation

**File**: `tests/integration/test_text_reference_integration.py`

**Patch**:
```diff
--- a/tests/integration/test_text_reference_integration.py
+++ b/tests/integration/test_text_reference_integration.py
@@ -41,11 +41,42 @@ class TestTextReferenceIntegration:
         extractor = TextReferenceExtractor()
         edges = extractor.extract(str(fixture_path), content)
         
-        # Validate some key patterns (existing checks)
+        # Validate ALL expected patterns from fixture
+        expected_targets = [
+            "file:src/lib/parser.py",
+            "class:src/lib/parser.py:Parser",
+            "method:src/lib/parser.py:Parser.detect_language",
+            "class:src/fs2/core/adapters/log_adapter.py:LogAdapter",
+            "callable:src/lib/resolver.py:calculate_confidence",
+            "file:docs/plans/022-cross-file-rels/tasks.md",
+            "type:src/models/types.py:ImportInfo",
+            "method:src/lib/parser.py:Parser.parse",
+            "file:src/app.py",
+            "callable:src/utils/helpers.py:format_output",
+            "class:src/core/service.py:Service",
+        ]
+        
+        actual_targets = [edge.target_node_id for edge in edges]
+        
+        # Assert all expected patterns were found
+        for expected in expected_targets:
+            assert expected in actual_targets, f"Missing pattern: {expected}"
+        
+        # Assert minimum count (at least 11 patterns)
         assert len(edges) >= 5
+        
+        # Validate confidence levels
         node_id_edges = [e for e in edges if e.confidence == 1.0]
         assert len(node_id_edges) >= 3
+        
+        # Validate no duplicate (source, target, line) tuples (DYK-7)
+        seen = set()
+        for edge in edges:
+            key = (edge.source_node_id, edge.target_node_id, edge.source_line)
+            assert key not in seen, f"Duplicate edge: {key}"
+            seen.add(key)
```

#### Acceptance Criteria

- [ ] Test validates all 11 expected patterns ✅
- [ ] Test catches hyphen bug if regex is reverted ✅
- [ ] Test validates deduplication (DYK-7) ✅

---

### FIX-008 [LOW]: (Optional) Handle trailing newlines

**Issue**: COR-005 - Trailing newline creates empty final line

**File**: `src/fs2/core/services/relationship_extraction/nodeid_detector.py:67`

**Impact**: Very low - empty lines don't match patterns, potential confusion in line numbers

**Fix** (optional):

```diff
--- a/src/fs2/core/services/relationship_extraction/nodeid_detector.py
+++ b/src/fs2/core/services/relationship_extraction/nodeid_detector.py
@@ -70,7 +70,8 @@ class NodeIdDetector:
         edges: list[CodeEdge] = []
 
         # Split content into lines for line number tracking
-        lines = content.split('\n')
+        # Strip trailing newline to avoid empty final line
+        lines = content.rstrip('\n').split('\n') if content else []
 
         for line_num, line in enumerate(lines, start=1):
             # Find all node_id patterns in this line
```

**Note**: This fix is optional and has minimal impact. Consider deferring unless line number accuracy becomes critical.

---

## Verification Checklist

After applying all CRITICAL and HIGH fixes:

- [ ] FIX-001: Hyphen support in NODE_ID_PATTERN ✅
- [ ] FIX-002: Input validation in NodeIdDetector ✅
- [ ] FIX-003: Input validation in RawFilenameDetector ✅
- [ ] FIX-004: Pattern consistency verified ✅
- [ ] All tests passing (37+ tests expected after new tests added) ✅
- [ ] Ruff clean ✅
- [ ] Mypy --strict clean ✅
- [ ] Coverage still > 80% ✅

Run final verification:

```bash
# Run all Phase 6 tests
pytest tests/unit/services/test_nodeid_detector.py \
       tests/unit/services/test_raw_filename_detector.py \
       tests/unit/services/test_text_reference_extractor.py \
       tests/integration/test_text_reference_integration.py -v

# Expected: 37+ passing (35 original + 2+ new from fixes)

# Quality gates
ruff check src/fs2/core/services/relationship_extraction/
mypy src/fs2/core/services/relationship_extraction/ --strict

# Coverage
pytest --cov=src/fs2/core/services/relationship_extraction \
       --cov-report=term-missing
# Expected: Still > 80% (likely 99%+)
```

After fixes complete, re-run code review:

```bash
/plan-7-code-review --phase "Phase 6: Node ID and Filename Detection" \
  --plan "/workspaces/flow_squared/docs/plans/025-lsp-research/lsp-integration-plan.md"
```

**Expected Outcome**: ✅ APPROVE verdict

---

**End of Fix Tasks**
