using System.Linq;
using System.Collections.Generic;

namespace TaskApp;

public class TaskService
{
    private readonly List<TaskItem> _tasks = new();

    public TaskItem AddTask(string title, Priority priority = Priority.Medium)
    {
        var task = new TaskItem(title, priority);
        _tasks.Add(task);
        return task;
    }

    public bool CompleteTask(string title)
    {
        var task = _tasks.FirstOrDefault(t => t.Title == title);
        if (task == null) return false;
        task.MarkDone();
        return true;
    }

    public List<TaskItem> GetPending()
    {
        return _tasks.Where(t => !t.Done).ToList();
    }

    public string Summary()
    {
        return string.Join("\n", _tasks.Select(t => t.Display()));
    }
}
