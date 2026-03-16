package service

import (
	"example.com/taskapp/model"
	"strings"
)

type TaskService struct {
	tasks []*model.Task
}

func NewTaskService() *TaskService {
	return &TaskService{tasks: make([]*model.Task, 0)}
}

func (s *TaskService) AddTask(title string, priority model.Priority) *model.Task {
	task := model.NewTask(title, priority)
	s.tasks = append(s.tasks, task)
	return task
}

func (s *TaskService) CompleteTask(title string) bool {
	for _, task := range s.tasks {
		if task.Title == title {
			task.MarkDone()
			return true
		}
	}
	return false
}

func (s *TaskService) GetPending() []*model.Task {
	var pending []*model.Task
	for _, task := range s.tasks {
		if !task.Done {
			pending = append(pending, task)
		}
	}
	return pending
}

func (s *TaskService) Summary() string {
	var lines []string
	for _, task := range s.tasks {
		lines = append(lines, task.Display())
	}
	return strings.Join(lines, "\n")
}
