"""DispositionProfile store - in-memory + file persistence.

Design decision (2026-05-06):
- D-2: In-memory + JSON file backup, discuss more if extended needs arise.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict

from ontology_engine.engine.cognitive.models import DispositionProfile


class DispositionStore:
    """Thread-safe in-memory store with JSON file backup."""

    def __init__(self, file_path: str | None = None):
        if file_path is None:
            project_root = os.environ.get(
                "ONTOLOGY_DATA_DIR",
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "data"),
            )
            os.makedirs(project_root, exist_ok=True)
            file_path = os.path.join(project_root, "disposition_profiles.json")
        self._file_path = file_path
        self._profiles: dict[str, DispositionProfile] = {}
        self._lock = threading.Lock()
        self._load()

    def get(self, space_id: str) -> DispositionProfile:
        with self._lock:
            if space_id not in self._profiles:
                self._profiles[space_id] = DispositionProfile(
                    id=f"disp:{space_id}",
                    scene="default",
                    space_id=space_id,
                )
            return self._profiles[space_id]

    def save(self, space_id: str, profile: DispositionProfile):
        with self._lock:
            self._profiles[space_id] = profile
            self._dump()

    def to_dict(self, space_id: str) -> dict:
        p = self.get(space_id)
        return {
            "id": p.id,
            "scene": p.scene,
            "space_id": p.space_id,
            "skepticism": p.skepticism,
            "evidence_demand": p.evidence_demand,
            "abstraction_preference": p.abstraction_preference,
            "thoroughness": p.thoroughness,
            "recency_bias": p.recency_bias,
            "empathy": p.empathy,
            "risk_tolerance": p.risk_tolerance,
        }

    def _load(self):
        try:
            if os.path.exists(self._file_path):
                with open(self._file_path) as f:
                    data = json.load(f)
                for sid, pdict in data.items():
                    if "id" not in pdict:
                        pdict["id"] = f"disp:{sid}"
                    if "scene" not in pdict:
                        pdict["scene"] = "default"
                    self._profiles[sid] = DispositionProfile(**pdict)
        except Exception:
            pass

    def _dump(self):
        try:
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
            data = {sid: asdict(p) for sid, p in self._profiles.items()}
            with open(self._file_path, "w") as f:
                json.dump(data, f, default=str, indent=2)
        except Exception:
            pass


_global_store: DispositionStore | None = None
_store_lock = threading.Lock()


def get_disposition_store() -> DispositionStore:
    global _global_store
    with _store_lock:
        if _global_store is None:
            _global_store = DispositionStore()
        return _global_store
