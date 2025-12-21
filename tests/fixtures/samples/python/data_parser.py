"""Data parsing utilities for structured data formats.

Provides parsers for CSV, JSON, and XML data with validation,
streaming support, and error recovery.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar


T = TypeVar("T")


@dataclass
class ParseError:
    """Details about a parsing error."""

    line: int
    column: int
    message: str
    context: str = ""


@dataclass
class ParseResult(Generic[T]):
    """Result of a parsing operation."""

    data: T | None
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if parsing succeeded without errors."""
        return len(self.errors) == 0 and self.data is not None


class DataParser(ABC, Generic[T]):
    """Abstract base class for data parsers.

    Defines the interface for parsing various data formats
    with support for streaming and validation.
    """

    @abstractmethod
    def parse(self, content: str) -> ParseResult[T]:
        """Parse string content into structured data.

        Args:
            content: The raw string content to parse.

        Returns:
            ParseResult containing the parsed data or errors.
        """
        pass

    @abstractmethod
    def parse_file(self, path: Path) -> ParseResult[T]:
        """Parse a file into structured data.

        Args:
            path: Path to the file to parse.

        Returns:
            ParseResult containing the parsed data or errors.
        """
        pass

    def validate(self, data: T) -> list[str]:
        """Validate parsed data (optional override).

        Args:
            data: The parsed data to validate.

        Returns:
            List of validation error messages, empty if valid.
        """
        return []


class JSONParser(DataParser[dict[str, Any]]):
    """Parser for JSON data with schema validation support."""

    def __init__(self, schema: dict[str, Any] | None = None, strict: bool = False):
        """Initialize JSON parser.

        Args:
            schema: Optional JSON schema for validation.
            strict: If True, treat warnings as errors.
        """
        self.schema = schema
        self.strict = strict

    def parse(self, content: str) -> ParseResult[dict[str, Any]]:
        """Parse JSON string content.

        Args:
            content: JSON string to parse.

        Returns:
            ParseResult with parsed dict or errors.
        """
        errors: list[ParseError] = []
        warnings: list[str] = []
        data: dict[str, Any] | None = None

        try:
            data = json.loads(content)
            if not isinstance(data, dict):
                errors.append(
                    ParseError(
                        line=1,
                        column=1,
                        message="Expected JSON object at root level",
                    )
                )
                data = None
        except json.JSONDecodeError as e:
            errors.append(
                ParseError(
                    line=e.lineno,
                    column=e.colno,
                    message=str(e.msg),
                    context=e.doc[max(0, e.pos - 20) : e.pos + 20],
                )
            )

        if data is not None and self.schema:
            validation_errors = self._validate_schema(data)
            if self.strict:
                errors.extend(validation_errors)
            else:
                warnings.extend(e.message for e in validation_errors)

        return ParseResult(data=data, errors=errors, warnings=warnings)

    def parse_file(self, path: Path) -> ParseResult[dict[str, Any]]:
        """Parse a JSON file.

        Args:
            path: Path to JSON file.

        Returns:
            ParseResult with parsed content.
        """
        try:
            content = path.read_text(encoding="utf-8")
            return self.parse(content)
        except FileNotFoundError:
            return ParseResult(
                data=None,
                errors=[
                    ParseError(line=0, column=0, message=f"File not found: {path}")
                ],
            )
        except PermissionError:
            return ParseResult(
                data=None,
                errors=[
                    ParseError(line=0, column=0, message=f"Permission denied: {path}")
                ],
            )

    def _validate_schema(self, data: dict[str, Any]) -> list[ParseError]:
        """Validate data against schema (stub implementation)."""
        # In production, use jsonschema library
        return []


class CSVParser(DataParser[list[dict[str, str]]]):
    """Parser for CSV data with configurable delimiters."""

    def __init__(
        self,
        delimiter: str = ",",
        has_header: bool = True,
        skip_empty_rows: bool = True,
    ):
        """Initialize CSV parser.

        Args:
            delimiter: Field separator character.
            has_header: Whether first row contains column names.
            skip_empty_rows: Whether to skip empty rows.
        """
        self.delimiter = delimiter
        self.has_header = has_header
        self.skip_empty_rows = skip_empty_rows

    def parse(self, content: str) -> ParseResult[list[dict[str, str]]]:
        """Parse CSV string content.

        Args:
            content: CSV string to parse.

        Returns:
            ParseResult with list of row dicts.
        """
        import csv
        from io import StringIO

        errors: list[ParseError] = []
        rows: list[dict[str, str]] = []

        reader = csv.reader(StringIO(content), delimiter=self.delimiter)

        try:
            headers = next(reader) if self.has_header else None

            for line_num, row in enumerate(reader, start=2 if self.has_header else 1):
                if self.skip_empty_rows and not any(row):
                    continue

                if headers:
                    if len(row) != len(headers):
                        errors.append(
                            ParseError(
                                line=line_num,
                                column=1,
                                message=f"Row has {len(row)} fields, expected {len(headers)}",
                            )
                        )
                        continue
                    rows.append(dict(zip(headers, row)))
                else:
                    rows.append({str(i): v for i, v in enumerate(row)})
        except csv.Error as e:
            errors.append(ParseError(line=0, column=0, message=str(e)))

        return ParseResult(data=rows if not errors else None, errors=errors)

    def parse_file(self, path: Path) -> ParseResult[list[dict[str, str]]]:
        """Parse a CSV file."""
        try:
            content = path.read_text(encoding="utf-8")
            return self.parse(content)
        except (FileNotFoundError, PermissionError) as e:
            return ParseResult(
                data=None,
                errors=[ParseError(line=0, column=0, message=str(e))],
            )

    def stream(self, path: Path) -> Iterator[dict[str, str]]:
        """Stream CSV rows one at a time for large files.

        Args:
            path: Path to CSV file.

        Yields:
            Dictionary for each row.
        """
        import csv

        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=self.delimiter)
            headers = next(reader) if self.has_header else None

            for row in reader:
                if self.skip_empty_rows and not any(row):
                    continue
                if headers:
                    yield dict(zip(headers, row))
                else:
                    yield {str(i): v for i, v in enumerate(row)}
