# Auth package for LSP cross-file reference testing
from .models import User
from .handler import authenticate

__all__ = ["User", "authenticate"]
