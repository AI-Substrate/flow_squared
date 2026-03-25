"""Service that operates on Items."""

from model import Item


class ItemService:
    """Service for creating and processing items."""

    def create_item(self, name: str, price: float) -> Item:
        return Item(name, price)

    def format_item(self, item: Item) -> str:
        return item.display()
