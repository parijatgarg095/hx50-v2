"""Input files for a build and their content fingerprint."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataSources:
    prices: Path
    shares: Path
    excluded_classes: Path | None = None

    def files(self) -> list[Path]:
        optional = [self.excluded_classes] if self.excluded_classes and self.excluded_classes.exists() else []
        return [self.prices, self.shares, *optional]

    def fingerprint(self) -> str:
        return sha256_of(self.files())


def sha256_of(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()
