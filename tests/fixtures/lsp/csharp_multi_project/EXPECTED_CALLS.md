# Expected Calls - C# Multi-Project Fixture

This document defines the expected cross-file and same-file method calls
that LSP-based relationship extraction should detect.

## Fixture Overview

| File | Path | Purpose |
|------|------|---------|
| Program.cs | src/App/Program.cs | Entry point with cross-file calls |
| AuthService.cs | src/Auth/AuthService.cs | AuthService with method chains |
| DateFormatter.cs | src/Utils/DateFormatter.cs | Utility functions |

## Cross-File Calls (6 expected)

These calls cross file boundaries and should be detected via LSP references/definitions.

| ID | Source File | Source Symbol | Source Line | Target File | Target Symbol | Target Line | Edge Type |
|----|-------------|---------------|-------------|-------------|---------------|-------------|-----------|
| CS-CF-001 | src/App/Program.cs | (top-level) | 12 | src/Auth/AuthService.cs | AuthService.Create | 65 | calls |
| CS-CF-002 | src/App/Program.cs | (top-level) | 13 | src/Auth/AuthService.cs | AuthService.Login | 35 | calls |
| CS-CF-003 | src/App/Program.cs | (top-level) | 14 | src/Utils/DateFormatter.cs | DateFormatter.FormatDate | 14 | calls |
| CS-CF-004 | src/App/Program.cs | ProcessUser | 24 | src/Auth/AuthService.cs | AuthService.ctor | 16 | calls |
| CS-CF-005 | src/App/Program.cs | ProcessUser | 25 | src/Auth/AuthService.cs | AuthService.Login | 35 | calls |
| CS-CF-006 | src/Auth/AuthService.cs | AuthService.Validate | 50 | src/Utils/DateFormatter.cs | DateFormatter.ValidateString | 26 | calls |

## Same-File Calls (4 expected)

These calls stay within the same file and test intra-file method resolution.

| ID | Source File | Source Symbol | Source Line | Target Symbol | Target Line | Pattern |
|----|-------------|---------------|-------------|---------------|-------------|---------|
| CS-SF-001 | src/Auth/AuthService.cs | AuthService.ctor | 20 | AuthService.Setup | 26 | constructor→private |
| CS-SF-002 | src/Auth/AuthService.cs | AuthService.Login | 39 | AuthService.Validate | 45 | public→private |
| CS-SF-003 | src/Auth/AuthService.cs | AuthService.Validate | 49 | AuthService.CheckToken | 56 | private→private chain |
| CS-SF-004 | src/Auth/AuthService.cs | AuthService.Create | 69 | AuthService.ctor | 16 | static→constructor |

## C#-Specific Patterns

1. **Top-level statements**: C# 9+ allows implicit Main (Program.cs)
2. **Static methods**: `DateFormatter.FormatDate()` on static class
3. **Access modifiers**: public/private visibility
4. **Namespaces**: Cross-namespace calls via using directives
5. **Expression-bodied members**: `=> new AuthService()` shorthand

## Validation Commands

```bash
# Check C# syntax
dotnet build src/App/App.csproj

# Run OmniSharp to find references
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

### src/App/Program.cs
- Line 8: Top-level statements start
- Line 12: `AuthService.Create()` call
- Line 13: `auth.Login()` call
- Line 14: `DateFormatter.FormatDate()` call
- Line 20: `ProcessUser()` definition
- Line 24: `new AuthService()` instantiation
- Line 25: `auth.Login()` call

### src/Auth/AuthService.cs
- Line 9: `AuthService` class definition
- Line 16: constructor definition
- Line 20: `Setup()` call
- Line 26: `Setup()` definition
- Line 35: `Login()` definition
- Line 39: `Validate()` call
- Line 45: `Validate()` definition
- Line 49: `CheckToken()` call
- Line 50: `DateFormatter.ValidateString()` call
- Line 56: `CheckToken()` definition
- Line 65: `Create()` definition
- Line 69: `new AuthService()` instantiation

### src/Utils/DateFormatter.cs
- Line 7: `DateFormatter` class definition
- Line 14: `FormatDate()` definition
- Line 26: `ValidateString()` definition
