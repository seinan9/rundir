from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pytest
import yaml

from rundir.config import RunConfig, apply_config


@dataclass
class Config(RunConfig):
    output_dir: str = "runs/x"
    lr: float = 0.1
    epochs: int = 1
    data: Path = Path("data")
    files: list[Path] = field(default_factory=list)


def write_yaml(path: Path, values: dict) -> Path:
    path.write_text(yaml.safe_dump(values))
    return path


def test_defaults_only(argv):
    cfg = Config()
    assert apply_config(cfg) is False
    assert cfg == Config()


def test_cli_overrides_defaults(argv):
    argv("--epochs", "5")
    cfg = Config()
    apply_config(cfg)
    assert cfg.epochs == 5


def test_yaml_overrides_defaults(argv, tmp_path):
    argv("--config", str(write_yaml(tmp_path / "c.yaml", {"epochs": 3, "lr": 0.5})))
    cfg = Config()
    apply_config(cfg)
    assert cfg.epochs == 3
    assert cfg.lr == 0.5


def test_cli_overrides_yaml(argv, tmp_path):
    path = write_yaml(tmp_path / "c.yaml", {"epochs": 3, "lr": 0.5})
    argv("--epochs", "9", "--config", str(path))
    cfg = Config()
    apply_config(cfg)
    assert cfg.epochs == 9
    assert cfg.lr == 0.5


def test_empty_yaml(argv, tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("")
    argv("--config", str(path))
    cfg = Config()
    apply_config(cfg)
    assert cfg == Config()


def test_unknown_yaml_field_raises(argv, tmp_path):
    argv("--config", str(write_yaml(tmp_path / "c.yaml", {"nope": 1})))
    with pytest.raises(TypeError, match="nope"):
        apply_config(Config())


def test_overwrite_returned(argv):
    argv("--overwrite")
    assert apply_config(Config()) is True


def test_dump_writes_resolved_config_and_exits(argv, tmp_path):
    out = tmp_path / "sub" / "dump.yaml"
    argv("--epochs", "4", "--overwrite", "--dump", str(out))
    with pytest.raises(SystemExit) as exc:
        apply_config(Config())
    assert exc.value.code == 0
    values = yaml.safe_load(out.read_text())
    assert values["epochs"] == 4
    assert "overwrite" not in values
    assert "dump" not in values


def test_dumped_config_loads_back(argv, tmp_path):
    out = tmp_path / "dump.yaml"
    argv("--epochs", "4", "--files", "a", "b", "--dump", str(out))
    with pytest.raises(SystemExit):
        apply_config(Config())

    argv("--config", str(out))
    cfg = Config()
    apply_config(cfg)
    assert cfg.epochs == 4
    assert cfg.files == [Path("a"), Path("b")]


# --- YAML values get the same conversion and validation as CLI flags.
def test_yaml_float_without_dot(argv, tmp_path):
    # PyYAML reads `1e-3` as a string.
    path = tmp_path / "c.yaml"
    path.write_text("lr: 1e-3\n")
    argv("--config", str(path))
    cfg = Config()
    apply_config(cfg)
    assert cfg.lr == 0.001


def test_yaml_path_converted(argv, tmp_path):
    argv("--config", str(write_yaml(tmp_path / "c.yaml", {"data": "d/e"})))
    cfg = Config()
    apply_config(cfg)
    assert cfg.data == Path("d/e")


def test_yaml_list_of_paths_converted(argv, tmp_path):
    argv("--config", str(write_yaml(tmp_path / "c.yaml", {"files": ["a", "b"]})))
    cfg = Config()
    apply_config(cfg)
    assert cfg.files == [Path("a"), Path("b")]


@dataclass
class ModeConfig(RunConfig):
    output_dir: str = "runs/x"
    mode: Literal["fast", "slow"] = "fast"


def test_yaml_literal_validated(argv, tmp_path):
    argv("--config", str(write_yaml(tmp_path / "c.yaml", {"mode": "medium"})))
    with pytest.raises(ValueError, match="medium"):
        apply_config(ModeConfig())


@dataclass
class ConfConfig(RunConfig):
    output_dir: str = "runs/x"
    conf: str = "default"


def test_field_prefix_not_taken_by_config(argv):
    argv("--conf", "x")
    cfg = ConfConfig()
    apply_config(cfg)
    assert cfg.conf == "x"


def test_yaml_wrong_type_raises(argv, tmp_path):
    argv("--config", str(write_yaml(tmp_path / "c.yaml", {"epochs": [1, 2]})))
    with pytest.raises(TypeError, match="epochs"):
        apply_config(Config())


def test_abbreviated_run_option_rejected(argv):
    argv("--over")
    with pytest.raises(SystemExit):
        apply_config(Config())
