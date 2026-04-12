"""Regression tests for ReID identity stabilization and aliasing."""
from __future__ import annotations

import importlib
import math
import sys
import types

import numpy as np


class _DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


def _load_reid_module(
    monkeypatch,
    *,
    match_threshold: float = 0.77,
    min_track_frames: int = 3,
    strong_match_threshold: float = 0.86,
    ambiguity_margin: float = 0.04,
    prototype_alpha: float = 0.18,
):
    fake_config = types.ModuleType("edge.core.config")
    fake_config.REID_MATCH_THRESHOLD = match_threshold
    fake_config.REID_MIN_TRACK_FRAMES = min_track_frames
    fake_config.REID_STRONG_MATCH_THRESHOLD = strong_match_threshold
    fake_config.REID_AMBIGUITY_MARGIN = ambiguity_margin
    fake_config.REID_PROTOTYPE_ALPHA = prototype_alpha

    fake_logger = types.ModuleType("edge.core.logger")
    fake_logger.get_logger = lambda name: _DummyLogger()

    monkeypatch.setitem(sys.modules, "edge.core.config", fake_config)
    monkeypatch.setitem(sys.modules, "edge.core.logger", fake_logger)
    sys.modules.pop("edge.core.reid", None)

    module = importlib.import_module("edge.core.reid")
    return importlib.reload(module)


def _unit_from_angle(angle_deg: float) -> np.ndarray:
    angle_rad = math.radians(angle_deg)
    return np.asarray([math.cos(angle_rad), math.sin(angle_rad)], dtype=np.float32)


def test_track_identity_is_not_locked_on_first_noisy_embedding(monkeypatch):
    reid = _load_reid_module(monkeypatch, min_track_frames=3)
    today = "2026-04-12"

    base = _unit_from_angle(0)
    for _ in range(3):
        canonical = reid.update_track_identity(1, base, 7, today)

    canonical_key = canonical["visitor_key"]
    assert canonical["identity_status"] == "CONFIRMED"

    first = reid.update_track_identity(2, _unit_from_angle(42), 7, today)
    second = reid.update_track_identity(2, _unit_from_angle(38), 7, today)
    third = reid.update_track_identity(2, _unit_from_angle(12), 7, today)

    assert first["identity_status"] == "PENDING"
    assert second["identity_status"] == "PENDING"
    assert first["visitor_key"] != canonical_key
    assert third["identity_status"] == "CONFIRMED"
    assert third["visitor_key"] == canonical_key
    assert third["reid_source"] == "matched_existing"


def test_cleanup_aliases_provisional_key_to_final_key(monkeypatch):
    reid = _load_reid_module(monkeypatch, min_track_frames=3)
    today = "2026-04-12"

    pending = reid.update_track_identity(11, _unit_from_angle(35), 3, today)
    provisional_key = pending["visitor_key"]
    assert pending["identity_status"] == "PENDING"

    reid.cleanup_old_tracks([])

    final_key = reid.canonicalize_visitor_key(provisional_key)
    assert final_key
    assert final_key != provisional_key
    assert reid.get_cache_stats()["alias_count"] >= 1


def test_ambiguous_match_requires_clear_margin(monkeypatch):
    reid = _load_reid_module(
        monkeypatch,
        strong_match_threshold=0.999,
        ambiguity_margin=0.04,
    )

    reid.reset_daily_cache("2026-04-12")
    reid._daily_embeddings["visitor_a"] = _unit_from_angle(0)
    reid._daily_embeddings["visitor_b"] = _unit_from_angle(10)
    reid._daily_embedding_counts["visitor_a"] = 1
    reid._daily_embedding_counts["visitor_b"] = 1
    reid._daily_matrix_dirty = True

    result = reid.find_similar_embedding(_unit_from_angle(5), threshold=0.77)

    assert result["visitor_key"] in {"visitor_a", "visitor_b"}
    assert result["similarity"] >= 0.77
    assert result["margin"] < 0.04
    assert result["confident"] is False
