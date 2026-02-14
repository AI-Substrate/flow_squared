"""Exclude tests/scratch/ from pytest collection.

Scratch tests are manual/exploratory scripts not meant for CI.
"""

collect_ignore_glob = ["test_*.py"]
