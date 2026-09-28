use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::enums::{FailureType, Language, Verdict};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EventEnvelope<T> {
    pub event_id: Uuid,
    pub event_type: String,
    pub schema_version: u32,
    pub occurred_at: DateTime<Utc>,
    pub correlation_id: Uuid,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub causation_id: Option<Uuid>,
    pub producer: String,
    pub payload: T,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SubmissionCreatedPayload {
    pub submission_id: Uuid,
    pub attempt_id: Uuid,
    pub user_id: Uuid,
    pub problem_version_id: Uuid,
    pub language: Language,
    #[serde(default = "default_priority")]
    pub base_priority: u32,
}

fn default_priority() -> u32 {
    50
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionScheduledPayload {
    pub attempt_id: Uuid,
    pub submission_id: Uuid,
    pub user_id: Uuid,
    pub priority: u32,
    pub scheduled_at: DateTime<Utc>,
    pub scheduler_partition: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionStartedPayload {
    pub attempt_id: Uuid,
    pub submission_id: Uuid,
    pub pod_name: String,
    pub node_name: String,
    pub started_at: DateTime<Utc>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionCompletedPayload {
    pub attempt_id: Uuid,
    pub submission_id: Uuid,
    pub verdict: Verdict,
    pub execution_ms: u64,
    pub cpu_ms: u64,
    pub peak_memory_bytes: u64,
    pub tests_passed: u32,
    pub tests_total: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub artifact_uri: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExecutionFailedPayload {
    pub attempt_id: Uuid,
    pub submission_id: Uuid,
    pub failure_type: FailureType,
    pub error_message: String,
    pub retryable: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

pub type SubmissionCreatedEvent = EventEnvelope<SubmissionCreatedPayload>;
pub type ExecutionScheduledEvent = EventEnvelope<ExecutionScheduledPayload>;
pub type ExecutionStartedEvent = EventEnvelope<ExecutionStartedPayload>;
pub type ExecutionCompletedEvent = EventEnvelope<ExecutionCompletedPayload>;
pub type ExecutionFailedEvent = EventEnvelope<ExecutionFailedPayload>;
