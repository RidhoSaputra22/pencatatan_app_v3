"""Regression tests for capture cleanup around RTSP reconnects."""
from __future__ import annotations

import importlib
import sys
import types


class _DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _FakeCapture:
    def __init__(self):
        self.release_calls = 0

    def isOpened(self):
        return True

    def release(self):
        self.release_calls += 1


class _FakeThread:
    def __init__(self, alive: bool = True, stop_on_join: bool = False):
        self.alive = alive
        self.stop_on_join = stop_on_join
        self.join_timeouts = []

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_timeouts.append(timeout)
        if self.stop_on_join:
            self.alive = False


def _load_capture_module(monkeypatch):
    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.CAP_DSHOW = 700
    fake_cv2.CAP_MSMF = 1400
    fake_cv2.CAP_ANY = 0
    fake_cv2.CAP_PROP_OPEN_TIMEOUT_MSEC = 53
    fake_cv2.CAP_PROP_READ_TIMEOUT_MSEC = 54
    fake_cv2.CAP_PROP_BUFFERSIZE = 38
    fake_cv2.CAP_PROP_FPS = 5

    def _unexpected_video_capture(*args, **kwargs):
        raise AssertionError("VideoCapture should not be called in this unit test")

    fake_cv2.VideoCapture = _unexpected_video_capture

    fake_logger = types.ModuleType("edge.core.logger")
    fake_logger.get_logger = lambda name: _DummyLogger()

    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    monkeypatch.setitem(sys.modules, "edge.core.logger", fake_logger)
    sys.modules.pop("edge.core.capture", None)

    module = importlib.import_module("edge.core.capture")
    return importlib.reload(module)


def test_release_defers_capture_release_until_reader_thread_exits(monkeypatch):
    capture_module = _load_capture_module(monkeypatch)
    latest = capture_module.LatestFrameCapture("rtsp://camera/live")
    native_capture = _FakeCapture()
    reader_thread = _FakeThread(alive=True, stop_on_join=False)

    latest._capture = native_capture
    latest._thread = reader_thread
    latest._running = True

    latest.release()

    assert reader_thread.join_timeouts == [5.0]
    assert native_capture.release_calls == 0
    assert len(latest._pending_releases) == 1

    reader_thread.alive = False

    assert latest.isOpened() is False
    assert native_capture.release_calls == 1
    assert latest._pending_releases == []


def test_release_still_releases_capture_when_reader_thread_stops_cleanly(monkeypatch):
    capture_module = _load_capture_module(monkeypatch)
    latest = capture_module.LatestFrameCapture("rtsp://camera/live")
    native_capture = _FakeCapture()
    reader_thread = _FakeThread(alive=True, stop_on_join=True)

    latest._capture = native_capture
    latest._thread = reader_thread
    latest._running = True

    latest.release()

    assert reader_thread.join_timeouts == [5.0]
    assert native_capture.release_calls == 1
    assert latest._pending_releases == []
