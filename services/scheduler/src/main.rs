pub mod engine;

use std::env;
use std::time::Duration;

use engine::SchedulerEngine;
use forgerun_contracts::SubmissionCreatedEvent;
use rdkafka::config::ClientConfig;
use rdkafka::consumer::{CommitMode, Consumer, StreamConsumer};
use rdkafka::message::Message;
use rdkafka::producer::{FutureProducer, FutureRecord};
use tracing::{error, info, warn};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    let brokers = env::var("KAFKA_BROKERS").unwrap_or_else(|_| "localhost:9092".to_string());
    let group_id =
        env::var("SCHEDULER_GROUP_ID").unwrap_or_else(|_| "forgerun-scheduler".to_string());
    let input_topic = env::var("KAFKA_TOPIC_SUBMISSION_CREATED")
        .unwrap_or_else(|_| "forge.submission.created.v1".to_string());
    let output_topic = env::var("KAFKA_TOPIC_EXECUTION_SCHEDULED")
        .unwrap_or_else(|_| "forge.execution.scheduled.v1".to_string());

    info!(
        brokers = %brokers,
        group_id = %group_id,
        input_topic = %input_topic,
        output_topic = %output_topic,
        "Starting ForgeRun Scheduler service"
    );

    // Initialize Kafka Consumer
    let consumer: StreamConsumer = ClientConfig::new()
        .set("bootstrap.servers", &brokers)
        .set("group.id", &group_id)
        .set("enable.auto.commit", "false")
        .set("auto.offset.reset", "earliest")
        .create()?;

    consumer.subscribe(&[&input_topic])?;

    // Initialize Kafka Producer
    let producer: FutureProducer = ClientConfig::new()
        .set("bootstrap.servers", &brokers)
        .set("message.timeout.ms", "5000")
        .create()?;

    let mut engine = SchedulerEngine::new();

    info!("Scheduler subscribed and waiting for events...");

    loop {
        match consumer.recv().await {
            Ok(msg) => {
                let payload = match msg.payload() {
                    Some(bytes) => bytes,
                    None => {
                        warn!("Received empty message, committing offset");
                        let _ = consumer.commit_message(&msg, CommitMode::Async);
                        continue;
                    }
                };

                let event: SubmissionCreatedEvent = match serde_json::from_slice(payload) {
                    Ok(ev) => ev,
                    Err(err) => {
                        error!(error = %err, "Failed to deserialize SubmissionCreatedEvent");
                        let _ = consumer.commit_message(&msg, CommitMode::Async);
                        continue;
                    }
                };

                let attempt_id = event.payload.attempt_id;
                let partition = msg.partition() as u32;

                if let Some(scheduled_event) = engine.schedule(&event, partition) {
                    let key = attempt_id.to_string();
                    let payload_json = serde_json::to_string(&scheduled_event)?;

                    let record = FutureRecord::to(&output_topic)
                        .key(&key)
                        .payload(&payload_json);

                    match producer.send(record, Duration::from_secs(5)).await {
                        Ok(_) => {
                            info!(
                                attempt_id = %attempt_id,
                                submission_id = %event.payload.submission_id,
                                priority = scheduled_event.payload.priority,
                                "Successfully scheduled execution attempt"
                            );
                            let _ = consumer.commit_message(&msg, CommitMode::Async);
                        }
                        Err((err, _)) => {
                            error!(attempt_id = %attempt_id, error = %err, "Failed to publish ExecutionScheduledEvent");
                        }
                    }
                } else {
                    info!(
                        attempt_id = %attempt_id,
                        "Suppressed duplicate scheduling attempt"
                    );
                    let _ = consumer.commit_message(&msg, CommitMode::Async);
                }
            }
            Err(err) => {
                error!(error = %err, "Kafka consumer receive error");
                tokio::time::sleep(Duration::from_millis(500)).await;
            }
        }
    }
}
