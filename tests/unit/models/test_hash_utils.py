"""Tests for hash utilities.

T006: Hash utility contract tests.
Purpose: Verify SHA-256 hashing helper is deterministic and UTF-8 safe.
"""

import hashlib

import pytest


@pytest.mark.unit
class TestHashUtils:
    """T006: Tests for compute_content_hash()."""

    def test_given_known_text_when_hashing_then_matches_sha256_hexdigest(self):
        """
        Purpose: Proves hashing is standard SHA-256 hexdigest.
        Quality Contribution: Prevents silent hash drift that breaks regeneration logic.
        Acceptance Criteria: Hash matches hashlib.sha256(text.encode("utf-8")).hexdigest().

        Task: T006
        """
        from fs2.core.utils.hash import compute_content_hash

        text = "hello"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()

        assert compute_content_hash(text) == expected

    def test_given_empty_text_when_hashing_then_matches_sha256_empty(self):
        """
        Purpose: Defines hashing behavior for empty content.
        Quality Contribution: Prevents edge-case crashes and inconsistent hashing.
        Acceptance Criteria: Hash equals SHA-256 of empty string.

        Task: T006
        """
        from fs2.core.utils.hash import compute_content_hash

        expected = hashlib.sha256(b"").hexdigest()

        assert compute_content_hash("") == expected

    def test_given_unicode_text_when_hashing_then_uses_utf8(self):
        """
        Purpose: Proves hashing handles unicode deterministically.
        Quality Contribution: Prevents cross-platform encoding inconsistencies.
        Acceptance Criteria: UTF-8 encoding used for hashing.

        Task: T006
        """
        from fs2.core.utils.hash import compute_content_hash

        text = "café"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()

        assert compute_content_hash(text) == expected

