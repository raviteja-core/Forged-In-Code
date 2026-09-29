use std::collections::{BinaryHeap, HashMap, HashSet};

use chrono::{DateTime, Utc};
use thiserror::Error;
use tracing::{debug, info};
use uuid::Uuid;

use forgerun_contracts::{
    ExecutionScheduledEvent, ExecutionScheduledPayload, SubmissionCreatedEvent,
};

use crate::config::SchedulerConfig;
use crate::queue::{HeapCandidate, QueuedTask, TenantQueue};
use crate::quota::QuotaTracker;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum SchedulerError {
    #[error("User pending queue limit exceeded")]
    UserQueueFull,
    #[error("Global queue capacity reached")]
    GlobalQueueFull,
}

#[derive(Debug, PartialEq, Eq)]
pub enum EnqueueResult {
    Enqueued,
    DuplicateSuppressed,
}

/// Advanced partition-aware scheduler engine implementing:
/// - Per-tenant FIFO subqueues
/// - Max-heap candidate priority queue with lazy aging calculation
/// - Concurrency quota enforcement (per-user and global)
/// - Deterministic tie-breaking (timestamp + monotonic sequence)
/// - Idempotent deduplication against duplicate Kafka events
#[derive(Debug)]
pub struct SchedulerEngine {
    pub config: SchedulerConfig,
    tenant_queues: HashMap<Uuid, TenantQueue>,
    candidate_heap: BinaryHeap<HeapCandidate>,
    quota_tracker: QuotaTracker,
    scheduled_attempts: HashSet<Uuid>,
    sequence_counter: u64,
    pub total_enqueued: u64,
    pub total_scheduled: u64,
    pub duplicates_suppressed: u64,
}

impl Default for SchedulerEngine {
    fn default() -> Self {
        Self::new(SchedulerConfig::default())
    }
}

impl SchedulerEngine {
    pub fn new(config: SchedulerConfig) -> Self {
        Self {
            config,
            tenant_queues: HashMap::new(),
            candidate_heap: BinaryHeap::new(),
            quota_tracker: QuotaTracker::new(),
            scheduled_attempts: HashSet::new(),
            sequence_counter: 0,
            total_enqueued: 0,
            total_scheduled: 0,
            duplicates_suppressed: 0,
        }
    }

    /// Enqueues a new submission attempt.
    /// Deduplicates duplicate attempts idempotently.
    pub fn enqueue(
        &mut self,
        event: &SubmissionCreatedEvent,
        now: DateTime<Utc>,
    ) -> Result<EnqueueResult, SchedulerError> {
        let attempt_id = event.payload.attempt_id;
        let user_id = event.payload.user_id;

        // Idempotency: if already scheduled or currently running, suppress duplicate
        if self.scheduled_attempts.contains(&attempt_id)
            || self.quota_tracker.is_attempt_running(&attempt_id)
        {
            self.duplicates_suppressed += 1;
            return Ok(EnqueueResult::DuplicateSuppressed);
        }

        // Check if already queued in tenant's pending queue
        let queue = self
            .tenant_queues
            .entry(user_id)
            .or_insert_with(|| TenantQueue::new(user_id));

        for task in &queue.tasks {
            if task.attempt_id == attempt_id {
                self.duplicates_suppressed += 1;
                return Ok(EnqueueResult::DuplicateSuppressed);
            }
        }

        // Check per-user pending queue limit
        if queue.len() >= self.config.per_user_pending_limit {
            return Err(SchedulerError::UserQueueFull);
        }

        self.sequence_counter += 1;
        let task = QueuedTask {
            attempt_id,
            submission_id: event.payload.submission_id,
            user_id,
            base_priority: event.payload.base_priority,
            enqueued_at: now,
            sequence_number: self.sequence_counter,
        };

        let was_empty = queue.is_empty();
        queue.push_back(task.clone());
        self.total_enqueued += 1;

        // If the tenant had no active tasks before, add this head task to the candidate heap
        if was_empty {
            self.candidate_heap
                .push(HeapCandidate::from_task(&task, now, &self.config));
        }

        Ok(EnqueueResult::Enqueued)
    }

    /// Attempts to dequeue and schedule the highest priority eligible task.
    /// Respects aging, per-tenant FIFO ordering, and concurrency quotas.
    pub fn try_schedule_next(&mut self, now: DateTime<Utc>) -> Option<ExecutionScheduledEvent> {
        // Rebuild candidate heap from active tenant heads using current timestamp
        // Only evaluates M active tenant heads (not all N queued tasks), achieving O(M) lazy refresh
        self.candidate_heap.clear();
        for queue in self.tenant_queues.values() {
            if let Some(head) = queue.peek_front() {
                self.candidate_heap
                    .push(HeapCandidate::from_task(head, now, &self.config));
            }
        }

        let mut deferred: Vec<HeapCandidate> = Vec::new();
        let mut selected_event: Option<ExecutionScheduledEvent> = None;

        while let Some(candidate) = self.candidate_heap.pop() {
            let queue = match self.tenant_queues.get_mut(&candidate.user_id) {
                Some(q) if !q.is_empty() => q,
                _ => continue,
            };

            // Quota check: Can this user and partition run right now?
            if !self
                .quota_tracker
                .can_schedule(&candidate.user_id, &self.config)
            {
                // If global quota is saturated, no candidate can run right now
                if self.quota_tracker.get_global_running() >= self.config.global_max_concurrency {
                    deferred.push(candidate);
                    break;
                }
                // User-specific quota saturated; defer candidate and continue to next user
                deferred.push(candidate);
                continue;
            }

            // Candidate is eligible and within quota: pop and schedule!
            let task = queue.pop_front().unwrap();
            let attempt_id = task.attempt_id;
            let user_id = task.user_id;

            // Acquire quota slot
            self.quota_tracker
                .acquire(attempt_id, user_id, &self.config);
            self.scheduled_attempts.insert(attempt_id);
            self.total_scheduled += 1;

            selected_event = Some(ExecutionScheduledEvent {
                event_id: Uuid::new_v4(),
                event_type: "execution.scheduled".to_string(),
                schema_version: 1,
                occurred_at: now,
                correlation_id: Uuid::new_v4(),
                causation_id: None,
                producer: "forgerun-scheduler".to_string(),
                payload: ExecutionScheduledPayload {
                    attempt_id,
                    submission_id: task.submission_id,
                    user_id,
                    priority: candidate.effective_priority,
                    scheduled_at: now,
                    scheduler_partition: self.config.partition,
                },
            });

            break;
        }

        selected_event
    }

    /// Releases a concurrency slot when an execution attempt finishes.
    /// If the tenant has pending tasks that were blocked by quota, this frees capacity.
    pub fn on_attempt_completed(&mut self, attempt_id: &Uuid, _now: DateTime<Utc>) -> Option<Uuid> {
        let user_id = self.quota_tracker.release(attempt_id)?;
        debug!(attempt_id = %attempt_id, user_id = %user_id, "Released scheduler execution slot");
        Some(user_id)
    }

    /// High-level single event schedule method (compatible with Phase 1 interface).
    /// Enqueues the event and immediately tries to schedule any eligible task.
    pub fn schedule(
        &mut self,
        event: &SubmissionCreatedEvent,
        partition: u32,
    ) -> Option<ExecutionScheduledEvent> {
        self.config.partition = partition;
        let now = Utc::now();
        match self.enqueue(event, now) {
            Ok(EnqueueResult::Enqueued) => self.try_schedule_next(now),
            Ok(EnqueueResult::DuplicateSuppressed) => None,
            Err(err) => {
                info!(error = %err, "Failed to enqueue submission");
                None
            }
        }
    }

    pub fn is_attempt_scheduled(&self, attempt_id: &Uuid) -> bool {
        self.scheduled_attempts.contains(attempt_id)
    }

    pub fn pending_tasks_count(&self) -> usize {
        self.tenant_queues.values().map(|q| q.len()).sum()
    }

    pub fn active_tenants_count(&self) -> usize {
        self.tenant_queues
            .values()
            .filter(|q| !q.is_empty())
            .count()
    }

    pub fn user_running_count(&self, user_id: &Uuid) -> usize {
        self.quota_tracker.get_user_running(user_id)
    }

    pub fn global_running_count(&self) -> usize {
        self.quota_tracker.get_global_running()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;
    use forgerun_contracts::{Language, SubmissionCreatedPayload};

    fn make_test_event(
        submission_id: Uuid,
        attempt_id: Uuid,
        user_id: Uuid,
        base_priority: u32,
    ) -> SubmissionCreatedEvent {
        SubmissionCreatedEvent {
            event_id: Uuid::new_v4(),
            event_type: "submission.created".to_string(),
            schema_version: 1,
            occurred_at: Utc::now(),
            correlation_id: Uuid::new_v4(),
            causation_id: None,
            producer: "api-service".to_string(),
            payload: SubmissionCreatedPayload {
                submission_id,
                attempt_id,
                user_id,
                problem_version_id: Uuid::new_v4(),
                language: Language::Python,
                base_priority,
            },
        }
    }

    #[test]
    fn test_duplicate_kafka_event_does_not_create_second_logical_attempt() {
        let mut engine = SchedulerEngine::default();
        let attempt_id = Uuid::new_v4();
        let event = make_test_event(Uuid::new_v4(), attempt_id, Uuid::new_v4(), 50);

        let res1 = engine.schedule(&event, 0);
        assert!(res1.is_some());
        assert_eq!(res1.unwrap().payload.attempt_id, attempt_id);

        let res2 = engine.schedule(&event, 0);
        assert!(res2.is_none(), "Duplicate delivery must be suppressed");
    }

    #[test]
    fn test_priority_ordering() {
        let mut engine = SchedulerEngine::new(SchedulerConfig {
            per_user_max_concurrency: 10,
            global_max_concurrency: 10,
            ..Default::default()
        });

        let now = Utc::now();
        let u1 = Uuid::new_v4();
        let u2 = Uuid::new_v4();
        let u3 = Uuid::new_v4();

        let e_low = make_test_event(Uuid::new_v4(), Uuid::new_v4(), u1, 10);
        let e_high = make_test_event(Uuid::new_v4(), Uuid::new_v4(), u2, 90);
        let e_mid = make_test_event(Uuid::new_v4(), Uuid::new_v4(), u3, 50);

        engine.enqueue(&e_low, now).unwrap();
        engine.enqueue(&e_high, now).unwrap();
        engine.enqueue(&e_mid, now).unwrap();

        // Highest priority (90) must be scheduled first
        let s1 = engine.try_schedule_next(now).unwrap();
        assert_eq!(s1.payload.attempt_id, e_high.payload.attempt_id);

        // Next mid priority (50)
        let s2 = engine.try_schedule_next(now).unwrap();
        assert_eq!(s2.payload.attempt_id, e_mid.payload.attempt_id);

        // Lowest priority (10)
        let s3 = engine.try_schedule_next(now).unwrap();
        assert_eq!(s3.payload.attempt_id, e_low.payload.attempt_id);
    }

    #[test]
    fn test_aging_prevents_starvation() {
        let mut engine = SchedulerEngine::new(SchedulerConfig {
            max_aging_bonus: 50,
            aging_interval_secs: 5,
            aging_step: 10,
            per_user_max_concurrency: 10,
            global_max_concurrency: 10,
            ..Default::default()
        });

        let t0 = Utc::now();
        let u_old = Uuid::new_v4();
        let u_new = Uuid::new_v4();

        // Low priority task enqueued at t0
        let e_old = make_test_event(Uuid::new_v4(), Uuid::new_v4(), u_old, 20);
        engine.enqueue(&e_old, t0).unwrap();

        // 20 seconds later, higher priority task arrives (base 40)
        let t1 = t0 + Duration::seconds(20);
        let e_new = make_test_event(Uuid::new_v4(), Uuid::new_v4(), u_new, 40);
        engine.enqueue(&e_new, t1).unwrap();

        // At t1:
        // Old task has aged 20s -> 4 intervals * 10 = +40 bonus -> effective priority = 20 + 40 = 60!
        // New task has 0s wait -> effective priority = 40.
        // Old task should win due to aging!
        let scheduled = engine.try_schedule_next(t1).unwrap();
        assert_eq!(
            scheduled.payload.attempt_id, e_old.payload.attempt_id,
            "Older lower-priority task should overtake newer higher-priority task after aging"
        );
        assert_eq!(scheduled.payload.priority, 60);
    }

    #[test]
    fn test_per_user_concurrency_quota_prevents_tenant_monopolization() {
        let mut engine = SchedulerEngine::new(SchedulerConfig {
            per_user_max_concurrency: 2,
            global_max_concurrency: 10,
            ..Default::default()
        });

        let now = Utc::now();
        let u_spam = Uuid::new_v4();
        let u_normal = Uuid::new_v4();

        // u_spam enqueues 4 high-priority tasks (priority 80)
        let spams: Vec<_> = (0..4)
            .map(|_| make_test_event(Uuid::new_v4(), Uuid::new_v4(), u_spam, 80))
            .collect();
        for s in &spams {
            engine.enqueue(s, now).unwrap();
        }

        // u_normal enqueues 1 lower-priority task (priority 50)
        let normal = make_test_event(Uuid::new_v4(), Uuid::new_v4(), u_normal, 50);
        engine.enqueue(&normal, now).unwrap();

        // First 2 scheduled tasks should be u_spam (up to quota of 2)
        let s1 = engine.try_schedule_next(now).unwrap();
        let s2 = engine.try_schedule_next(now).unwrap();
        assert_eq!(s1.payload.user_id, u_spam);
        assert_eq!(s2.payload.user_id, u_spam);
        assert_eq!(engine.user_running_count(&u_spam), 2);

        // u_spam is now at quota! 3rd scheduled task MUST be u_normal despite lower priority!
        let s3 = engine.try_schedule_next(now).unwrap();
        assert_eq!(
            s3.payload.user_id, u_normal,
            "u_normal should be scheduled because u_spam is quota-saturated"
        );

        // No more eligible tasks until u_spam completes one
        assert!(engine.try_schedule_next(now).is_none());

        // u_spam completes task 1
        engine.on_attempt_completed(&s1.payload.attempt_id, now);
        assert_eq!(engine.user_running_count(&u_spam), 1);

        // Now u_spam's 3rd task can be scheduled
        let s4 = engine.try_schedule_next(now).unwrap();
        assert_eq!(s4.payload.user_id, u_spam);
    }
}
