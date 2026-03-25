"""Data model for the sample project."""


class Item:
    """A simple item with a name and price."""

    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price

    def display(self) -> str:
        return f"{self.name}: ${self.price:.2f}"
