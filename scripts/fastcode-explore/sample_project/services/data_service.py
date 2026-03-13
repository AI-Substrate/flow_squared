"""Data processing service."""

from .base import BaseService
from ..utils.helpers import validate, format_output


class DataService(BaseService):
    """Process and transform data."""

    def __init__(self):
        super().__init__("DataService")

    def process(self, data):
        validate(data)
        self.logger.info(f"Processing {len(data)} items")
        result = self._transform(data)
        return format_output(result)

    def _transform(self, data):
        return [item.upper() for item in data]
