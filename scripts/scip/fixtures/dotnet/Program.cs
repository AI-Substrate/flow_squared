using TaskApp;

var svc = new TaskService();
svc.AddTask("Write tests", Priority.High);
svc.AddTask("Review PR", Priority.Medium);
svc.CompleteTask("Write tests");

Console.WriteLine(svc.Summary());
Console.WriteLine($"Pending: {svc.GetPending().Count}");
