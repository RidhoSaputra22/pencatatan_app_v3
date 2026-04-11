"""Central logging configuration for the edge worker.

Log levels based on APP_ENV:
  dev         → DEBUG   (all messages shown)
  production  → INFO    (verbose per-frame/per-track messages suppressed)
  anything else → INFO
"""
import logging
import os

from .config import APP_ENV

_LEVEL = logging.DEBUG if APP_ENV == "dev" else logging.INFO

# Configure root logger once
logging.basicConfig(
    level=_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Suppress noisy third-party libraries in non-dev mode
if APP_ENV != "dev":
    for _noisy in (
        "ultralytics",
        "torch",
        "urllib3",
        "werkzeug",
        "PIL",
        "deep_sort_realtime",
    ):
        logging.getLogger(_noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under 'edge.<name>'."""
    return logging.getLogger(f"edge.{name}")
