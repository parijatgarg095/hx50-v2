"""Application service: the single entry point the API (or any other adapter) talks to."""
from __future__ import annotations

import threading
from dataclasses import replace

from .config import Settings
from .domain import Mandate, Scorecard
from .pipeline.build import build_index
from .storage import IndexReader, Manifest


class RebuildInProgress(RuntimeError):
    """Another rebuild holds the lock."""


class IndexService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._rebuild_lock = threading.Lock()
        self.reader = IndexReader(settings.db_path)

    def current_mandate(self) -> Mandate:
        return self.reader.manifest().mandate if self.reader.is_built() else Mandate()

    def rebuild(self, **rule_changes: int) -> tuple[Manifest, list[Scorecard]]:
        """Rebuild with some rules changed; unspecified rules (base level, costs...) carry over from the live run."""
        # Non-blocking: a second click should fail fast with a clear status, not queue another full build.
        if not self._rebuild_lock.acquire(blocking=False):
            raise RebuildInProgress("a rebuild is already running")
        try:
            mandate = replace(self.current_mandate(), **rule_changes)
            return build_index(self._settings.sources, mandate, self._settings.db_path)
        finally:
            self._rebuild_lock.release()
