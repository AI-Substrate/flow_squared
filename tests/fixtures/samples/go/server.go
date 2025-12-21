// Package server provides HTTP server implementation with middleware support.
// It includes structured logging, request handling, and graceful shutdown.
package server

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// Config holds server configuration options.
type Config struct {
	Host            string        `json:"host"`
	Port            int           `json:"port"`
	ReadTimeout     time.Duration `json:"read_timeout"`
	WriteTimeout    time.Duration `json:"write_timeout"`
	ShutdownTimeout time.Duration `json:"shutdown_timeout"`
	MaxBodySize     int64         `json:"max_body_size"`
}

// DefaultConfig returns sensible default configuration.
func DefaultConfig() *Config {
	return &Config{
		Host:            "0.0.0.0",
		Port:            8080,
		ReadTimeout:     15 * time.Second,
		WriteTimeout:    15 * time.Second,
		ShutdownTimeout: 30 * time.Second,
		MaxBodySize:     10 << 20, // 10 MB
	}
}

// Response represents a standard API response.
type Response struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
	Meta    *Meta       `json:"meta,omitempty"`
}

// Meta contains response metadata.
type Meta struct {
	RequestID string `json:"request_id"`
	Duration  string `json:"duration"`
	Timestamp string `json:"timestamp"`
}

// HandlerFunc is a type for HTTP handler functions that return errors.
type HandlerFunc func(w http.ResponseWriter, r *http.Request) error

// Middleware wraps a handler with additional functionality.
type Middleware func(HandlerFunc) HandlerFunc

// Server represents an HTTP server with middleware support.
type Server struct {
	config     *Config
	router     *http.ServeMux
	middleware []Middleware
	server     *http.Server
	mu         sync.RWMutex
	started    bool
}

// NewServer creates a new Server instance.
func NewServer(cfg *Config) *Server {
	if cfg == nil {
		cfg = DefaultConfig()
	}

	s := &Server{
		config:     cfg,
		router:     http.NewServeMux(),
		middleware: make([]Middleware, 0),
	}

	return s
}

// Use adds middleware to the server.
func (s *Server) Use(mw Middleware) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.middleware = append(s.middleware, mw)
}

// Handle registers a handler for a path pattern.
func (s *Server) Handle(pattern string, handler HandlerFunc) {
	wrapped := s.wrapHandler(handler)
	s.router.HandleFunc(pattern, wrapped)
}

// wrapHandler applies middleware and error handling to a handler.
func (s *Server) wrapHandler(h HandlerFunc) http.HandlerFunc {
	// Apply middleware in reverse order
	wrapped := h
	for i := len(s.middleware) - 1; i >= 0; i-- {
		wrapped = s.middleware[i](wrapped)
	}

	return func(w http.ResponseWriter, r *http.Request) {
		if err := wrapped(w, r); err != nil {
			s.handleError(w, err)
		}
	}
}

// handleError writes an error response.
func (s *Server) handleError(w http.ResponseWriter, err error) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusInternalServerError)
	json.NewEncoder(w).Encode(Response{
		Success: false,
		Error:   err.Error(),
	})
}

// Start begins listening for HTTP requests.
func (s *Server) Start() error {
	s.mu.Lock()
	if s.started {
		s.mu.Unlock()
		return fmt.Errorf("server already started")
	}
	s.started = true
	s.mu.Unlock()

	addr := fmt.Sprintf("%s:%d", s.config.Host, s.config.Port)

	s.server = &http.Server{
		Addr:         addr,
		Handler:      s.router,
		ReadTimeout:  s.config.ReadTimeout,
		WriteTimeout: s.config.WriteTimeout,
	}

	log.Printf("Starting server on %s", addr)
	return s.server.ListenAndServe()
}

// StartWithGracefulShutdown starts the server and handles shutdown signals.
func (s *Server) StartWithGracefulShutdown() error {
	errChan := make(chan error, 1)

	go func() {
		if err := s.Start(); err != nil && err != http.ErrServerClosed {
			errChan <- err
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	select {
	case err := <-errChan:
		return err
	case sig := <-quit:
		log.Printf("Received signal %v, shutting down...", sig)
		return s.Shutdown()
	}
}

// Shutdown gracefully stops the server.
func (s *Server) Shutdown() error {
	s.mu.RLock()
	if !s.started || s.server == nil {
		s.mu.RUnlock()
		return nil
	}
	s.mu.RUnlock()

	ctx, cancel := context.WithTimeout(context.Background(), s.config.ShutdownTimeout)
	defer cancel()

	log.Println("Shutting down server...")
	return s.server.Shutdown(ctx)
}

// LoggingMiddleware logs request details.
func LoggingMiddleware(next HandlerFunc) HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) error {
		start := time.Now()
		err := next(w, r)
		duration := time.Since(start)

		log.Printf("%s %s %s %v", r.Method, r.URL.Path, r.RemoteAddr, duration)
		return err
	}
}

// RecoveryMiddleware recovers from panics.
func RecoveryMiddleware(next HandlerFunc) HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) (err error) {
		defer func() {
			if rec := recover(); rec != nil {
				log.Printf("Panic recovered: %v", rec)
				err = fmt.Errorf("internal server error")
			}
		}()
		return next(w, r)
	}
}

// JSON writes a JSON response.
func JSON(w http.ResponseWriter, status int, data interface{}) error {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	return json.NewEncoder(w).Encode(data)
}
