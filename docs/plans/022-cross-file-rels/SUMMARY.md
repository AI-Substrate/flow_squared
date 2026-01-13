# Cross-File Relationship Detection: Executive Summary

**TL;DR**: We validated that Tree-sitter can detect cross-file imports with 100% accuracy for Python and TypeScript. The approach works, but raw filename detection in prose (the most common pattern in real codebases) isn't implemented yet.

---

## What We Did

We ran a controlled experiment to see if we could detect cross-file relationships (imports, function calls, documentation links) using Tree-sitter parsing instead of SCIP indexers. We created 21 fixture files across 15 languages and defined 15 ground truth relationships to validate against.

**The experiment consisted of 6 scripts:**
1. Tree-sitter setup verification
2. Node ID pattern detection (finding `callable:path:Symbol` in text)
3. Import extraction across languages
4. Function/method call extraction
5. Cross-language reference detection (Dockerfile, YAML)
6. Confidence scoring validation against ground truth

---

## What We Learned

### The Good News

- **Import detection works great** for Python, TypeScript, Go, Java, C, and C++
- **Node ID patterns are bulletproof** - when someone writes `callable:src/calc.py:Calculator.add` in a log file, we detect it 100% of the time with confidence 1.0
- **Tree-sitter-language-pack is the right choice** - one pip install, 165 languages, no external binaries
- **fs2's NetworkX graph already supports edge attributes** - infrastructure is 80% ready

### The Concerning News

- **Raw file names in prose don't work** - if a README says "see `auth_handler.py` for details", we don't catch it. This is arguably the most common cross-file reference pattern in real codebases.
- **Constructor confidence is miscalibrated** - Python constructors like `AuthHandler()` get 0.5 confidence (PascalCase heuristic) but we expected 0.8
- **Method calls on typed receivers need type inference** - `self.auth.validate_token()` can't be resolved to `AuthHandler.validate_token` without knowing the type of `self.auth`

### Languages That Don't Work

- **Ruby**: 0 imports detected (Tree-sitter query needs fixing)
- **Rust**: 0 imports detected (Tree-sitter query needs fixing)
- **JavaScript CommonJS**: Not implemented (`require()` not supported)

---

## What's Ready for Production

| Capability | Status | Confidence |
|------------|--------|------------|
| Python imports | Ready | 0.9 |
| TypeScript/TSX imports | Ready | 0.9 |
| Go imports | Ready | 0.9 |
| Node ID detection in text | Ready | 1.0 |
| Dockerfile COPY/ADD refs | Ready | 0.7 |
| Constructor detection | Needs tuning | 0.5 |

**Recommendation**: Ship Python and TypeScript import detection first. These are the most common languages and have 100% validation accuracy.

---

## What's Missing

| Gap | Impact | Effort |
|-----|--------|--------|
| Raw filename detection in prose | High - can't link READMEs to code | Low - regex pattern |
| Ruby/Rust import queries | Medium - blocks those ecosystems | Medium - debug Tree-sitter |
| Cross-file method resolution | Medium - partial call graphs | High - needs type inference |
| JavaScript CommonJS | Medium - legacy codebases | Low - add `require()` query |
| YAML reference testing | Low - code exists, untested | Low - add fixture |

---

## Recommended Next Steps

### P0: Do First (1-2 days)
1. **Implement raw filename detection** - Add regex to catch `auth_handler.py` in prose. This is the biggest gap.
2. **Ship Python + TypeScript extractors** - They're validated and ready.

### P1: Do Soon (3-5 days)
3. **Fix constructor confidence** - Either keep 0.5 (safer) or bump to 0.7 with import context
4. **Debug Ruby/Rust queries** - Run Tree-sitter manually against fixtures to diagnose

### P2: Backlog
5. **Add CommonJS support** - Implement `require()` pattern detection
6. **Create YAML test fixture** - Exercise the existing but untested code
7. **Consider type inference** - Only if method call resolution becomes critical

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Ground truth entries tested | 15 |
| Pass rate | 67% (10/15) |
| Detection rate | 80% (12/15) |
| Import accuracy (Python/TS) | 100% |
| Node ID accuracy | 100% |
| Call detection accuracy | 50%* |

*Constructors detected, method calls on typed receivers not resolved.

---

## Files Reference

- **Full experimentation dossier**: `experimentation-dossier.md`
- **Research dossier**: `research-dossier.md`
- **Experiment scripts**: `/workspaces/flow_squared/scripts/cross-files-rels-research/experiments/`
- **Results JSON**: `/workspaces/flow_squared/scripts/cross-files-rels-research/results/`
- **Ground truth definition**: `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/ground_truth.py`

---

*Generated: 2026-01-13*
