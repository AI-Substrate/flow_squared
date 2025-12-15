from functools import wraps


def retry(times: int):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    pass

        return wrapper

    return decorator


class Service:
    @retry(3)
    async def call_api(self, endpoint: str):
        pass

    @property
    def status(self) -> str:
        return "running"

    @classmethod
    def create(cls):
        return cls()
