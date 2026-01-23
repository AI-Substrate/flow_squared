# Auth package for LSP cross-file reference testing
from .handler import authenticate
from .models import User

__all__ = ["User", "authenticate"]
