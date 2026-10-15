import logging
import sys

import pytest


@pytest.fixture
def argv(monkeypatch):
    """Set the script arguments that `apply_config` reads from `sys.argv`."""

    def set_argv(*args: str) -> None:
        monkeypatch.setattr(sys, "argv", ["script.py", *args])

    set_argv()
    return set_argv


@pytest.fixture(autouse=True)
def restore_global_state(monkeypatch):
    """`Run` replaces `sys.excepthook` and the root logging handlers."""
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    yield
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()
