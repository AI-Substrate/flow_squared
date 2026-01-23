# Expected Calls - TypeScript Multi-Project Fixture

This document defines the expected cross-file and same-file method calls
that LSP-based relationship extraction should detect.

## Fixture Overview

| File | Path | Purpose |
|------|------|---------|
| app.ts | packages/client/src/app.ts | Entry point with cross-file calls |
| auth.ts | packages/client/src/auth.ts | AuthService with method chains |
| utils.ts | packages/client/src/utils.ts | Utility functions |

## Cross-File Calls (6 expected)

These calls cross file boundaries and should be detected via LSP references/definitions.

| ID | Source File | Source Symbol | Source Line | Target File | Target Symbol | Target Line | Edge Type |
|----|-------------|---------------|-------------|-------------|---------------|-------------|-----------|
| TS-CF-001 | src/app.ts | main | 14 | src/auth.ts | AuthService.create | 58 | calls |
| TS-CF-002 | src/app.ts | main | 15 | src/auth.ts | AuthService.login | 31 | calls |
| TS-CF-003 | src/app.ts | main | 16 | src/utils.ts | formatDate | 8 | calls |
| TS-CF-004 | src/app.ts | processUser | 26 | src/auth.ts | AuthService.constructor | 15 | calls |
| TS-CF-005 | src/app.ts | processUser | 27 | src/auth.ts | AuthService.login | 31 | calls |
| TS-CF-006 | src/auth.ts | AuthService.validate | 45 | src/utils.ts | validateString | 19 | calls |

## Same-File Calls (4 expected)

These calls stay within the same file and test intra-file method resolution.

| ID | Source File | Source Symbol | Source Line | Target Symbol | Target Line | Pattern |
|----|-------------|---------------|-------------|---------------|-------------|---------|
| TS-SF-001 | src/auth.ts | AuthService.constructor | 19 | AuthService.setup | 24 | constructor→private |
| TS-SF-002 | src/auth.ts | AuthService.login | 35 | AuthService.validate | 40 | public→private |
| TS-SF-003 | src/auth.ts | AuthService.validate | 44 | AuthService.checkToken | 51 | private→private chain |
| TS-SF-004 | src/auth.ts | AuthService.create | 62 | AuthService.constructor | 15 | static→constructor |

## Call Patterns Demonstrated

1. **Function → Static Method**: `main()` → `AuthService.create()`
2. **Function → Instance Method**: `main()` → `auth.login()`
3. **Function → Function**: `main()` → `formatDate()`
4. **Constructor → Private**: `constructor()` → `setup()`
5. **Public → Private**: `login()` → `validate()`
6. **Private → Private (chain)**: `validate()` → `checkToken()`
7. **Static → Constructor**: `create()` → `new AuthService()`
8. **Method → External Function**: `validate()` → `validateString()`

## Validation Commands

```bash
# Check TypeScript syntax
npx tsc --noEmit packages/client/src/*.ts

# Run typescript-language-server to find references
# (requires manual LSP interaction)
```

## Test Assertions

When running `test_symbol_level_edges.py`:

1. **Cross-file count**: ≥6 edges detected
2. **Same-file count**: ≥4 edges detected
3. **Total count**: ≥10 edges
4. **Accuracy**: All documented edges should be detected (zero false negatives)
5. **Precision**: No spurious edges to unrelated symbols (minimal false positives)

## Line Number Reference

### packages/client/src/app.ts
- Line 10: `main()` definition
- Line 14: `AuthService.create()` call
- Line 15: `auth.login()` call
- Line 16: `formatDate()` call
- Line 22: `processUser()` definition
- Line 26: `new AuthService()` instantiation
- Line 27: `auth.login()` call

### packages/client/src/auth.ts
- Line 9: `AuthService` class definition
- Line 15: `constructor()` definition
- Line 19: `this.setup()` call
- Line 24: `setup()` definition
- Line 31: `login()` definition
- Line 35: `this.validate()` call
- Line 40: `validate()` definition
- Line 44: `this.checkToken()` call
- Line 45: `validateString()` call
- Line 51: `checkToken()` definition
- Line 58: `create()` definition
- Line 62: `new AuthService()` instantiation

### packages/client/src/utils.ts
- Line 8: `formatDate()` definition
- Line 19: `validateString()` definition
