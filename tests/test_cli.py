from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pytest

from rundir.cli import convert_value, parse_into


@dataclass
class AllTypes:
    name: str = "a"
    count: int = 1
    rate: float = 0.5
    path: Path = Path("in")
    flag: bool = False
    limit: int | None = None
    tags: list[str] = field(default_factory=list)
    sizes: list[int] = field(default_factory=lambda: [1, 2])
    mode: Literal["fast", "slow"] = "fast"
    top_k: int = 5


def test_defaults_kept_without_flags():
    cfg = AllTypes()
    parse_into(cfg, [])
    assert cfg == AllTypes()


def test_every_type_parsed():
    cfg = AllTypes()
    parse_into(
        cfg,
        [
            "--name", "b",
            "--count", "3",
            "--rate", "1e-3",
            "--path", "out/x",
            "--flag",
            "--limit", "7",
            "--tags", "x", "y",
            "--sizes", "4", "5", "6",
            "--mode", "slow",
        ],
    )  # fmt: skip
    assert cfg.name == "b"
    assert cfg.count == 3
    assert cfg.rate == 0.001
    assert cfg.path == Path("out/x")
    assert cfg.flag is True
    assert cfg.limit == 7
    assert cfg.tags == ["x", "y"]
    assert cfg.sizes == [4, 5, 6]
    assert cfg.mode == "slow"


def test_no_flag_clears_bool():
    cfg = AllTypes(flag=True)
    parse_into(cfg, ["--no-flag"])
    assert cfg.flag is False


def test_empty_list():
    cfg = AllTypes()
    parse_into(cfg, ["--sizes"])
    assert cfg.sizes == []


@pytest.mark.parametrize("flag", ["--top_k", "--top-k"])
def test_underscore_and_dash_spellings(flag):
    cfg = AllTypes()
    parse_into(cfg, [flag, "9"])
    assert cfg.top_k == 9


def test_current_values_are_defaults():
    cfg = AllTypes(count=42)
    parse_into(cfg, ["--name", "z"])
    assert cfg.count == 42


@pytest.mark.parametrize(
    "args", [["--mode", "medium"], ["--count", "x"], ["--unknown", "1"]]
)
def test_invalid_args_exit(args):
    with pytest.raises(SystemExit):
        parse_into(AllTypes(), args)


@dataclass
class DictField:
    d: dict = field(default_factory=dict)


@dataclass
class MultiUnion:
    x: int | str = 1


@dataclass
class TupleField:
    t: tuple[int, int] = (1, 2)


@pytest.mark.parametrize("cls", [DictField, MultiUnion, TupleField])
def test_unsupported_types_raise(cls):
    with pytest.raises(TypeError, match="Unsupported type"):
        parse_into(cls(), [])


# --- convert_value (YAML values)
HINTS = {f: AllTypes.__dataclass_fields__[f].type for f in AllTypes.__dataclass_fields__}


@pytest.mark.parametrize(
    "name, value, expected",
    [
        ("name", "b", "b"),
        ("count", 3, 3),
        ("count", "3", 3),
        ("rate", 1, 1.0),
        ("rate", "1e-3", 0.001),
        ("path", "a/b", Path("a/b")),
        ("flag", True, True),
        ("limit", None, None),
        ("limit", 4, 4),
        ("tags", [], []),
        ("sizes", [1, "2"], [1, 2]),
        ("mode", "slow", "slow"),
    ],
)
def test_convert_value(name, value, expected):
    result = convert_value(name, HINTS[name], value)
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize(
    "name, value, error",
    [
        ("count", 1.5, TypeError),
        ("count", True, TypeError),
        ("count", None, TypeError),
        ("count", "x", ValueError),
        ("rate", False, TypeError),
        ("flag", "yes", TypeError),
        ("tags", "x", TypeError),
        ("sizes", [1, "x"], ValueError),
        ("mode", "medium", ValueError),
    ],
)
def test_convert_value_rejects(name, value, error):
    with pytest.raises(error, match=name):
        convert_value(name, HINTS[name], value)
