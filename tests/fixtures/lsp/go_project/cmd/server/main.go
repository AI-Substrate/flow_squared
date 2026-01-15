package main

import (
	"fmt"
	"github.com/example/goproject/internal/auth"
)

func main() {
	// Cross-file function call - SolidLSP should detect this
	isValid := auth.Validate("testuser")
	fmt.Printf("Valid: %v\n", isValid)
}
