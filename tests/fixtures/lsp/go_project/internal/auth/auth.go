// Package auth provides authentication utilities.
// Line 2: auth package
package auth

import "github.com/example/goproject/pkg/utils"

// AuthService handles authentication.
// Line 8: AuthService struct definition
type AuthService struct {
	token string
}

// NewAuthService creates a new auth service.
// Line 14: NewAuthService function definition
// Line 18: NewAuthService → setup (same-file, constructor-like→private)
func NewAuthService() *AuthService {
	s := &AuthService{}
	s.setup()
	return s
}

// setup initializes the service.
// Line 23: setup method definition
func (s *AuthService) setup() {
	s.token = "default"
}

// Login authenticates a user.
// Line 29: Login method definition
// Line 33: Login → validate (same-file, exported→unexported)
func (s *AuthService) Login(user string) bool {
	return s.validate(user)
}

// validate checks credentials.
// Line 37: validate method definition
// Line 41: validate → checkToken (same-file, chain)
// Line 42: validate → utils.ValidateString (cross-file)
func (s *AuthService) validate(user string) bool {
	tokenOk := s.checkToken(user)
	nameOk := utils.ValidateString(user)
	return tokenOk && nameOk
}

// checkToken verifies token validity.
// Line 47: checkToken method definition
func (s *AuthService) checkToken(user string) bool {
	return s.token != "" && len(user) > 0
}

// Validate is a standalone validation function.
// LSP should find references from main.go.
// Line 54: Validate function definition
func Validate(username string) bool {
	return len(username) > 0
}
