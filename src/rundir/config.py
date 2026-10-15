import sys
from argparse import ArgumentParser
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml

from rundir.cli import parse_into


@dataclass
class RunConfig:
    """Fields every run needs. Subclass this and add experiment parameters."""

    output_dir: str

    log_level: str = "INFO"
    log_file: str = "log"

    def save(self, path: Path) -> None:
        values = {k: _plain(v) for k, v in asdict(self).items()}
        path.write_text(yaml.dump(values, default_flow_style=False, sort_keys=False))

    def __str__(self) -> str:
        return ", ".join(f"{k}={v}" for k, v in asdict(self).items())


def apply_config(cfg: RunConfig) -> bool:
    """Layer defaults -> YAML -> CLI flags onto `cfg` in place.

    Returns whether --overwrite was passed. It is a run option, not part of the
    config, so it never ends up in a saved config.yaml.
    """
    pre = ArgumentParser(add_help=False)
    pre.add_argument("--config", type=Path)
    pre.add_argument("--dump", type=Path)
    pre.add_argument("--overwrite", action="store_true")
    pre_args, remaining = pre.parse_known_args()

    if pre_args.config is not None:
        _apply_yaml(cfg, pre_args.config)

    parse_into(cfg, remaining)

    if pre_args.dump is not None:
        _dump_config(cfg, pre_args.dump)
        raise SystemExit(0)

    return pre_args.overwrite


def _plain(value: object) -> object:
    """Paths as strings, so the YAML loads back with `safe_load`."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _apply_yaml(cfg: RunConfig, path: Path) -> None:
    values = yaml.safe_load(path.read_text()) or {}
    unknown = set(values) - {f.name for f in fields(cfg)}
    if unknown:
        raise TypeError(f"Unknown config fields: {unknown}")
    for key, value in values.items():
        setattr(cfg, key, value)


def _dump_config(cfg: RunConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg.save(path)
    print(f"Config written to {path}", file=sys.stderr)
