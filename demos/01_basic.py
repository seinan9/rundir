"""
Minimal rundir script: a config with two parameters, one output file.

    python demos/01_basic.py
    python demos/01_basic.py --name rundir --repeat 5 --overwrite

Outputs go to runs/basic/, metadata to runs/basic/meta/.
"""

# %%
# --- Imports
import logging
from dataclasses import dataclass

from rundir import Run, RunConfig


# %%
# --- Config
@dataclass
class Config(RunConfig):
    output_dir: str = "runs/basic"
    name: str = "world"
    repeat: int = 3


cfg = Config()
run = Run(cfg)

# %%
# --- Main
lines = [f"Hello, {cfg.name}!"] * cfg.repeat
(run.dir / "greeting.txt").write_text("\n".join(lines) + "\n")
logging.info("Wrote %d lines to %s", len(lines), run.dir / "greeting.txt")

run.done()
