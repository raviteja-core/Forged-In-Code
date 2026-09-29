use std::cmp::Ordering;
use std::collections::VecDeque;

use chrono::{DateTime, Utc};
use uuid::Uuid;

use crate::config::SchedulerConfig;

/// A single submission attempt waiting in the scheduler queue.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct QueuedTask {
    pub attempt_id: Uuid,
    pub submission_id: Uuid,
    pub user_id: Uuid,
    pub base_priority: u32,
    pub enqueued_at: DateTime<Utc>,
    pub sequence_number: u64,
}

impl QueuedTask {
    /// Computes effective priority applying aging bonus:
    /// effective_priority = base_priority + min(MAX_AGING_BONUS, floor(wait_seconds / AGING_INTERVAL) * AGING_STEP)
    #[inline]
    pub fn effective_priority(&self, now: DateTime<Utc>, config: &SchedulerConfig) -> u32 {
        let elapsed_secs = (now - self.enqueued_at).num_seconds().max(0) as u64;
        let intervals = elapsed_secs / config.aging_interval_secs.max(1);
        let bonus =
            ((intervals as u32).saturating_mul(config.aging_step)).min(config.max_aging_bonus);
        self.base_priority.saturating_add(bonus)
    }
}

/// FIFO subqueue for a specific tenant (user).
#[derive(Debug, Clone, Default)]
pub struct TenantQueue {
    pub user_id: Uuid,
    pub tasks: VecDeque<QueuedTask>,
}

impl TenantQueue {
    pub fn new(user_id: Uuid) -> Self {
        Self {
            user_id,
            tasks: VecDeque::new(),
        }
    }

    pub fn push_back(&mut self, task: QueuedTask) {
        self.tasks.push_back(task);
    }

    pub fn pop_front(&mut self) -> Option<QueuedTask> {
        self.tasks.pop_front()
    }

    pub fn peek_front(&self) -> Option<&QueuedTask> {
        self.tasks.front()
    }

    pub fn len(&self) -> usize {
        self.tasks.len()
    }

    pub fn is_empty(&self) -> bool {
        self.tasks.is_empty()
    }
}

/// A candidate entry in the scheduler's active max-heap representing the head of a tenant queue.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HeapCandidate {
    pub user_id: Uuid,
    pub effective_priority: u32,
    pub head_enqueued_at: DateTime<Utc>,
    pub head_sequence: u64,
}

impl HeapCandidate {
    pub fn from_task(task: &QueuedTask, now: DateTime<Utc>, config: &SchedulerConfig) -> Self {
        Self {
            user_id: task.user_id,
            effective_priority: task.effective_priority(now, config),
            head_enqueued_at: task.enqueued_at,
            head_sequence: task.sequence_number,
        }
    }
}

impl Ord for HeapCandidate {
    fn cmp(&self, other: &Self) -> Ordering {
        // 1. Highest effective priority first
        self.effective_priority
            .cmp(&other.effective_priority)
            // 2. Tie-break: Older submission first (earlier timestamp wins)
            .then_with(|| other.head_enqueued_at.cmp(&self.head_enqueued_at))
            // 3. Tie-break: Lower monotonic sequence number first
            .then_with(|| other.head_sequence.cmp(&self.head_sequence))
            // 4. Deterministic tie-break by user UUID
            .then_with(|| self.user_id.cmp(&other.user_id))
    }
}

impl PartialOrd for HeapCandidate {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;

    #[test]
    fn test_effective_priority_aging_calculation() {
        let config = SchedulerConfig {
            max_aging_bonus: 30,
            aging_interval_secs: 10,
            aging_step: 5,
            ..Default::default()
        };

        let now = Utc::now();
        let task = QueuedTask {
            attempt_id: Uuid::new_v4(),
            submission_id: Uuid::new_v4(),
            user_id: Uuid::new_v4(),
            base_priority: 20,
            enqueued_at: now - Duration::seconds(25), // 25 seconds wait -> 2 full intervals -> +10
            sequence_number: 1,
        };

        assert_eq!(task.effective_priority(now, &config), 30);

        // Long wait capped at max_aging_bonus (30) -> 20 + 30 = 50
        let old_task = QueuedTask {
            enqueued_at: now - Duration::seconds(1000),
            ..task
        };
        assert_eq!(old_task.effective_priority(now, &config), 50);
    }

    #[test]
    fn test_heap_candidate_ordering_and_tie_breaking() {
        let now = Utc::now();
        let u1 = Uuid::new_v4();
        let u2 = Uuid::new_v4();

        // Higher priority candidate beats lower priority
        let c_high = HeapCandidate {
            user_id: u1,
            effective_priority: 80,
            head_enqueued_at: now,
            head_sequence: 10,
        };
        let c_low = HeapCandidate {
            user_id: u2,
            effective_priority: 40,
            head_enqueued_at: now - Duration::seconds(60),
            head_sequence: 5,
        };
        assert!(c_high > c_low);

        // Same priority: older candidate wins (reverse cmp on timestamp)
        let c_older = HeapCandidate {
            user_id: u1,
            effective_priority: 50,
            head_enqueued_at: now - Duration::seconds(30),
            head_sequence: 15,
        };
        let c_newer = HeapCandidate {
            user_id: u2,
            effective_priority: 50,
            head_enqueued_at: now,
            head_sequence: 10,
        };
        assert!(c_older > c_newer);

        // Same priority and same timestamp: lower sequence number wins
        let c_seq1 = HeapCandidate {
            user_id: u1,
            effective_priority: 50,
            head_enqueued_at: now,
            head_sequence: 1,
        };
        let c_seq2 = HeapCandidate {
            user_id: u2,
            effective_priority: 50,
            head_enqueued_at: now,
            head_sequence: 2,
        };
        assert!(c_seq1 > c_seq2);
    }
}
