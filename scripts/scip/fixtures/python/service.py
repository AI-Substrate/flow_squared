"""Task management service."""

from model import Task, Priority


class TaskService:
    def __init__(self) -> None:
        self._tasks: list[Task] = []

    def add_task(self, title: str, priority: Priority = Priority.MEDIUM) -> Task:
        task = Task(title=title, priority=priority)
        self._tasks.append(task)
        return task

    def complete_task(self, title: str) -> bool:
        for task in self._tasks:
            if task.title == title:
                task.mark_done()
                return True
        return False

    def get_pending(self) -> list[Task]:
        return [t for t in self._tasks if not t.done]

    def summary(self) -> str:
        lines = [t.display() for t in self._tasks]
        return "\n".join(lines)
