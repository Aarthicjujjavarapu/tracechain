import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TraceChainConfig:
    base_url: str = field(
        default_factory=lambda: os.getenv("TRACECHAIN_BACKEND_URL", "http://localhost:8000").rstrip("/")
    )
    enabled: bool = field(
        default_factory=lambda: os.getenv("TRACECHAIN_ENABLED", "true").lower() == "true"
    )
    # seconds before giving up on a backend call — never blocks the user's workflow
    timeout: float = field(
        default_factory=lambda: float(os.getenv("TRACECHAIN_TIMEOUT", "5"))
    )
    # "http" (default) sends traces to the backend API
    # "local" writes directly to a SQLite file — zero infrastructure required
    mode: str = field(
        default_factory=lambda: os.getenv("TRACECHAIN_MODE", "http").lower()
    )
    db_path: str = field(
        default_factory=lambda: os.getenv("TRACECHAIN_DB_PATH", "./tracechain.db")
    )

    _default: "TraceChainConfig | None" = field(default=None, init=False, repr=False)

    @classmethod
    def default(cls) -> "TraceChainConfig":
        return cls()
