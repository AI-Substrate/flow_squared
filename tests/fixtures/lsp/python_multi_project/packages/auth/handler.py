"""Authentication handler using User model."""
from .models import User


def authenticate(username: str) -> bool:
    """Authenticate a user.

    Creates User instance and calls validate() method.
    SolidLSP should detect this cross-file method call.
    """
    user = User(username)
    return user.validate()  # Cross-file method call
