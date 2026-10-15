import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

import rundir.run
from rundir import Run, RunConfig
from rundir.run import _remove_interactive_dir


@dataclass
class Config(RunConfig):
    output_dir: str = "runs/x"
    epochs: int = 1


@pytest.fixture
def cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --- Script mode
def test_run_dir_layout(argv, cwd):
    argv("--epochs", "3")
    cfg = Config()
    run = Run(cfg)
    logging.info("hello")
    run.done()

    meta = cwd / "runs/x/meta"
    assert run.dir == Path("runs/x")
    assert cfg.epochs == 3  # updated in place
    assert yaml.safe_load((meta / "config.yaml").read_text())["epochs"] == 3
    assert (meta / "script.py").read_text() == Path(__file__).read_text()
    assert "hello" in (meta / "log").read_text()
    done = (meta / "done").read_text()
    assert done.startswith("completed: ")
    assert "elapsed:" in done


def test_custom_log_file(argv, cwd):
    argv("--log_file", "train.log")
    Run(Config())
    assert (cwd / "runs/x/meta/train.log").exists()


def test_no_done_until_done_called(argv, cwd):
    Run(Config())
    assert not (cwd / "runs/x/meta/done").exists()


def test_existing_dir_refused(argv, cwd):
    Run(Config()).done()
    with pytest.raises(FileExistsError, match="finished run"):
        Run(Config())


def test_existing_incomplete_dir_refused(argv, cwd):
    Run(Config())
    with pytest.raises(FileExistsError, match="incomplete run"):
        Run(Config())


def test_overwrite_replaces_run_dir(argv, cwd):
    run = Run(Config())
    (run.dir / "old.txt").write_text("old")
    argv("--overwrite")
    run = Run(Config())
    assert not (run.dir / "old.txt").exists()
    assert (run.dir / "meta/config.yaml").exists()


def test_overwrite_refuses_non_run_dir(argv, cwd):
    precious = cwd / "runs/x"
    precious.mkdir(parents=True)
    (precious / "data.txt").write_text("keep me")
    argv("--overwrite")
    with pytest.raises(FileExistsError, match="not a run directory"):
        Run(Config())
    assert (precious / "data.txt").read_text() == "keep me"


def test_overwrite_not_saved(argv, cwd):
    argv("--overwrite")
    run = Run(Config())
    assert "overwrite" not in yaml.safe_load((run.dir / "meta/config.yaml").read_text())


def test_uncaught_exceptions_logged(argv, cwd):
    Run(Config())
    try:
        raise ValueError("boom")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    assert "boom" in (cwd / "runs/x/meta/log").read_text()


# --- Subclass hooks
class HookRun(Run):
    def __init__(self, cfg):
        self.calls = []
        super().__init__(cfg)

    def setup_logging(self, log_file):
        self.calls.append(("setup_logging", log_file))
        super().setup_logging(log_file)

    def setup(self):
        self.calls.append(("setup", self.cfg.epochs))


def test_hooks_called_in_order_with_final_config(argv, cwd):
    argv("--epochs", "7")
    run = HookRun(Config())
    assert run.calls == [
        ("setup_logging", Path("runs/x/meta/log")),
        ("setup", 7),
    ]


def test_subclass_init_still_finds_caller_script(argv, cwd):
    run = HookRun(Config())
    assert (run.dir / "meta/script.py").read_text() == Path(__file__).read_text()


# --- Interactive mode
@pytest.fixture
def interactive(monkeypatch):
    monkeypatch.setattr(rundir.run, "_is_interactive", lambda: True)
    monkeypatch.setattr(rundir.run, "_session_dirs", set())
    registered = []
    monkeypatch.setattr(
        rundir.run.atexit, "register", lambda *args: registered.append(args)
    )
    return registered


def test_interactive_ignores_argv_and_output_dir(argv, cwd, interactive):
    argv("--epochs", "9")
    cfg = Config()
    run = Run(cfg)
    run.done()
    assert cfg.epochs == 1
    assert not (cwd / "runs").exists()
    assert not (run.dir / "meta").exists()
    # Name falls back to the test file's stem: it lives outside cwd.
    assert run.dir == cwd / "interactive" / Path(__file__).stem


def test_interactive_root_override(cwd, interactive):
    class ScratchRun(Run):
        interactive_root = "scratch"

    run = ScratchRun(Config())
    assert run.dir.parent == cwd / "scratch"


def test_interactive_dir_cleared_once_per_session(cwd, interactive):
    stale = cwd / "interactive" / Path(__file__).stem
    stale.mkdir(parents=True)
    (stale / "leftover.txt").write_text("x")

    run = Run(Config())
    assert not (run.dir / "leftover.txt").exists()
    (run.dir / "out.txt").write_text("y")

    run = Run(Config())  # re-running the config cell keeps output
    assert (run.dir / "out.txt").exists()
    assert len(interactive) == 1


def test_remove_interactive_dir_prunes_empty_parents(tmp_path):
    root = tmp_path / "interactive"
    run_dir = root / "a" / "b"
    run_dir.mkdir(parents=True)
    (run_dir / "out.txt").write_text("x")
    _remove_interactive_dir(run_dir, root)
    assert not root.exists()
    assert tmp_path.exists()


def test_remove_interactive_dir_keeps_shared_parents(tmp_path):
    root = tmp_path / "interactive"
    run_dir = root / "a" / "b"
    other = root / "a" / "c"
    run_dir.mkdir(parents=True)
    other.mkdir()
    _remove_interactive_dir(run_dir, root)
    assert not run_dir.exists()
    assert other.exists()
