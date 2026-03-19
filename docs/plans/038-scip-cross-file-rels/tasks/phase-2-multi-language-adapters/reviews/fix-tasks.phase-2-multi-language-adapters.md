# Fix Tasks: Phase 2: Multi-Language Adapters

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Make JavaScript alias support constructible
- **Severity**: HIGH
- **File(s)**:
  - `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter.py`
  - `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter.py`
- **Issue**: `normalise_language("js")` returns `javascript`, but `create_scip_adapter("javascript")` raises `SCIPAdapterError`. That breaks the documented `js` alias contract and leaves AC13 false in practice.
- **Fix**: Make every accepted alias/canonical value map to a constructible adapter. The cleanest Phase 2 remediation is to let canonical `javascript` resolve to the shared `SCIPTypeScriptAdapter` (or change normalisation so `js` canonicalises directly to `typescript`), then add a direct regression test for `create_scip_adapter(normalise_language("js"))`.
- **Patch hint**:
  ```diff
  --- /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter.py
  +++ /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter.py
  @@
   from fs2.core.adapters.scip_adapter_dotnet import SCIPDotNetAdapter
   from fs2.core.adapters.scip_adapter_go import SCIPGoAdapter
   from fs2.core.adapters.scip_adapter_python import SCIPPythonAdapter
   from fs2.core.adapters.scip_adapter_typescript import SCIPTypeScriptAdapter
  @@
       adapters: dict[str, type[SCIPAdapterBase]] = {
  +        "javascript": SCIPTypeScriptAdapter,
           "python": SCIPPythonAdapter,
           "typescript": SCIPTypeScriptAdapter,
           "go": SCIPGoAdapter,
           "dotnet": SCIPDotNetAdapter,
       }
  --- /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter.py
  +++ /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter.py
  @@
  +def test_factory_supports_javascript_alias():
  +    adapter = create_scip_adapter(normalise_language("js"))
  +    assert isinstance(adapter, SCIPTypeScriptAdapter)
  ```

## Medium / Low Fixes

### FT-002: Remove out-of-scope telemetry from the phase diff
- **Severity**: MEDIUM
- **File(s)**:
  - `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/.chainglass/data/activity-log.jsonl`
- **Issue**: The tracked `.chainglass` activity log is included in the Phase 2 diff even though it is not part of the declared adapter/tests/fixtures/doc outputs for this phase.
- **Fix**: Remove the file from the Phase 2 change set before merge (split it into a separate non-phase change or revert it from this branch/commit range).
- **Patch hint**:
  ```diff
  --- /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/.chainglass/data/activity-log.jsonl
  +++ /dev/null
  @@
  -<remove the tracked telemetry change from the Phase 2 diff>
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
