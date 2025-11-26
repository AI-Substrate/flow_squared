//! Sample Rust file for tree-sitter exploration.
//! Includes various Rust constructs.

use std::collections::HashMap;
use std::fmt::{self, Display};
use std::sync::{Arc, Mutex};

/// Custom error type
#[derive(Debug)]
pub enum AppError {
    NotFound(String),
    InvalidInput { field: String, message: String },
    Internal(Box<dyn std::error::Error>),
}

impl Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AppError::NotFound(id) => write!(f, "Not found: {}", id),
            AppError::InvalidInput { field, message } => {
                write!(f, "Invalid {}: {}", field, message)
            }
            AppError::Internal(e) => write!(f, "Internal error: {}", e),
        }
    }
}

impl std::error::Error for AppError {}

/// A trait defining repository behavior
pub trait Repository<T> {
    fn find(&self, id: &str) -> Result<Option<T>, AppError>;
    fn save(&mut self, item: T) -> Result<(), AppError>;
    fn delete(&mut self, id: &str) -> Result<bool, AppError>;
}

/// User struct with derive macros
#[derive(Debug, Clone, PartialEq)]
pub struct User {
    pub id: String,
    pub name: String,
    pub email: Option<String>,
    status: Status,
}

/// Status enum
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Pending,
    Active,
    Inactive,
}

impl Default for Status {
    fn default() -> Self {
        Status::Pending
    }
}

impl User {
    /// Constructor
    pub fn new(id: impl Into<String>, name: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            name: name.into(),
            email: None,
            status: Status::default(),
        }
    }

    /// Builder pattern method
    pub fn with_email(mut self, email: impl Into<String>) -> Self {
        self.email = Some(email.into());
        self
    }

    /// Getter
    pub fn status(&self) -> Status {
        self.status
    }

    /// Setter
    pub fn set_status(&mut self, status: Status) {
        self.status = status;
    }
}

/// Generic struct with lifetime
pub struct Cache<'a, K, V> {
    items: HashMap<K, V>,
    name: &'a str,
}

impl<'a, K, V> Cache<'a, K, V>
where
    K: std::hash::Hash + Eq,
{
    pub fn new(name: &'a str) -> Self {
        Self {
            items: HashMap::new(),
            name,
        }
    }

    pub fn get(&self, key: &K) -> Option<&V> {
        self.items.get(key)
    }

    pub fn insert(&mut self, key: K, value: V) -> Option<V> {
        self.items.insert(key, value)
    }
}

/// In-memory repository implementation
pub struct InMemoryRepo {
    users: Arc<Mutex<HashMap<String, User>>>,
}

impl InMemoryRepo {
    pub fn new() -> Self {
        Self {
            users: Arc::new(Mutex::new(HashMap::new())),
        }
    }
}

impl Repository<User> for InMemoryRepo {
    fn find(&self, id: &str) -> Result<Option<User>, AppError> {
        let users = self.users.lock().map_err(|_| {
            AppError::Internal("Lock poisoned".into())
        })?;
        Ok(users.get(id).cloned())
    }

    fn save(&mut self, item: User) -> Result<(), AppError> {
        let mut users = self.users.lock().map_err(|_| {
            AppError::Internal("Lock poisoned".into())
        })?;
        users.insert(item.id.clone(), item);
        Ok(())
    }

    fn delete(&mut self, id: &str) -> Result<bool, AppError> {
        let mut users = self.users.lock().map_err(|_| {
            AppError::Internal("Lock poisoned".into())
        })?;
        Ok(users.remove(id).is_some())
    }
}

/// Async function
pub async fn fetch_user(id: &str) -> Result<User, AppError> {
    // Simulated async operation
    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
    Ok(User::new(id, "Fetched User"))
}

/// Macro definition
macro_rules! create_user {
    ($id:expr, $name:expr) => {
        User::new($id, $name)
    };
    ($id:expr, $name:expr, $email:expr) => {
        User::new($id, $name).with_email($email)
    };
}

/// Pattern matching example
pub fn process_status(status: Status) -> &'static str {
    match status {
        Status::Pending => "Waiting...",
        Status::Active => "Running!",
        Status::Inactive => "Stopped.",
    }
}

/// Closure example
pub fn apply_transform<F>(users: Vec<User>, f: F) -> Vec<String>
where
    F: Fn(&User) -> String,
{
    users.iter().map(|u| f(u)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_user_creation() {
        let user = User::new("1", "Alice");
        assert_eq!(user.name, "Alice");
        assert_eq!(user.status(), Status::Pending);
    }

    #[test]
    fn test_macro() {
        let user = create_user!("2", "Bob", "bob@example.com");
        assert!(user.email.is_some());
    }
}
