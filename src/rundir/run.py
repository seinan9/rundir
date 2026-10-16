import atexit
import inspect
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from types import FrameType

from rundir.config import RunConfig, apply_config

_session_dirs: set[Path] = set()  # interactive dirs claimed by this kernel


class Run[C: RunConfig = RunConfig]:
    """Creates the run directory, starts logging and records metadata.

    Interactively the config is used as given and output goes to a per-script
    scratch directory under `interactive_root` that is deleted when the kernel
    shuts down. As a script the config is layered defaults -> YAML (--config)
    -> CLI flags, and output goes to `output_dir`, which must not already exist
    unless --overwrite is passed. The config is updated in place, so the object
    passed in stays the source of truth.

    Subclasses add project behavior (seeding, quieting loggers, ...) by
    overriding `setup`, and can replace the logging setup via `setup_logging`.
    They don't override `__init__`. To use a richer config type inside
    `setup`, subclass `Run[MyConfig]`.
    """

    interactive_root = "interactive"
    cfg: C

    def __init__(self, cfg: C) -> None:
        source_script = _caller_script(self._caller_frame())
        self.cfg = cfg
        self._start_time = time.time()
        self._interactive = _is_interactive()

        overwrite = False
        if not self._interactive:
            overwrite = apply_config(cfg)

        if self._interactive:
            self.dir = _interactive_dir(source_script, self.interactive_root)
            self.setup_logging(None)
        else:
            self.dir = _script_dir(cfg, overwrite)
            meta_dir = self.dir / "meta"
            meta_dir.mkdir(parents=True, exist_ok=True)
            self.setup_logging(meta_dir / cfg.log_file)
            _log_uncaught_exceptions()

        self.setup()

        if not self._interactive:
            _write_metadata(cfg, self.dir / "meta", source_script)

        logging.info("Run directory: %s", self.dir)
        logging.info("Config: %s", cfg)

    def setup_logging(self, log_file: Path | None) -> None:
        """Configure logging to stdout and `log_file` (None for interactive runs).

        Override to replace the logging setup entirely; for small tweaks
        (format, extra handlers, logger levels) use `setup` instead.
        """
        handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
        if log_file is not None:
            handlers.append(logging.FileHandler(log_file))

        logging.basicConfig(
            level=self.cfg.log_level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=handlers,
            force=True,
        )

    def setup(self) -> None:
        """Hook for subclasses, called once the config is final and logging is set up."""

    def done(self) -> None:
        """Log the total elapsed time and mark the run complete."""
        elapsed = time.time() - self._start_time
        logging.info("Completed in %.1fs", elapsed)
        if self._interactive:
            return
        with open(self.dir / "meta" / "done", "w") as f:
            f.write(f"completed: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write(f"elapsed:   {elapsed:.1f}s\n")

    def _caller_frame(self) -> FrameType | None:
        """The first frame outside this run's (possibly subclassed) `__init__`s."""
        frame = inspect.currentframe()
        frame = frame.f_back if frame is not None else None  # Run.__init__
        while (
            frame is not None
            and frame.f_code.co_name == "__init__"
            and frame.f_locals.get("self") is self
        ):
            frame = frame.f_back
        return frame


# --- Helpers
def _is_interactive() -> bool:
    """True in a REPL or Jupyter/IPython kernel, False when run as a script."""
    return hasattr(sys, "ps1") or "ipykernel" in sys.modules


def _caller_script(frame: FrameType | None) -> Path | None:
    """The file `Run` was created from.

    In VS Code's interactive window cells run from a temporary file, but the
    Jupyter extension sets `__file__` to the source script in the kernel.
    """
    if frame is None:
        return None
    file = frame.f_globals.get("__file__") or frame.f_code.co_filename
    path = Path(file).resolve()
    return path if path.suffix == ".py" and path.is_file() else None


def _interactive_dir(source_script: Path | None, root_name: str) -> Path:
    """Per-script scratch directory, scoped to the current kernel session.

    The first `Run` of a script in a session clears leftovers (e.g. from a
    killed kernel) and registers deletion at kernel shutdown or restart.
    Re-running the config cell later in the session keeps existing output.
    """
    root = Path.cwd() / root_name
    if source_script is None:
        name = Path("unknown")
    elif source_script.is_relative_to(Path.cwd()):
        name = source_script.relative_to(Path.cwd()).with_suffix("")
    else:
        name = Path(source_script.stem)
    run_dir = root / name

    if run_dir not in _session_dirs:
        shutil.rmtree(run_dir, ignore_errors=True)
        atexit.register(_remove_interactive_dir, run_dir, root)
        _session_dirs.add(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _remove_interactive_dir(run_dir: Path, root: Path) -> None:
    """Delete `run_dir` and any parents up to `root` left empty by it."""
    shutil.rmtree(run_dir, ignore_errors=True)
    for parent in run_dir.parents:
        if not parent.is_relative_to(root):
            break
        try:
            parent.rmdir()
        except OSError:  # not empty: another script still uses it
            break


def _script_dir(cfg: RunConfig, overwrite: bool) -> Path:
    """A fresh `output_dir`, so a finished run is never half-overwritten.

    With `overwrite`, an existing run directory is deleted first. Only
    directories that look like runs (contain `meta/`) are deleted, so a
    mistyped `output_dir` cannot wipe unrelated data.
    """
    run_dir = Path(cfg.output_dir)
    if run_dir.exists():
        status = "finished" if (run_dir / "meta" / "done").exists() else "incomplete"
        if not overwrite:
            raise FileExistsError(
                f"Run directory {run_dir} already exists ({status} run). "
                "Pass --overwrite to replace it."
            )
        if not (run_dir / "meta").is_dir():
            raise FileExistsError(
                f"Refusing to overwrite {run_dir}: it is not a run directory."
            )
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    return run_dir


def _write_metadata(cfg: RunConfig, meta_dir: Path, source_script: Path | None) -> None:
    cfg.save(meta_dir / "config.yaml")
    if source_script is not None:
        shutil.copy(source_script, meta_dir / "script.py")
    logging.info("Source script: %s", source_script)


def _log_uncaught_exceptions() -> None:
    """Route uncaught exceptions through logging so they reach the log file."""
    default_excepthook = sys.excepthook

    def handler(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            default_excepthook(exc_type, exc_value, exc_tb)
            return
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = handler
