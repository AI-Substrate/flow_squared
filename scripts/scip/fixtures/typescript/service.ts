import { Task, Priority, createTask, displayTask } from "./model";

export class TaskService {
  private tasks: Task[] = [];

  addTask(title: string, priority: Priority = Priority.Medium): Task {
    const task = createTask(title, priority);
    this.tasks.push(task);
    return task;
  }

  completeTask(title: string): boolean {
    const task = this.tasks.find((t) => t.title === title);
    if (task) {
      task.done = true;
      return true;
    }
    return false;
  }

  getPending(): Task[] {
    return this.tasks.filter((t) => !t.done);
  }

  summary(): string {
    return this.tasks.map(displayTask).join("\n");
  }
}
