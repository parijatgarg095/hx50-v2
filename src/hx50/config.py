"""Runtime settings. Environment-specific values are resolved here and injected everywhere else."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .pipeline.sources import DataSources

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path

    @property
    def sources(self) -> DataSources:
        return DataSources(
            prices=self.data_dir / "prices.csv",
            shares=self.data_dir / "shares.csv",
            excluded_classes=self.data_dir / "excluded_classes.csv",
        )

    @property
    def universe_csv(self) -> Path:
        return self.data_dir / "universe.csv"

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(os.environ.get("HX50_DATA_DIR", PROJECT_ROOT / "data"))
        db_path = Path(os.environ.get("HX50_DB", data_dir / "hx50.db"))
        return cls(data_dir=data_dir, db_path=db_path)
