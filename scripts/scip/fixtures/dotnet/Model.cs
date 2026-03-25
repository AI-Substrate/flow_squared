namespace TaskApp;

public enum Priority
{
    Low,
    Medium,
    High
}

public class TaskItem
{
    public string Title { get; }
    public Priority Priority { get; }
    public bool Done { get; private set; }

    public TaskItem(string title, Priority priority)
    {
        Title = title;
        Priority = priority;
        Done = false;
    }

    public void MarkDone()
    {
        Done = true;
    }

    public string Display()
    {
        var status = Done ? "✓" : "○";
        return $"[{status}] {Title} ({Priority.ToString().ToLower()})";
    }
}
