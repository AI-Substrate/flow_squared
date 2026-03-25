export enum Priority {
  Low = "low",
  Medium = "medium",
  High = "high",
}

export interface Task {
  title: string;
  priority: Priority;
  done: boolean;
}

export function createTask(title: string, priority: Priority = Priority.Medium): Task {
  return { title, priority, done: false };
}

export function displayTask(task: Task): string {
  const status = task.done ? "✓" : "○";
  return `[${status}] ${task.title} (${task.priority})`;
}
