import os
import shutil
import sys

from forgerun_contracts.enums import Language
from pydantic import BaseModel, Field

# Sanitized environment isolating untrusted execution from host secrets and database credentials
SAFE_SUBPROCESS_ENV = {
    "PATH": os.environ.get(
        "PATH", "/usr/local/cargo/bin:/opt/java/openjdk/bin:/usr/local/bin:/usr/bin:/bin"
    ),
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "HOME": "/tmp",
    "RUST_BACKTRACE": "0",
}

HAS_UNSHARE = shutil.which("unshare") is not None


def wrap_with_sandbox(cmd: list[str]) -> list[str]:
    """Wraps execution command with user and network namespace isolation (unshare -r -n) when available."""
    if HAS_UNSHARE and os.environ.get("FORGERUN_DISABLE_UNSHARE") != "1":
        return ["unshare", "-r", "-n", "--"] + cmd
    return cmd


class LanguagePolicy(BaseModel):
    """Defines compilation, runtime command, and execution boundaries for a supported language."""

    language: Language
    source_filename: str
    is_compiled: bool
    compile_cmd: list[str] = Field(default_factory=list)
    compile_timeout_sec: float = 15.0
    run_cmd: list[str]
    binary_filename: str | None = None
    env_vars: dict[str, str] = Field(default_factory=dict)


def get_default_policy(language: Language | str) -> LanguagePolicy:
    """Returns the runtime policy manifest for the requested programming language."""
    lang_str = language.value if isinstance(language, Language) else str(language).lower()

    if lang_str == Language.PYTHON.value:
        return LanguagePolicy(
            language=Language.PYTHON,
            source_filename="solution.py",
            is_compiled=False,
            run_cmd=[sys.executable, "-u", "solution.py"],
        )
    elif lang_str == Language.CPP.value:
        return LanguagePolicy(
            language=Language.CPP,
            source_filename="solution.cpp",
            is_compiled=True,
            compile_cmd=["g++", "-O2", "-std=c++20", "solution.cpp", "-o", "solution"],
            compile_timeout_sec=15.0,
            run_cmd=["./solution"],
            binary_filename="solution",
        )
    elif lang_str == Language.JAVA.value:
        return LanguagePolicy(
            language=Language.JAVA,
            source_filename="Solution.java",
            is_compiled=True,
            compile_cmd=["javac", "Solution.java"],
            compile_timeout_sec=15.0,
            run_cmd=["java", "-Xmx{memory_limit_mb}m", "-Xms16m", "-XX:+UseSerialGC", "Solution"],
            binary_filename="Solution.class",
        )
    elif lang_str == Language.RUST.value:
        return LanguagePolicy(
            language=Language.RUST,
            source_filename="solution.rs",
            is_compiled=True,
            compile_cmd=["rustc", "-O", "solution.rs", "-o", "solution"],
            compile_timeout_sec=20.0,
            run_cmd=["./solution"],
            binary_filename="solution",
        )
    else:
        raise ValueError(f"Unsupported language: {language}")
