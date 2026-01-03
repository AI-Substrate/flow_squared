# Test-Driven Development

fs2 uses **Full TDD** with fakes preferred over mocks.

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── unit/
│   ├── config/          # Configuration tests
│   ├── adapters/        # Adapter tests
│   ├── models/          # Domain model tests
│   └── services/        # Service tests
├── docs/                # Canonical documentation tests
└── scratch/             # Fast exploration (excluded from CI)
```

## Pytest Markers

```python
@pytest.mark.unit         # Fast, isolated tests
@pytest.mark.integration  # Tests with external deps
@pytest.mark.docs         # Documentation/example tests
```

## Key Fixtures (conftest.py)

```python
@pytest.fixture
def clean_config_env(monkeypatch):
    """Clears all FS2_* env vars - prevents test pollution."""

@pytest.fixture
def test_context():
    """Pre-wired DI container with FakeConfigurationService + FakeLogAdapter."""
```

## Fakes Over Mocks

**Don't use `unittest.mock`** - implement real test doubles:

```python
# YES - Real fake that inherits from ABC
adapter = FakeSampleAdapter(config)
result = adapter.process("data")
assert adapter.call_history == [...]

# NO - Mock object
adapter = Mock(spec=SampleAdapter)  # Fragile, no type safety
```

## Test Naming Convention

```python
def test_given_X_when_Y_then_Z():
    """
    Purpose: What truth this proves
    Quality Contribution: How this prevents bugs
    """
    # Arrange
    ...
    # Act
    ...
    # Assert
    ...
```

## Further Reading

- [tests/docs/test_sample_adapter_pattern.py](../../tests/docs/test_sample_adapter_pattern.py) - 19 canonical tests
- [Adding Services & Adapters](adding-services-adapters.md) - Testing section
