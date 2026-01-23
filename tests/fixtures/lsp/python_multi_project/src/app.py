"""Main application demonstrating cross-file method calls."""
from .auth import AuthService
from .utils import format_date


def main() -> None:
    """Entry point with cross-file calls.
    
    Line 6: main definition
    Line 12: main → AuthService.create (cross-file, function→static)
    Line 13: main → auth.login (cross-file, function→instance method)
    Line 14: main → format_date (cross-file, function→function)
    """
    auth = AuthService.create()
    result = auth.login("testuser")
    date = format_date()
    print(f"Login: {result}, Date: {date}")


def process_user(username: str) -> bool:
    """Process a user with cross-file call.
    
    Line 19: process_user definition
    Line 24: process_user → AuthService (cross-file, instantiation)
    Line 25: process_user → auth.login (cross-file)
    """
    auth = AuthService()
    return auth.login(username)


if __name__ == "__main__":
    main()
