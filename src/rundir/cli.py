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


def _arg_kwargs(name: str, hint: Any) -> dict[str, Any]:
    if get_origin(hint) in (Union, UnionType):
        inner = [a for a in get_args(hint) if a is not NoneType]
        if len(inner) != 1:
            raise TypeError(f"Unsupported type for --{name}: {hint}")
        hint = inner[0]
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
