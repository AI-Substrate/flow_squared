//! A generic cache implementation with TTL support.
//!
//! Provides thread-safe caching with automatic expiration and eviction policies.
//! Supports multiple eviction strategies: LRU, LFU, and FIFO.

use std::collections::HashMap;
use std::hash::Hash;
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant};

/// Eviction policy for the cache.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum EvictionPolicy {
    /// Least Recently Used - evicts the oldest accessed item
    LRU,
    /// Least Frequently Used - evicts the least accessed item
    LFU,
    /// First In First Out - evicts the oldest inserted item
    FIFO,
}

/// Configuration for the cache.
#[derive(Debug, Clone)]
pub struct CacheConfig {
    /// Maximum number of entries in the cache
    pub max_size: usize,
    /// Time-to-live for cache entries
    pub ttl: Duration,
    /// Eviction policy when cache is full
    pub eviction_policy: EvictionPolicy,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            max_size: 1000,
            ttl: Duration::from_secs(300), // 5 minutes
            eviction_policy: EvictionPolicy::LRU,
        }
    }
}

/// A cache entry with metadata.
#[derive(Debug, Clone)]
struct CacheEntry<V> {
    value: V,
    inserted_at: Instant,
    last_accessed: Instant,
    access_count: u64,
}

impl<V: Clone> CacheEntry<V> {
    fn new(value: V) -> Self {
        let now = Instant::now();
        Self {
            value,
            inserted_at: now,
            last_accessed: now,
            access_count: 1,
        }
    }

    fn is_expired(&self, ttl: Duration) -> bool {
        self.inserted_at.elapsed() > ttl
    }

    fn touch(&mut self) {
        self.last_accessed = Instant::now();
        self.access_count += 1;
    }
}

/// Error types for cache operations.
#[derive(Debug, Clone, PartialEq)]
pub enum CacheError {
    /// The requested key was not found
    NotFound,
    /// The cache entry has expired
    Expired,
    /// The cache is at capacity
    Full,
}

/// A trait for cacheable values.
pub trait Cacheable: Clone + Send + Sync + 'static {}

impl<T: Clone + Send + Sync + 'static> Cacheable for T {}

/// Thread-safe cache with configurable eviction.
pub struct Cache<K, V>
where
    K: Eq + Hash + Clone + Send + Sync,
    V: Cacheable,
{
    config: CacheConfig,
    entries: Arc<RwLock<HashMap<K, CacheEntry<V>>>>,
}

impl<K, V> Cache<K, V>
where
    K: Eq + Hash + Clone + Send + Sync,
    V: Cacheable,
{
    /// Create a new cache with the given configuration.
    pub fn new(config: CacheConfig) -> Self {
        Self {
            config,
            entries: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Create a new cache with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(CacheConfig::default())
    }

    /// Get a value from the cache.
    ///
    /// Returns `None` if the key doesn't exist or has expired.
    pub fn get(&self, key: &K) -> Option<V> {
        let mut entries = self.entries.write().ok()?;

        if let Some(entry) = entries.get_mut(key) {
            if entry.is_expired(self.config.ttl) {
                entries.remove(key);
                return None;
            }
            entry.touch();
            return Some(entry.value.clone());
        }
        None
    }

    /// Insert a value into the cache.
    ///
    /// If the cache is full, an entry will be evicted according to the
    /// configured eviction policy.
    pub fn insert(&self, key: K, value: V) -> Result<(), CacheError> {
        let mut entries = self.entries.write().map_err(|_| CacheError::Full)?;

        // Check if we need to evict
        if entries.len() >= self.config.max_size && !entries.contains_key(&key) {
            self.evict_one(&mut entries);
        }

        entries.insert(key, CacheEntry::new(value));
        Ok(())
    }

    /// Remove a value from the cache.
    pub fn remove(&self, key: &K) -> Option<V> {
        let mut entries = self.entries.write().ok()?;
        entries.remove(key).map(|e| e.value)
    }

    /// Clear all entries from the cache.
    pub fn clear(&self) {
        if let Ok(mut entries) = self.entries.write() {
            entries.clear();
        }
    }

    /// Get the number of entries in the cache.
    pub fn len(&self) -> usize {
        self.entries.read().map(|e| e.len()).unwrap_or(0)
    }

    /// Check if the cache is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Remove expired entries from the cache.
    pub fn cleanup_expired(&self) -> usize {
        let mut entries = match self.entries.write() {
            Ok(e) => e,
            Err(_) => return 0,
        };

        let ttl = self.config.ttl;
        let before = entries.len();
        entries.retain(|_, entry| !entry.is_expired(ttl));
        before - entries.len()
    }

    fn evict_one(&self, entries: &mut HashMap<K, CacheEntry<V>>) {
        let key_to_remove = match self.config.eviction_policy {
            EvictionPolicy::LRU => entries
                .iter()
                .min_by_key(|(_, e)| e.last_accessed)
                .map(|(k, _)| k.clone()),
            EvictionPolicy::LFU => entries
                .iter()
                .min_by_key(|(_, e)| e.access_count)
                .map(|(k, _)| k.clone()),
            EvictionPolicy::FIFO => entries
                .iter()
                .min_by_key(|(_, e)| e.inserted_at)
                .map(|(k, _)| k.clone()),
        };

        if let Some(key) = key_to_remove {
            entries.remove(&key);
        }
    }
}

impl<K, V> Clone for Cache<K, V>
where
    K: Eq + Hash + Clone + Send + Sync,
    V: Cacheable,
{
    fn clone(&self) -> Self {
        Self {
            config: self.config.clone(),
            entries: Arc::clone(&self.entries),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_insert_and_get() {
        let cache = Cache::<String, i32>::with_defaults();
        cache.insert("key".to_string(), 42).unwrap();
        assert_eq!(cache.get(&"key".to_string()), Some(42));
    }

    #[test]
    fn test_eviction() {
        let config = CacheConfig {
            max_size: 2,
            ..Default::default()
        };
        let cache = Cache::<i32, &str>::new(config);
        cache.insert(1, "one").unwrap();
        cache.insert(2, "two").unwrap();
        cache.insert(3, "three").unwrap();
        assert_eq!(cache.len(), 2);
    }
}
