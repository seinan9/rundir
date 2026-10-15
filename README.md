# rundir

Run directories, layered configs and logging for experiment scripts. Depends only on `pyyaml`.

- **Config as a dataclass.** Fields become CLI flags automatically, can be loaded from or dumped to
  YAML, and are type-checked either way.
- **One directory per run.** Outputs, the resolved config, a copy of the script and the log file
  end up together. Existing runs are never overwritten by accident.
- **Logging set up for you.** Output goes to stdout and the run's log file, including uncaught
  exceptions.
- **Works interactively.** In Jupyter or a REPL the same script runs unchanged and writes to a
  throwaway scratch directory instead.

## Install

Requires Python 3.13+.

```
uv add git+https://github.com/seinan9/rundir
```

or 

```
pip install git+https://github.com/seinan9/rundir
```

## Quick start

```python
from dataclasses import dataclass

from rundir import Run, RunConfig


@dataclass
class Config(RunConfig):
    output_dir: str = "runs/basic"
    name: str = "world"
    repeat: int = 3


cfg = Config()
run = Run(cfg)
(run.dir / "greeting.txt").write_text(f"Hello, {cfg.name}!\n" * cfg.repeat)
run.done()
```

```
python demos/01_basic.py --name rundir --repeat 5
```

This creates `runs/basic/` containing `greeting.txt` and a `meta/` folder with the resolved
config, a copy of the script, the log and a `done` marker. Running it again fails because
`runs/basic/` already exists. Pass `--overwrite` to replace it, or `--output_dir` to pick a new one.

## Demos

| Script | Shows |
| --- | --- |
| [`demos/01_basic.py`](demos/01_basic.py) | A config with two fields and one output file |
| [`demos/02_config.py`](demos/02_config.py) | A shared project config, every field type, `--dump` / `--config` |
| [`demos/03_custom_run.py`](demos/03_custom_run.py) | A `Run` subclass with custom `setup()`, `setup_logging()` and `interactive_root` |

## Script vs. interactive

- **As a script**, the config is layered: dataclass defaults → `--config x.yaml` → CLI flags.
  Output goes to `output_dir`, which must not already exist.
- **Interactively** (REPL, Jupyter, VS Code interactive window), the config is used as given.
  Output goes to a per-script scratch dir under `interactive/`, which is deleted when the kernel
  shuts down or restarts.

## CLI flags

| Flag | Effect |
| --- | --- |
| `--config x.yaml` | Load field values from YAML. Values are converted and checked like flags; unknown fields are an error. |
| `--<field> value` | Override a field (`--top-k` and `--top_k` both work). |
| `--<flag>` / `--no-<flag>` | Set a bool field. |
| `--dump x.yaml` | Write the resolved config and exit. |
| `--overwrite` | Replace an existing run dir. Only dirs that contain `meta/` are replaced. |

Supported field types are `str`, `int`, `float`, `Path`, `bool`, `X | None`, `list[X]`, and
`Literal[...]`. Any other type raises a `TypeError`. See [`demos/02_config.py`](demos/02_config.py).

## Run directory

```
<output_dir>/
  meta/
    config.yaml   # resolved config
    script.py     # copy of the calling script
    log           # log file (name set by log_file)
    done          # written by run.done(): completion time and elapsed seconds
  ...             # your outputs
```

## Extending

Subclass `Run` and override its hooks instead of `__init__`:

- `setup()` runs once the config is final and logging is configured. Use it for seeding,
  quieting loggers and other project setup.
- `setup_logging(log_file)` replaces the logging setup. `log_file` is `None` for interactive runs.
- `interactive_root` sets the scratch root (default `"interactive"`).

```python
@dataclass
class RunConfig(rundir.RunConfig):
    seed: int = 42


class Run(rundir.Run):
    cfg: RunConfig  # narrows the type for setup()

    def setup(self) -> None:
        random.seed(self.cfg.seed)
```

For the full version, see [`demos/03_custom_run.py`](demos/03_custom_run.py).
