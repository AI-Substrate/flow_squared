import { TaskService } from "./service";
import { Priority } from "./model";

interface CreateResult {
  status: string;
  task: string;
}

interface ListResult {
  tasks: string;
  pending: number;
}

export function handleCreate(title: string, priorityStr: string): CreateResult {
  const svc = new TaskService();
  const priority = priorityStr as Priority;
  const task = svc.addTask(title, priority);
  return { status: "created", task: `${task.title} (${task.priority})` };
}

export function handleList(): ListResult {
  const svc = new TaskService();
  return { tasks: svc.summary(), pending: svc.getPending().length };
}
