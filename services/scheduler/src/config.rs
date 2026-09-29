use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchedulerConfig {
    /// Kafka partition assigned to this scheduler instance
    pub partition: u32,
    /// Maximum priority boost accumulated via wait-time aging
    pub max_aging_bonus: u32,
    /// Seconds a submission must wait to earn an aging step
    pub aging_interval_secs: u64,
    /// Priority boost increment added per aging interval
    pub aging_step: u32,
    /// Maximum concurrent executing jobs allowed per user
    pub per_user_max_concurrency: usize,
    /// Maximum concurrent executing jobs allowed globally on this partition/cluster
    pub global_max_concurrency: usize,
    /// Maximum pending (queued) tasks allowed per user before rejection
    pub per_user_pending_limit: usize,
}

impl Default for SchedulerConfig {
    fn default() -> Self {
        Self {
            partition: 0,
            max_aging_bonus: 50,
            aging_interval_secs: 5,
            aging_step: 5,
            per_user_max_concurrency: 2,
            global_max_concurrency: 50,
            per_user_pending_limit: 100,
        }
    }
}
