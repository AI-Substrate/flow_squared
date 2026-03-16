package main

import (
	"fmt"
	"example.com/taskapp/model"
	"example.com/taskapp/service"
)

type CreateResult struct {
	Status string
	Task   string
}

type ListResult struct {
	Tasks   string
	Pending int
}

func HandleCreate(title string, priorityStr string) CreateResult {
	svc := service.NewTaskService()
	var priority model.Priority
	switch priorityStr {
	case "low":
		priority = model.Low
	case "high":
		priority = model.High
	default:
		priority = model.Medium
	}
	task := svc.AddTask(title, priority)
	return CreateResult{Status: "created", Task: task.Display()}
}

func HandleList() ListResult {
	svc := service.NewTaskService()
	return ListResult{Tasks: svc.Summary(), Pending: len(svc.GetPending())}
}

func main() {
	result := HandleCreate("Write tests", "high")
	fmt.Printf("Status: %s, Task: %s\n", result.Status, result.Task)
}
