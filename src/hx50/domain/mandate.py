"""The index rulebook. Every rule a client may change is a field, so a mandate change is data, not code."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class InvalidMandate(ValueError):
    """The requested rules cannot produce an index."""


@dataclass(frozen=True)
class Mandate:
    size: int = 50
    exclude_top: int = 10
    buffer: int = 10
    top_buffer: int = 0
    base_level: float = 1000.0
    cost_bps: float = 10.0
    reentry_window: int = 4

    def __post_init__(self) -> None:
        if self.size < 1:
            raise InvalidMandate("size must be at least 1")
        for name in ("exclude_top", "buffer", "top_buffer", "reentry_window"):
            if getattr(self, name) < 0:
                raise InvalidMandate(f"{name} must not be negative")
        if self.top_buffer > self.exclude_top:
            raise InvalidMandate("top_buffer cannot exceed exclude_top")
        if self.base_level <= 0:
            raise InvalidMandate("base_level must be positive")
        if self.cost_bps < 0:
            raise InvalidMandate("cost_bps must not be negative")

    @property
    def first_rank(self) -> int:
        return self.exclude_top + 1

    @property
    def last_rank(self) -> int:
        return self.exclude_top + self.size

    @property
    def retention_floor(self) -> int:
        return self.last_rank + self.buffer

    def is_eligible(self, rank: int) -> bool:
        return rank > self.exclude_top

    def is_retained(self, rank: int) -> bool:
        # Incumbents survive a wider band than newcomers need to enter; that gap is what dampens churn.
        return self.exclude_top - self.top_buffer < rank <= self.retention_floor

    def ensure_fits(self, universe_size: int) -> None:
        if self.last_rank > universe_size:
            raise InvalidMandate(
                f"size + exclude_top = {self.last_rank} exceeds the universe of {universe_size} names"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
