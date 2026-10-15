from argparse import ArgumentParser, BooleanOptionalAction
from dataclasses import fields
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

_SCALARS = (str, int, float, Path)


def parse_into(cfg: Any, args: list[str]) -> None:
    """Parse `--field value` flags for the dataclass `cfg` and set them in place.

    Current values of `cfg` are the defaults, so flags only override what
    was given explicitly.
    """
    hints = get_type_hints(type(cfg))
    parser = ArgumentParser()
    for f in fields(cfg):
        flags = [f"--{f.name}"]
        if "_" in f.name:
            flags.append(f"--{f.name.replace('_', '-')}")
        parser.add_argument(
            *flags,
            dest=f.name,
            default=getattr(cfg, f.name),
            **_arg_kwargs(f.name, hints[f.name]),
        )
    parsed = parser.parse_args(args)
    for f in fields(cfg):
        setattr(cfg, f.name, getattr(parsed, f.name))


def convert_value(name: str, hint: Any, value: Any) -> Any:
    """Check and convert a value loaded from YAML for the field `name`.

    Uses the same type rules as the CLI flags. Strings are parsed like flag
    values (so `1e-3` becomes a float); other values must already have the
    field's type.
    """
    hint, optional = _unwrap_optional(name, hint)
    if value is None:
        if optional:
            return None
        raise TypeError(f"{name}: expected {hint}, got None")
    if hint is bool:
        if not isinstance(value, bool):
            raise TypeError(f"{name}: expected bool, got {value!r}")
        return value
    if get_origin(hint) is list:
        if not isinstance(value, list):
            raise TypeError(f"{name}: expected a list, got {value!r}")
        (item,) = get_args(hint)
        return [_convert_scalar(name, item, v) for v in value]
    return _convert_scalar(name, hint, value)


def _convert_scalar(name: str, hint: Any, value: Any) -> Any:
    kwargs = _scalar_kwargs(name, hint)
    type_ = kwargs["type"]
    if isinstance(value, str):
        try:
            value = type_(value)
        except ValueError:
            raise ValueError(f"{name}: invalid {type_.__name__} value {value!r}")
    elif type_ is float and isinstance(value, int) and not isinstance(value, bool):
        value = float(value)
    elif not isinstance(value, type_) or isinstance(value, bool):
        raise TypeError(f"{name}: expected {type_.__name__}, got {value!r}")
    if "choices" in kwargs and value not in kwargs["choices"]:
        raise ValueError(f"{name}: {value!r} is not one of {kwargs['choices']}")
    return value


def _unwrap_optional(name: str, hint: Any) -> tuple[Any, bool]:
    """`X | None` -> (X, True), anything else -> (hint, False)."""
    if get_origin(hint) not in (Union, UnionType):
        return hint, False
    inner = [a for a in get_args(hint) if a is not NoneType]
    if len(inner) != 1:
        raise TypeError(f"Unsupported type for --{name}: {hint}")
    return inner[0], True


def _arg_kwargs(name: str, hint: Any) -> dict[str, Any]:
    hint, _ = _unwrap_optional(name, hint)
    if hint is bool:
        return {"action": BooleanOptionalAction}
    if get_origin(hint) is list:
        (item,) = get_args(hint)
        return {"nargs": "*", **_scalar_kwargs(name, item)}
    return _scalar_kwargs(name, hint)


def _scalar_kwargs(name: str, hint: Any) -> dict[str, Any]:
    if get_origin(hint) is Literal:
        choices = get_args(hint)
        return {"type": type(choices[0]), "choices": choices}
    if hint in _SCALARS:
        return {"type": hint}
    raise TypeError(f"Unsupported type for --{name}: {hint}")
