// Package utils provides utility functions.
// Line 1: utils package
package utils

import "time"

// FormatDate formats a time for display.
// LSP should find references from main.go.
// Line 9: FormatDate function definition
func FormatDate(t *time.Time) string {
	if t == nil {
		now := time.Now()
		t = &now
	}
	return t.Format("2006-01-02") // Line 15
}

// ValidateString checks if a string is not empty.
// LSP should find references from auth service.
// Line 20: ValidateString function definition
func ValidateString(value string) bool {
	return len(value) > 0 // Line 23
}
