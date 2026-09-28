pub mod enums;
pub mod events;

pub use enums::*;
pub use events::*;

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use uuid::Uuid;

    #[test]
    fn test_submission_created_roundtrip() {
        let event = SubmissionCreatedEvent {
            event_id: Uuid::new_v4(),
            event_type: "submission.created".to_string(),
            schema_version: 1,
            occurred_at: Utc::now(),
            correlation_id: Uuid::new_v4(),
            causation_id: None,
            producer: "api-service".to_string(),
            payload: SubmissionCreatedPayload {
                submission_id: Uuid::new_v4(),
                attempt_id: Uuid::new_v4(),
                user_id: Uuid::new_v4(),
                problem_version_id: Uuid::new_v4(),
                language: Language::Python,
                base_priority: 50,
            },
        };

        let json = serde_json::to_string(&event).expect("Failed to serialize");
        let deserialized: SubmissionCreatedEvent =
            serde_json::from_str(&json).expect("Failed to deserialize");
        assert_eq!(event, deserialized);
    }

    #[test]
    fn test_verdict_serialization() {
        assert_eq!(
            serde_json::to_string(&Verdict::Accepted).unwrap(),
            "\"ACCEPTED\""
        );
        assert_eq!(
            serde_json::to_string(&Verdict::WrongAnswer).unwrap(),
            "\"WRONG_ANSWER\""
        );
        assert_eq!(
            serde_json::to_string(&Verdict::TimeLimit).unwrap(),
            "\"TIME_LIMIT\""
        );
        assert!(Verdict::InfrastructureFailure.is_infrastructure_failure());
        assert!(!Verdict::Accepted.is_infrastructure_failure());
    }

    #[test]
    fn test_language_serialization() {
        assert_eq!(
            serde_json::to_string(&Language::Python).unwrap(),
            "\"python\""
        );
        assert_eq!(serde_json::to_string(&Language::Cpp).unwrap(), "\"cpp\"");
    }
}
