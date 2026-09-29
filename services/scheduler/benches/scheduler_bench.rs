use chrono::Utc;
use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use forgerun_contracts::{Language, SubmissionCreatedEvent, SubmissionCreatedPayload};
use forgerun_scheduler::{SchedulerConfig, SchedulerEngine};
use uuid::Uuid;

fn make_event(user_id: Uuid, priority: u32) -> SubmissionCreatedEvent {
    SubmissionCreatedEvent {
        event_id: Uuid::new_v4(),
        event_type: "submission.created".to_string(),
        schema_version: 1,
        occurred_at: Utc::now(),
        correlation_id: Uuid::new_v4(),
        causation_id: None,
        producer: "bench".to_string(),
        payload: SubmissionCreatedPayload {
            submission_id: Uuid::new_v4(),
            attempt_id: Uuid::new_v4(),
            user_id,
            problem_version_id: Uuid::new_v4(),
            language: Language::Python,
            base_priority: priority,
        },
    }
}

fn bench_enqueue(c: &mut Criterion) {
    let mut group = c.benchmark_group("scheduler_enqueue");

    for tenant_count in [10, 100, 500] {
        let tenants: Vec<Uuid> = (0..tenant_count).map(|_| Uuid::new_v4()).collect();
        let events: Vec<_> = (0..1000)
            .map(|i| make_event(tenants[i % tenant_count], (i % 100) as u32))
            .collect();

        group.bench_with_input(
            BenchmarkId::new("tenants", tenant_count),
            &events,
            |b, evs| {
                b.iter(|| {
                    let mut engine = SchedulerEngine::new(SchedulerConfig {
                        per_user_pending_limit: 10000,
                        ..Default::default()
                    });
                    let now = Utc::now();
                    for ev in evs {
                        let _ = engine.enqueue(black_box(ev), now);
                    }
                });
            },
        );
    }
    group.finish();
}

fn bench_dequeue(c: &mut Criterion) {
    let mut group = c.benchmark_group("scheduler_dequeue");

    for count in [100, 1000, 5000] {
        group.bench_with_input(BenchmarkId::new("tasks", count), &count, |b, &n| {
            b.iter_batched(
                || {
                    let mut engine = SchedulerEngine::new(SchedulerConfig {
                        per_user_pending_limit: 10000,
                        per_user_max_concurrency: 10000,
                        global_max_concurrency: 10000,
                        ..Default::default()
                    });
                    let now = Utc::now();
                    let tenants: Vec<Uuid> = (0..50).map(|_| Uuid::new_v4()).collect();
                    for i in 0..n {
                        let ev = make_event(tenants[i % 50], (i % 100) as u32);
                        engine.enqueue(&ev, now).unwrap();
                    }
                    (engine, now)
                },
                |(mut engine, now)| {
                    let mut scheduled = 0;
                    while let Some(_) = engine.try_schedule_next(now) {
                        scheduled += 1;
                    }
                    black_box(scheduled)
                },
                criterion::BatchSize::SmallInput,
            );
        });
    }
    group.finish();
}

fn bench_duplicate_suppression(c: &mut Criterion) {
    c.bench_function("scheduler_duplicate_suppression", |b| {
        let mut engine = SchedulerEngine::default();
        let now = Utc::now();
        let ev = make_event(Uuid::new_v4(), 50);
        engine.enqueue(&ev, now).unwrap();

        b.iter(|| {
            let res = engine.enqueue(black_box(&ev), now);
            black_box(res)
        });
    });
}

fn bench_fairness_overhead(c: &mut Criterion) {
    c.bench_function("scheduler_fairness_under_spam", |b| {
        b.iter_batched(
            || {
                let mut engine = SchedulerEngine::new(SchedulerConfig {
                    per_user_max_concurrency: 2,
                    global_max_concurrency: 100,
                    per_user_pending_limit: 500,
                    ..Default::default()
                });
                let now = Utc::now();
                let spammer = Uuid::new_v4();
                let normal_users: Vec<Uuid> = (0..10).map(|_| Uuid::new_v4()).collect();

                // Spammer enqueues 200 tasks
                for _ in 0..200 {
                    let ev = make_event(spammer, 90);
                    engine.enqueue(&ev, now).unwrap();
                }
                // 10 normal users enqueue 1 task each
                for u in &normal_users {
                    let ev = make_event(*u, 30);
                    engine.enqueue(&ev, now).unwrap();
                }
                (engine, now)
            },
            |(mut engine, now)| {
                // Drain until quota allows
                let mut scheduled = 0;
                while let Some(_) = engine.try_schedule_next(now) {
                    scheduled += 1;
                }
                black_box(scheduled)
            },
            criterion::BatchSize::SmallInput,
        );
    });
}

criterion_group!(
    benches,
    bench_enqueue,
    bench_dequeue,
    bench_duplicate_suppression,
    bench_fairness_overhead
);
criterion_main!(benches);
