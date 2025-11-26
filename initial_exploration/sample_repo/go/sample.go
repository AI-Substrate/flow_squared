// Package sample demonstrates Go constructs for tree-sitter exploration.
package sample

import (
	"context"
	"errors"
	"fmt"
	"sync"
)

// Constants
const (
	MaxSize    = 100
	DefaultTTL = 3600
)

// Type alias
type ID = string

// Custom type
type Status int

const (
	Pending Status = iota
	Active
	Inactive
)

// Interface definition
type Repository interface {
	Find(ctx context.Context, id ID) (*User, error)
	Save(ctx context.Context, user *User) error
	Delete(ctx context.Context, id ID) error
}

// Struct definition
type User struct {
	ID        ID
	Name      string
	Email     string
	Status    Status
	metadata  map[string]any // unexported field
}

// Constructor function
func NewUser(id ID, name string) *User {
	return &User{
		ID:       id,
		Name:     name,
		Status:   Pending,
		metadata: make(map[string]any),
	}
}

// Method with pointer receiver
func (u *User) SetEmail(email string) {
	u.Email = email
}

// Method with value receiver
func (u User) FullName() string {
	return u.Name
}

// Struct embedding (composition)
type AdminUser struct {
	User
	Permissions []string
}

// Generic struct (Go 1.18+)
type Cache[K comparable, V any] struct {
	mu    sync.RWMutex
	items map[K]V
}

// Generic method
func (c *Cache[K, V]) Get(key K) (V, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	val, ok := c.items[key]
	return val, ok
}

func (c *Cache[K, V]) Set(key K, value V) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items[key] = value
}

// Generic function
func Map[T, U any](slice []T, f func(T) U) []U {
	result := make([]U, len(slice))
	for i, v := range slice {
		result[i] = f(v)
	}
	return result
}

// Interface implementation check
var _ Repository = (*InMemoryRepo)(nil)

// Implementing interface
type InMemoryRepo struct {
	users map[ID]*User
	mu    sync.RWMutex
}

func (r *InMemoryRepo) Find(ctx context.Context, id ID) (*User, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	user, ok := r.users[id]
	if !ok {
		return nil, errors.New("user not found")
	}
	return user, nil
}

func (r *InMemoryRepo) Save(ctx context.Context, user *User) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.users[user.ID] = user
	return nil
}

func (r *InMemoryRepo) Delete(ctx context.Context, id ID) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.users, id)
	return nil
}

// Goroutine and channel example
func ProcessAsync(items []string) <-chan string {
	out := make(chan string)
	go func() {
		defer close(out)
		for _, item := range items {
			out <- fmt.Sprintf("processed: %s", item)
		}
	}()
	return out
}

// Select statement
func ProcessWithTimeout(ctx context.Context, ch <-chan string) (string, error) {
	select {
	case val := <-ch:
		return val, nil
	case <-ctx.Done():
		return "", ctx.Err()
	}
}

// Defer, panic, recover
func SafeExecute(f func()) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("panic recovered: %v", r)
		}
	}()
	f()
	return nil
}

// Init function
func init() {
	fmt.Println("Package initialized")
}
