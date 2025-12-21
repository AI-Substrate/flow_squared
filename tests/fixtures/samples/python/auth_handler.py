"""Authentication handler for user authentication and authorization.

This module provides secure token-based authentication with support for
JWT validation, session management, and role-based access control.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class AuthRole(Enum):
    """User roles for access control."""

    GUEST = "guest"
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


@dataclass
class AuthToken:
    """Represents an authentication token with expiration."""

    token_id: str
    user_id: str
    role: AuthRole
    issued_at: datetime
    expires_at: datetime
    refresh_token: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def remaining_time(self) -> timedelta:
        """Get remaining time until expiration."""
        if self.is_expired:
            return timedelta(0)
        return self.expires_at - datetime.utcnow()


class AuthenticationError(Exception):
    """Base exception for authentication failures."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message)
        self.code = code


class TokenExpiredError(AuthenticationError):
    """Raised when an authentication token has expired."""

    def __init__(self, token_id: str):
        super().__init__(f"Token {token_id} has expired", "TOKEN_EXPIRED")
        self.token_id = token_id


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    def __init__(self):
        super().__init__("Invalid username or password", "INVALID_CREDENTIALS")


class AuthHandler:
    """Handles user authentication and session management.

    Provides methods for login, logout, token validation, and
    role-based access control checks.

    Attributes:
        token_lifetime: Duration for which tokens remain valid.
        _token_store: Internal storage for active tokens.
    """

    def __init__(self, token_lifetime_hours: int = 24):
        """Initialize the auth handler.

        Args:
            token_lifetime_hours: How long tokens remain valid.
        """
        self.token_lifetime = timedelta(hours=token_lifetime_hours)
        self._token_store: dict[str, AuthToken] = {}

    async def authenticate(
        self, username: str, password: str, role: AuthRole = AuthRole.USER
    ) -> AuthToken:
        """Authenticate a user and create a session token.

        Args:
            username: The user's username.
            password: The user's password.
            role: The role to assign to the session.

        Returns:
            An AuthToken representing the authenticated session.

        Raises:
            InvalidCredentialsError: If authentication fails.
        """
        # In production, validate against a real user store
        if not self._validate_credentials(username, password):
            raise InvalidCredentialsError()

        token = self._create_token(username, role)
        self._token_store[token.token_id] = token
        return token

    async def validate_token(self, token_id: str) -> AuthToken:
        """Validate a token and return its details.

        Args:
            token_id: The token identifier to validate.

        Returns:
            The validated AuthToken.

        Raises:
            AuthenticationError: If token is not found.
            TokenExpiredError: If token has expired.
        """
        token = self._token_store.get(token_id)
        if token is None:
            raise AuthenticationError(f"Token {token_id} not found", "TOKEN_NOT_FOUND")

        if token.is_expired:
            del self._token_store[token_id]
            raise TokenExpiredError(token_id)

        return token

    async def logout(self, token_id: str) -> bool:
        """Invalidate a token and end the session.

        Args:
            token_id: The token to invalidate.

        Returns:
            True if the token was found and removed, False otherwise.
        """
        if token_id in self._token_store:
            del self._token_store[token_id]
            return True
        return False

    def has_permission(self, token: AuthToken, required_role: AuthRole) -> bool:
        """Check if a token has the required permission level.

        Args:
            token: The authentication token to check.
            required_role: The minimum role required.

        Returns:
            True if the token's role meets the requirement.
        """
        role_hierarchy = {
            AuthRole.GUEST: 0,
            AuthRole.USER: 1,
            AuthRole.ADMIN: 2,
            AuthRole.SUPERADMIN: 3,
        }
        return role_hierarchy[token.role] >= role_hierarchy[required_role]

    def _validate_credentials(self, username: str, password: str) -> bool:
        """Validate user credentials (stub implementation)."""
        # In production, check against actual user database
        return len(username) > 0 and len(password) >= 8

    def _create_token(self, user_id: str, role: AuthRole) -> AuthToken:
        """Create a new authentication token."""
        import uuid

        now = datetime.utcnow()
        return AuthToken(
            token_id=str(uuid.uuid4()),
            user_id=user_id,
            role=role,
            issued_at=now,
            expires_at=now + self.token_lifetime,
        )
