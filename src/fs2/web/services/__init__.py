"""Web services for fs2 Hub.

Services in this module provide read-only config inspection,
backup operations, and other web-specific functionality.

CRITICAL: These services MUST NOT mutate os.environ.
Use dotenv_values() NOT load_dotenv() for secret access.
"""
