use chrono::Utc;
use std::collections::HashSet;
use uuid::Uuid;

use forgerun_contracts::{
    ExecutionScheduledEvent, ExecutionScheduledPayload, SubmissionCreatedEvent,
};

/// Core scheduling engine with attempt deduplication and priority calculation.
#[derive(Debug, Default)]
pub struct SchedulerEngine {
    scheduled_attempts: HashSet<Uuid>,
}

impl SchedulerEngine {
    pub fn new() -> Self {
        Self {
            scheduled_attempts: HashSet::new(),
        }
    }

    /// Schedules a submission. If the attempt has already been scheduled (duplicate delivery),
    /// returns None to guarantee idempotency.
    pub fn schedule(
        &mut self,
        event: &SubmissionCreatedEvent,
        partition: u32,
    ) -> Option<ExecutionScheduledEvent> {
        let attempt_id = event.payload.attempt_id;

        // Idempotency: If already scheduled, suppress duplicate logical attempt
        if !self.scheduled_attempts.insert(attempt_id) {
            return None;
        }

        let effective_priority = event.payload.base_priority;

        Some(ExecutionScheduledEvent {
            event_id: Uuid::new_v4(),
            event_type: "execution.scheduled".to_string(),
            schema_version: 1,
            occurred_at: Utc::now(),
            correlation_id: event.correlation_id,
            causation_id: Some(event.event_id),
            producer: "forgerun-scheduler".to_string(),
            payload: ExecutionScheduledPayload {
                attempt_id,
                submission_id: event.payload.submission_id,
                user_id: event.payload.user_id,
                priority: effective_priority,
                scheduled_at: Utc::now(),
                scheduler_partition: partition,
            },
        })
    }

    pub fn is_attempt_scheduled(&self, attempt_id: &Uuid) -> bool {
        self.scheduled_attempts.contains(attempt_id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use forgerun_contracts::{Language, SubmissionCreatedPayload};

    #[test]
    fn test_duplicate_kafka_event_does_not_create_second_logical_attempt() {
        let mut engine = SchedulerEngine::new();
        let attempt_id = Uuid::new_v4();
        let submission_id = Uuid::new_v4();
        let user_id = Uuid::new_v4();

        let event = SubmissionCreatedEvent {
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
                base_priority: 50,
            },
        };

        // First event dispatch must succeed
        let scheduled_1 = engine.schedule(&event, 0);
        assert!(scheduled_1.is_some());
        let res1 = scheduled_1.unwrap();
        assert_eq!(res1.payload.attempt_id, attempt_id);

        // Duplicate delivery of the exact same event must return None (suppressed)
        let scheduled_2 = engine.schedule(&event, 0);
        assert!(
            scheduled_2.is_none(),
            "Duplicate event should not create a second attempt"
        );

        // A retry with a new attempt_id must schedule
        let mut event2 = event.clone();
        let attempt_id2 = Uuid::new_v4();
        event2.payload.attempt_id = attempt_id2;
        let scheduled_3 = engine.schedule(&event2, 0);
        assert!(scheduled_3.is_some());
        assert_eq!(scheduled_3.unwrap().payload.attempt_id, attempt_id2);
    }
}
