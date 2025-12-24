# External Research: Regex Timeout Protection

**Research Date**: 2025-12-23
**Research Query**: Python regex timeout protection, catastrophic backtracking prevention, ReDoS mitigation
**Sources**: Perplexity deep search

---

## Executive Summary

Python's standard `re` module has no built-in timeout mechanism and holds the GIL during matching, making catastrophic backtracking dangerous. The **recommended solution** for fs2 is to use the `regex` module (drop-in replacement) which provides built-in timeout support and GIL release.

---

## 1. The Problem: Catastrophic Backtracking & ReDoS

### What It Is

Catastrophic backtracking occurs when a regex pattern causes exponential time complexity due to nested quantifiers. This is exploitable via **ReDoS (Regular Expression Denial of Service)** attacks.

> "Nested quantifiers are repeated or alternated tokens inside a group that is itself repeated or alternated. These almost always lead to catastrophic backtracking."
> — [Regular-Expressions.info](https://www.regular-expressions.info/catastrophic.html)

### Why Python Is Vulnerable

> "The standard regular expression module is a C module that doesn't release the GIL before running. This means that if you have a long running regular expression, like one that is doing catastrophic backtracking - no other code running in another thread will ever get run."
> — [Ben Frederickson](https://www.benfrederickson.com/python-catastrophic-regular-expressions-and-the-gil/)

### Recent CVEs (2024)

| CVE | Library | Impact |
|-----|---------|--------|
| CVE-2024-24762 | python-multipart | ReDoS via Content-Type header |
| CVE-2024-6232 | Python core (TarFile) | ReDoS in header parsing |

Sources: [Snyk CVE-2024-6232](https://security.snyk.io/vuln/SNYK-UNMANAGED-PYTHON-7924816), [Vicarius CVE-2024-24762](https://www.vicarius.io/vsociety/posts/redos-in-python-multipart-cve-2024-24762)

---

## 2. Solution Comparison

| Approach | Cross-Platform | Pros | Cons | Recommended |
|----------|----------------|------|------|-------------|
| **`regex` module timeout** | Yes | Built-in, easy, GIL release | Third-party dep | **Yes** |
| RE2 library (google-re2) | Yes | Prevents backtracking entirely | Limited features | Alternative |
| Subprocess isolation | Yes | Reliable isolation | Performance overhead | Fallback |
| signal.SIGALRM | Unix only | No dependencies | Doesn't work (GIL) | No |
| Pattern optimization | Yes | No overhead | Requires expertise | Complementary |

---

## 3. Recommended Solution: `regex` Module

### Installation

```bash
pip install regex
# or
uv add regex
```

### Timeout Parameter Example

```python
import regex

# Basic timeout (raises TimeoutError after 2 seconds)
try:
    result = regex.search(r'(a+)+$', user_input, timeout=2)
except TimeoutError:
    # Handle timeout gracefully
    result = None
```

Source: [regex on PyPI](https://pypi.org/project/regex/)

### GIL Release for Concurrent Matching

```python
import regex

# Enable concurrent matching (releases GIL, allows other threads to run)
result = regex.search(r'pattern', text, concurrent=True)

# Combined with timeout
result = regex.match(r'pattern', text, timeout=5, concurrent=True)
```

> "The regex module releases the GIL during matching on instances of the built-in (immutable) string classes, enabling other Python threads to run concurrently."
> — [regex PyPI](https://pypi.org/project/regex/)

### Drop-in Replacement

The `regex` module is backwards-compatible with `re`:

```python
# Before
import re
result = re.search(r'pattern', text)

# After (drop-in replacement with timeout)
import regex
result = regex.search(r'pattern', text, timeout=2)
```

---

## 4. Alternative: RE2 Library

For maximum safety, RE2 uses finite automata instead of backtracking:

```bash
pip install google-re2
```

```python
import re2

# RE2 guarantees linear time complexity - no catastrophic backtracking possible
result = re2.search(r'(a+)+$', dangerous_input)  # Runs in O(n) time
```

**Limitations**: RE2 doesn't support all regex features (lookahead, backreferences).

> "RE2 is an excellent library that uses a finite automata approach to avoid this type of catastrophic backtracking. Using this library on the same 32 character input reduces the running time from 12 minutes to basically instant."
> — [Ben Frederickson](https://www.benfrederickson.com/python-catastrophic-regular-expressions-and-the-gil/)

---

## 5. Pattern Optimization Best Practices

Even with timeout protection, optimize patterns to avoid issues:

### Avoid Nested Quantifiers

```python
# Bad: Nested quantifiers
r'(a+)+'  # Exponential complexity

# Good: Atomic grouping or possessive quantifiers (regex module)
r'(?>a+)'  # Atomic group (no backtracking)
r'a++'     # Possessive quantifier
```

### Use Non-Greedy When Possible

```python
# Bad: Greedy with backtracking risk
r'.*something'

# Good: Non-greedy
r'.*?something'
```

> "To avoid catastrophic backtracking, the key is to make the repeating subpattern non-greedy, by adding the character `?` to the end."
> — [Regular-Expressions.info](https://www.regular-expressions.info/catastrophic.html)

### Input Validation

```python
MAX_PATTERN_LENGTH = 1000

def safe_regex_search(pattern: str, text: str, timeout: float = 2.0):
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise ValueError(f"Pattern too long: {len(pattern)} > {MAX_PATTERN_LENGTH}")

    try:
        return regex.search(pattern, text, timeout=timeout)
    except TimeoutError:
        return None
    except regex.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")
```

---

## 6. Static Analysis Tools

Detect vulnerable patterns before runtime:

| Tool | Description |
|------|-------------|
| [Dlint DUO138](https://github.com/duo-labs/dlint) | Detects inefficient regex in Python |
| [CodeQL](https://github.blog/security/how-to-fix-a-redos/) | GitHub's ReDoS detection |
| [Semgrep](https://semgrep.dev/blog/2020/finding-python-redos-bugs-at-scale-using-dlint-and-r2c/) | Find ReDoS at scale |

---

## 7. Recommended Implementation for fs2

### Add Dependency

```toml
# pyproject.toml
dependencies = [
    "regex>=2024.0.0",
]
```

### RegexMatcher Implementation

```python
import regex
from dataclasses import dataclass

# Default timeout (seconds)
DEFAULT_REGEX_TIMEOUT = 2.0
MAX_PATTERN_LENGTH = 2000

@dataclass(frozen=True)
class RegexConfig:
    timeout: float = DEFAULT_REGEX_TIMEOUT
    max_pattern_length: int = MAX_PATTERN_LENGTH


class RegexMatcher:
    """Regex matcher with timeout protection against catastrophic backtracking."""

    def __init__(self, config: RegexConfig | None = None):
        self._config = config or RegexConfig()

    def match(self, pattern: str, text: str) -> regex.Match | None:
        """Execute regex match with timeout protection.

        Args:
            pattern: Regex pattern (user-provided)
            text: Text to search

        Returns:
            Match object or None

        Raises:
            ValueError: Invalid pattern or pattern too long
        """
        # Validate pattern length
        if len(pattern) > self._config.max_pattern_length:
            raise ValueError(
                f"Pattern exceeds maximum length: {len(pattern)} > {self._config.max_pattern_length}"
            )

        try:
            # Compile pattern (validates syntax)
            compiled = regex.compile(pattern)

            # Search with timeout (concurrent=True releases GIL)
            return compiled.search(text, timeout=self._config.timeout, concurrent=True)

        except TimeoutError:
            # Pattern took too long - likely catastrophic backtracking
            return None

        except regex.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
```

### Error Messages

```python
class RegexTimeoutError(Exception):
    """Regex execution exceeded timeout limit."""

    def __init__(self, pattern: str, timeout: float):
        super().__init__(
            f"Regex timed out after {timeout}s. "
            f"Pattern may be too complex: {pattern[:50]}..."
        )
        self.pattern = pattern
        self.timeout = timeout
```

---

## 8. Key Recommendations for fs2

1. **Use `regex` module** instead of `re` for all user-provided patterns
2. **Set default timeout** of 2 seconds (configurable)
3. **Enable `concurrent=True`** to release GIL during matching
4. **Validate pattern length** (max 2000 characters)
5. **Return None on timeout** (graceful degradation, not hard error)
6. **Log timeout events** for monitoring
7. **Document safe patterns** in user documentation

---

## Sources

- [regex on PyPI](https://pypi.org/project/regex/)
- [Ben Frederickson: Python Catastrophic Regular Expressions](https://www.benfrederickson.com/python-catastrophic-regular-expressions-and-the-gil/)
- [Regular-Expressions.info: Catastrophic Backtracking](https://www.regular-expressions.info/catastrophic.html)
- [GitHub Blog: How to Fix a ReDoS](https://github.blog/security/how-to-fix-a-redos/)
- [Snyk: Timing Out Synchronous Functions](https://snyk.io/blog/timing-out-synchronous-functions-with-regex/)
- [AWS CodeGuru: Catastrophic Backtracking Detection](https://docs.aws.amazon.com/codeguru/detector-library/python/catastrophic-backtracking-regex/)
