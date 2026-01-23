# Expected Calls - Python Multi-Project Fixture

This document defines the expected cross-file and same-file method calls
that LSP-based relationship extraction should detect.

## Fixture Overview

| File | Path | Purpose |
|------|------|---------|
| app.py | src/app.py | Entry point with cross-file calls |
| auth.py | src/auth.py | AuthService with method chains |
| utils.py | src/utils.py | Utility functions |

## Cross-File Calls (5 expected)

These calls cross file boundaries and should be detected via LSP references/definitions.

| ID | Source File | Source Symbol | Source Line | Target File | Target Symbol | Target Line | Edge Type |
|----|-------------|---------------|-------------|-------------|---------------|-------------|-----------|
| PY-CF-001 | src/app.py | main | 12 | src/auth.py | AuthService.create | 52 | calls |
| PY-CF-002 | src/app.py | main | 13 | src/auth.py | AuthService.login | 26 | calls |
| PY-CF-003 | src/app.py | main | 14 | src/utils.py | format_date | 8 | calls |
| PY-CF-004 | src/app.py | process_user | 24 | src/auth.py | AuthService.__init__ | 10 | calls |
| PY-CF-005 | src/app.py | process_user | 25 | src/auth.py | AuthService.login | 26 | calls |
| PY-CF-006 | src/auth.py | AuthService._validate | 41 | src/utils.py | validate_string | 18 | calls |

## Same-File Calls (5 expected)

These calls stay within the same file and test intra-file method resolution.

| ID | Source File | Source Symbol | Source Line | Target Symbol | Target Line | Pattern |
|----|-------------|---------------|-------------|---------------|-------------|---------|
| PY-SF-001 | src/auth.py | AuthService.__init__ | 16 | AuthService._setup | 19 | constructor→private |
| PY-SF-002 | src/auth.py | AuthService.login | 32 | AuthService._validate | 35 | public→private |
| PY-SF-003 | src/auth.py | AuthService._validate | 40 | AuthService._check_token | 45 | private→private chain |
| PY-SF-004 | src/auth.py | AuthService.create | 58 | AuthService.__init__ | 10 | static→constructor |

## Call Patterns Demonstrated

1. **Function → Static Method**: `main()` → `AuthService.create()`
2. **Function → Instance Method**: `main()` → `auth.login()`
3. **Function → Function**: `main()` → `format_date()`
4. **Constructor → Private**: `__init__()` → `_setup()`
5. **Public → Private**: `login()` → `_validate()`
6. **Private → Private (chain)**: `_validate()` → `_check_token()`
7. **Static → Constructor**: `create()` → `AuthService()`
8. **Method → External Function**: `_validate()` → `validate_string()`

## Validation Commands

```bash
# Run Pyright LSP to find references to AuthService.login
pyright --outputjson src/auth.py | jq '.generalDiagnostics'

# Check fixture syntax
python -m py_compile src/app.py src/auth.py src/utils.py
```

## Test Assertions

When running `test_symbol_level_edges.py`:

1. **Cross-file count**: ≥6 edges detected
2. **Same-file count**: ≥4 edges detected  
3. **Total count**: ≥10 edges
4. **Accuracy**: All documented edges should be detected (zero false negatives)
5. **Precision**: No spurious edges to unrelated symbols (minimal false positives)

## Line Number Reference

### src/app.py
- Line 6: `main()` definition
- Line 12: `AuthService.create()` call
- Line 13: `auth.login()` call
- Line 14: `format_date()` call
- Line 19: `process_user()` definition
- Line 24: `AuthService()` instantiation
- Line 25: `auth.login()` call

### src/auth.py
- Line 5: `AuthService` class definition
- Line 10: `__init__()` definition
- Line 16: `self._setup()` call
- Line 19: `_setup()` definition
- Line 26: `login()` definition
- Line 32: `self._validate()` call
- Line 35: `_validate()` definition
- Line 40: `self._check_token()` call
- Line 41: `validate_string()` call
- Line 45: `_check_token()` definition
- Line 52: `create()` definition
- Line 58: `AuthService()` instantiation

### src/utils.py
- Line 8: `format_date()` definition
- Line 18: `validate_string()` definition
