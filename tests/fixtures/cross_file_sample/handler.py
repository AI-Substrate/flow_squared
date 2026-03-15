"""Handler that uses the service."""

from service import ItemService


def handle_request(name: str, price: float) -> str:
    svc = ItemService()
    item = svc.create_item(name, price)
    return svc.format_item(item)
