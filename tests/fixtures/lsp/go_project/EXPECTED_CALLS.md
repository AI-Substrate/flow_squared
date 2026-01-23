# Expected Calls - Go Project Fixture

This document defines the expected cross-file and same-file method calls
that LSP-based relationship extraction should detect.

## Fixture Overview

| File | Path | Purpose |
|------|------|---------|
| main.go | cmd/app/main.go | Entry point with cross-file calls |
| auth.go | internal/auth/auth.go | AuthService with method chains |
| format.go | pkg/utils/format.go | Utility functions |

## Cross-File Calls (6 expected)

These calls cross file boundaries and should be detected via LSP references/definitions.

| ID | Source File | Source Symbol | Source Line | Target File | Target Symbol | Target Line | Edge Type |
|----|-------------|---------------|-------------|-------------|---------------|-------------|-----------|
| GO-CF-001 | cmd/app/main.go | main | 16 | internal/auth/auth.go | NewAuthService | 14 | calls |
| GO-CF-002 | cmd/app/main.go | main | 17 | internal/auth/auth.go | AuthService.Login | 29 | calls |
| GO-CF-003 | cmd/app/main.go | main | 18 | pkg/utils/format.go | FormatDate | 9 | calls |
| GO-CF-004 | cmd/app/main.go | processUser | 27 | internal/auth/auth.go | NewAuthService | 14 | calls |
| GO-CF-005 | cmd/app/main.go | processUser | 28 | internal/auth/auth.go | AuthService.Login | 29 | calls |
| GO-CF-006 | internal/auth/auth.go | AuthService.validate | 42 | pkg/utils/format.go | ValidateString | 20 | calls |

## Same-File Calls (4 expected)

These calls stay within the same file and test intra-file method resolution.

| ID | Source File | Source Symbol | Source Line | Target Symbol | Target Line | Pattern |
|----|-------------|---------------|-------------|---------------|-------------|---------|
| GO-SF-001 | internal/auth/auth.go | NewAuthService | 18 | AuthService.setup | 23 | constructor→unexported |
| GO-SF-002 | internal/auth/auth.go | AuthService.Login | 33 | AuthService.validate | 37 | exported→unexported |
| GO-SF-003 | internal/auth/auth.go | AuthService.validate | 41 | AuthService.checkToken | 47 | unexported→unexported chain |

## Go-Specific Patterns

1. **Constructor-like pattern**: `NewAuthService()` factory function
2. **Exported vs Unexported**: Capital letter = exported, lowercase = unexported
3. **Method receivers**: `(s *AuthService)` style methods on structs
4. **Package imports**: Cross-package calls via import paths

## Validation Commands

```bash
# Check Go syntax
go build ./cmd/app/...

# Run gopls to find references
# (requires manual LSP interaction)
```

## Test Assertions

When running `test_symbol_level_edges.py`:

1. **Cross-file count**: ≥6 edges detected
2. **Same-file count**: ≥3 edges detected
3. **Total count**: ≥9 edges
4. **Accuracy**: All documented edges should be detected (zero false negatives)
5. **Precision**: No spurious edges to unrelated symbols (minimal false positives)

## Line Number Reference

### cmd/app/main.go
- Line 12: `main()` definition
- Line 16: `auth.NewAuthService()` call
- Line 17: `s.Login()` call
- Line 18: `utils.FormatDate()` call
- Line 23: `processUser()` definition
- Line 27: `auth.NewAuthService()` call
- Line 28: `s.Login()` call

### internal/auth/auth.go
- Line 8: `AuthService` struct definition
- Line 14: `NewAuthService()` definition
- Line 18: `s.setup()` call
- Line 23: `setup()` definition
- Line 29: `Login()` definition
- Line 33: `s.validate()` call
- Line 37: `validate()` definition
- Line 41: `s.checkToken()` call
- Line 42: `utils.ValidateString()` call
- Line 47: `checkToken()` definition
- Line 54: `Validate()` standalone function

### pkg/utils/format.go
- Line 9: `FormatDate()` definition
- Line 20: `ValidateString()` definition
