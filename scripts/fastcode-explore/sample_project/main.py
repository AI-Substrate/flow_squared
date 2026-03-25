"""Main entry point."""

from .services.data_service import DataService


def main():
    service = DataService()
    service.health_check()
    result = service.process(["hello", "world"])
    print(result)


if __name__ == "__main__":
    main()
