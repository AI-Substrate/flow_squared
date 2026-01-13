"""Application service orchestrating authentication and data parsing.

This module demonstrates cross-file relationships for fs2 experimentation:
- Cross-file imports from auth_handler.py and data_parser.py
- Constructor calls (AuthHandler, JSONParser)
- Method calls (validate_token, parse)
"""

from auth_handler import AuthHandler, AuthToken, AuthRole
from data_parser import JSONParser, ParseResult


class AppService:
    """Orchestrates authentication and data parsing operations.

    Attributes:
        auth: Handler for authentication operations.
        parser: Parser for JSON data processing.
    """

    def __init__(self, token_lifetime_hours: int = 24):
        """Initialize the application service.

        Args:
            token_lifetime_hours: Token validity duration in hours.
        """
        self.auth = AuthHandler(token_lifetime_hours)
        self.parser = JSONParser()

    async def process_request(
        self, token_id: str, data: str
    ) -> ParseResult[dict[str, any]]:
        """Process an authenticated request with JSON data.

        Args:
            token_id: The authentication token identifier.
            data: JSON string to parse.

        Returns:
            ParseResult containing parsed data or errors.

        Raises:
            ValueError: If token is expired.
            AuthenticationError: If token is invalid.
        """
        # Validate the authentication token
        token = await self.auth.validate_token(token_id)

        if token.is_expired:
            raise ValueError("Token expired")

        # Parse the request data
        return self.parser.parse(data)

    async def authenticate_and_parse(
        self,
        username: str,
        password: str,
        data: str,
        role: AuthRole = AuthRole.USER,
    ) -> tuple[AuthToken, ParseResult[dict[str, any]]]:
        """Authenticate a user and parse their data in one operation.

        Args:
            username: User's username.
            password: User's password.
            data: JSON data to parse after authentication.
            role: Role to assign to the session.

        Returns:
            Tuple of (AuthToken, ParseResult).
        """
        # Authenticate the user
        token = await self.auth.authenticate(username, password, role)

        # Parse the data
        result = self.parser.parse(data)

        return token, result

    def check_admin_permission(self, token: AuthToken) -> bool:
        """Check if a token has admin permissions.

        Args:
            token: The authentication token to check.

        Returns:
            True if the token has admin or higher privileges.
        """
        return self.auth.has_permission(token, AuthRole.ADMIN)
