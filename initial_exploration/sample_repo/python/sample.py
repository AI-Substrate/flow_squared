"""Sample Python file for tree-sitter exploration."""

from typing import List, Optional
import asyncio


def standalone_function(x: int, y: int) -> int:
    """A standalone function."""
    return x + y


class Calculator:
    """A sample class with various method types."""

    class_variable: int = 0

    def __init__(self, name: str = "calc"):
        self.name = name
        self._value = 0

    def add(self, a: int, b: int) -> int:
        """Instance method."""
        return a + b

    @staticmethod
    def multiply(a: int, b: int) -> int:
        """Static method."""
        return a * b

    @classmethod
    def from_value(cls, value: int) -> "Calculator":
        """Class method."""
        calc = cls()
        calc._value = value
        return calc

    @property
    def value(self) -> int:
        """Property getter."""
        return self._value

    async def fetch_data(self, url: str) -> dict:
        """Async method."""
        await asyncio.sleep(0.1)
        return {"url": url, "data": "sample"}


class AdvancedCalculator(Calculator):
    """Inheritance example."""

    def add(self, a: int, b: int) -> int:
        """Override method."""
        result = super().add(a, b)
        return result


# Decorators and nested functions
def decorator(func):
    """A simple decorator."""
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@decorator
def decorated_function():
    """Decorated function."""
    pass


# Comprehensions and lambdas
squares = [x**2 for x in range(10)]
square_dict = {x: x**2 for x in range(5)}
evens = {x for x in range(10) if x % 2 == 0}
double = lambda x: x * 2


# Context manager
class FileHandler:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
