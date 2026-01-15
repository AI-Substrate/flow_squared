"""User model with validation method."""


class User:
    """User entity with validation logic."""

    def __init__(self, username: str) -> None:
        self.username = username

    def validate(self) -> bool:
        """Validate user credentials.

        SolidLSP should find references to this method from handler.py.
        """
        return len(self.username) > 0
