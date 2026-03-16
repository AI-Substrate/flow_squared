package model

import "fmt"

type Priority int

const (
	Low    Priority = iota
	Medium
	High
)

func (p Priority) String() string {
	switch p {
	case Low:
		return "low"
	case Medium:
		return "medium"
	case High:
		return "high"
	default:
		return "unknown"
	}
}

type Task struct {
	Title    string
	Priority Priority
	Done     bool
}

func NewTask(title string, priority Priority) *Task {
	return &Task{Title: title, Priority: priority, Done: false}
}

func (t *Task) MarkDone() {
	t.Done = true
}

func (t *Task) Display() string {
	status := "○"
	if t.Done {
		status = "✓"
	}
	return fmt.Sprintf("[%s] %s (%s)", status, t.Title, t.Priority)
}
