// Package auth provides authentication utilities.
package auth

// Validate checks if credentials are valid.
// SolidLSP should find references to this function from main.go.
func Validate(username string) bool {
	return len(username) > 0
}
