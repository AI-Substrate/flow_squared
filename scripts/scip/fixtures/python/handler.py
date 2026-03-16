"""Request handler using TaskService."""

from service import TaskService
from model import Priority


def handle_create(title: str, priority_str: str) -> dict:
    svc = TaskService()
    priority = Priority(priority_str)
    task = svc.add_task(title, priority)
    return {"status": "created", "task": task.display()}


def handle_list() -> dict:
    svc = TaskService()
    return {"tasks": svc.summary(), "pending": len(svc.get_pending())}


if __name__ == "__main__":
    result = handle_create("Write tests", "high")
    print(result)
