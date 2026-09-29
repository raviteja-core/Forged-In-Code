use std::collections::HashMap;
use uuid::Uuid;

use crate::config::SchedulerConfig;

/// Manages per-tenant and global concurrency quotas.
#[derive(Debug, Clone, Default)]
pub struct QuotaTracker {
    /// Active running attempts per user
    user_running: HashMap<Uuid, usize>,
    /// Global active running attempts
    global_running: usize,
    /// Maps running attempt_id -> user_id for slot release on completion
    running_attempts: HashMap<Uuid, Uuid>,
}

impl QuotaTracker {
    pub fn new() -> Self {
        Self::default()
    }

    /// Checks if a user has available execution capacity under both per-user and global limits.
    pub fn can_schedule(&self, user_id: &Uuid, config: &SchedulerConfig) -> bool {
        if self.global_running >= config.global_max_concurrency {
            return false;
        }
        let user_count = self.user_running.get(user_id).copied().unwrap_or(0);
        user_count < config.per_user_max_concurrency
    }

    /// Attempts to acquire an execution slot for an attempt.
    pub fn acquire(&mut self, attempt_id: Uuid, user_id: Uuid, config: &SchedulerConfig) -> bool {
        if !self.can_schedule(&user_id, config) {
            return false;
        }

        *self.user_running.entry(user_id).or_insert(0) += 1;
        self.global_running += 1;
        self.running_attempts.insert(attempt_id, user_id);
        true
    }

    /// Releases an execution slot when an attempt completes or fails.
    /// Returns the user_id whose slot was released, if found.
    pub fn release(&mut self, attempt_id: &Uuid) -> Option<Uuid> {
        let user_id = self.running_attempts.remove(attempt_id)?;

        if self.global_running > 0 {
            self.global_running -= 1;
        }

        if let Some(count) = self.user_running.get_mut(&user_id) {
            if *count > 1 {
                *count -= 1;
            } else {
                self.user_running.remove(&user_id);
            }
        }

        Some(user_id)
    }

    pub fn get_user_running(&self, user_id: &Uuid) -> usize {
        self.user_running.get(user_id).copied().unwrap_or(0)
    }

    pub fn get_global_running(&self) -> usize {
        self.global_running
    }

    pub fn is_attempt_running(&self, attempt_id: &Uuid) -> bool {
        self.running_attempts.contains_key(attempt_id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_quota_tracker_limits_and_releases() {
        let mut tracker = QuotaTracker::new();
        let config = SchedulerConfig {
            per_user_max_concurrency: 2,
            global_max_concurrency: 3,
            ..Default::default()
        };

        let u1 = Uuid::new_v4();
        let u2 = Uuid::new_v4();

        let a1 = Uuid::new_v4();
        let a2 = Uuid::new_v4();
        let a3 = Uuid::new_v4();
        let a4 = Uuid::new_v4();

        // User 1 acquires slot 1 and 2
        assert!(tracker.acquire(a1, u1, &config));
        assert!(tracker.acquire(a2, u1, &config));
        // User 1 reaches per-user quota of 2
        assert!(!tracker.can_schedule(&u1, &config));
        assert!(!tracker.acquire(a3, u1, &config));

        // User 2 acquires slot 3 (hitting global max of 3)
        assert!(tracker.can_schedule(&u2, &config));
        assert!(tracker.acquire(a4, u2, &config));

        // Global capacity full
        assert!(!tracker.can_schedule(&u2, &config));

        // Release slot for User 1
        assert_eq!(tracker.release(&a1), Some(u1));
        assert_eq!(tracker.get_user_running(&u1), 1);
        assert_eq!(tracker.get_global_running(), 2);

        // User 1 can now acquire again
        assert!(tracker.can_schedule(&u1, &config));
        assert!(tracker.acquire(a3, u1, &config));
    }
}
