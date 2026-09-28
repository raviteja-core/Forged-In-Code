use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Language {
    Python,
    Cpp,
    Java,
    Rust,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SubmissionStatus {
    Created,
    Queued,
    Scheduled,
    Starting,
    Compiling,
    Running,
    Judging,
    Completed,
    Failed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Verdict {
    Accepted,
    WrongAnswer,
    CompileError,
    RuntimeError,
    TimeLimit,
    MemoryLimit,
    OutputLimit,
    Canceled,
    SandboxError,
    InfrastructureFailure,
}

impl Verdict {
    pub fn is_infrastructure_failure(&self) -> bool {
        matches!(self, Verdict::InfrastructureFailure | Verdict::SandboxError)
    }

    pub fn is_terminal(&self) -> bool {
        true
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FailureType {
    UserCode,
    Infrastructure,
    Timeout,
    SandboxError,
}
