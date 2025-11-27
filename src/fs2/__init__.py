"""
Flowspace2 (fs2) - Clean Architecture Python scaffold.

This package implements Clean Architecture with strict dependency boundaries:
- cli → services (presentation layer)
- services → adapters/repos (composition layer)
- adapters/repos → external systems (infrastructure layer)

See: docs/plans/002-project-skele/project-skele-spec.md
"""
