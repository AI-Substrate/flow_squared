"""Authentication service with method call chains."""

from .utils import validate_string


class AuthService:
    """Authentication service demonstrating various call patterns.

    Line 5: class definition
    """

    def __init__(self) -> None:
        """Initialize and call private setup.

        Line 10: constructor definition
        Line 16: constructor → _setup (same-file, private)
        """
        self._token: str | None = None
        self._setup()

    def _setup(self) -> None:
        """Private setup method.

        Line 19: _setup definition
        """
        self._token = "default"

    def login(self, user: str) -> bool:
        """Login with method chain.

        Line 26: login definition
        Line 32: login → _validate (same-file, public→private)
        """
        return self._validate(user)

    def _validate(self, user: str) -> bool:
        """Validate credentials with chain.

        Line 35: _validate definition
        Line 40: _validate → _check_token (same-file, chain)
        Line 41: _validate → validate_string (cross-file)
        """
        token_ok = self._check_token(user)
        name_ok = validate_string(user)
        return token_ok and name_ok

    def _check_token(self, user: str) -> bool:
        """Check token validity.

        Line 45: _check_token definition
        """
        return self._token is not None and len(user) > 0

    @staticmethod
    def create() -> "AuthService":
        """Factory method calling constructor.

        Line 52: create definition
        Line 58: create → __init__ (same-file, static→constructor)
        """
        return AuthService()
