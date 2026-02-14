# Fix Tasks — Azure AD Credential Support

**Review**: [review.md](./review.md)
**Verdict**: REQUEST_CHANGES
**Testing Approach**: Full TDD

---

## Fix 1: Ruff B904 — LLM Adapter (LINT-001)

**Severity**: HIGH
**File**: `src/fs2/core/adapters/llm_adapter_azure.py`
**Lines**: 123-127

**Issue**: `raise LLMAdapterError(...)` within `except ImportError` does not use `from None`, violating ruff B904 (flake8-bugbear). This causes confusing double tracebacks for users.

**Fix**:
```diff
 except ImportError:
     raise LLMAdapterError(
         "azure-identity package is required for Azure AD authentication. "
         "Install it with: pip install fs2[azure-ad]"
-    )
+    ) from None
```

**Validation**: `ruff check src/fs2/core/adapters/llm_adapter_azure.py` passes. All existing tests still pass.

---

## Fix 2: Ruff B904 — Embedding Adapter (LINT-002)

**Severity**: HIGH
**File**: `src/fs2/core/adapters/embedding_adapter_azure.py`
**Lines**: 99-103

**Issue**: Same as Fix 1 but for `EmbeddingAdapterError`.

**Fix**:
```diff
 except ImportError:
     raise EmbeddingAdapterError(
         "azure-identity package is required for Azure AD authentication. "
         "Install it with: pip install fs2[azure-ad]"
-    )
+    ) from None
```

**Validation**: `ruff check src/fs2/core/adapters/embedding_adapter_azure.py` passes. All existing tests still pass.

---

## Fix 3: Change Footnotes Ledger (GRAPH-001, GRAPH-002)

**Severity**: HIGH (plan hygiene)
**Files**: `az-login-plan.md` § Change Footnotes Ledger, `tasks.md` § Phase Footnote Stubs

**Issue**: All 4 footnote entries are placeholders. No FlowSpace node IDs recorded for modified files.

**Fix**: Run `plan-6a` to populate:
- Plan § Change Footnotes Ledger with FlowSpace node IDs for all 7 modified files
- Tasks.md § Phase Footnote Stubs with matching entries
- Task table Notes column with footnote references

---

## Fix 4: Plan Status Header (PLAN-005)

**Severity**: MEDIUM (consistency)
**File**: `az-login-plan.md`
**Line**: 9

**Issue**: Header says `**Status**: DRAFT` but footer says `**Status**: COMPLETE`.

**Fix**:
```diff
-**Status**: DRAFT
+**Status**: COMPLETE
```

---

## Fix Order

1. Fix 1 + Fix 2 (code changes — apply together, re-run lint)
2. Fix 3 (plan hygiene — run plan-6a)
3. Fix 4 (plan header — trivial edit)
4. Re-run review to verify
