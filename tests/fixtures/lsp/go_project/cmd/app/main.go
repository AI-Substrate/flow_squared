// Main application demonstrating cross-file method calls.
// Line 2: main package
package main

import (
	"fmt"
	"github.com/example/goproject/internal/auth"
	"github.com/example/goproject/pkg/utils"
)

// main is the entry point with cross-file calls.
// Line 12: main function definition
// Line 16: main → auth.NewAuthService (cross-file, function→constructor-like)
// Line 17: main → s.Login (cross-file, function→method)
// Line 18: main → utils.FormatDate (cross-file, function→function)
func main() {
	s := auth.NewAuthService()
	result := s.Login("testuser")
	date := utils.FormatDate(nil)
	fmt.Printf("Login: %v, Date: %s\n", result, date)
}

// processUser handles user processing.
// Line 23: processUser function definition
// Line 27: processUser → auth.NewAuthService (cross-file)
// Line 28: processUser → s.Login (cross-file)
func processUser(username string) bool {
	s := auth.NewAuthService()
	return s.Login(username)
}
