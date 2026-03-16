"""Domain model classes."""

from dataclasses import dataclass
from enum import Enum


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Task:
    title: str
    priority: Priority
    done: bool = False

    def mark_done(self) -> None:
        self.done = True

    def display(self) -> str:
        status = "✓" if self.done else "○"
        return f"[{status}] {self.title} ({self.priority.value})"
