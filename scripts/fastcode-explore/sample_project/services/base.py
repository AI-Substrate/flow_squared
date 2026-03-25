"""Base service class."""

from ..utils.helpers import Logger


class BaseService:
    """Base class for all services."""

    def __init__(self, name):
        self.logger = Logger(name)

    def health_check(self):
        self.logger.info("Health check OK")
        return True
