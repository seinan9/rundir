"""
Toy training loop with a project-specific Run: `setup` seeds and records the
environment, `setup_logging` logs DEBUG to the file but only INFO to the
console, and interactive scratch dirs go to scratch/ instead of interactive/.

    python demos/03_custom_run.py --epochs 5 --lr 0.2
    python demos/03_custom_run.py --seed 1 --overwrite

In a real project the RunConfig/Run layer lives in a shared module and all
scripts import it from there.
"""

# %%
# --- Imports
import json
import logging
import platform
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import rundir


# %%
# --- Project layer
@dataclass
class RunConfig(rundir.RunConfig):
    seed: int = 42


class Run(rundir.Run):
    cfg: RunConfig  # narrows the type for setup()
    interactive_root = "scratch"

    def setup_logging(self, log_file: Path | None) -> None:
        fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        handlers: list[logging.Handler] = [console]
        if log_file is not None:
            handlers.append(logging.FileHandler(log_file))

        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.DEBUG)
        for h in handlers:
            h.setFormatter(fmt)
            root.addHandler(h)

    def setup(self) -> None:
        random.seed(self.cfg.seed)
        env = {"python": sys.version.split()[0], "host": platform.node()}
        logging.debug("Environment: %s", env)
        meta_dir = self.dir / "meta"
        if meta_dir.is_dir():  # script runs only
            (meta_dir / "env.json").write_text(json.dumps(env, indent=2))


# %%
# --- Config
@dataclass
class Config(RunConfig):
    output_dir: str = "runs/train"
    epochs: int = 3
    steps: int = 10
    lr: float = 0.1


cfg = Config()
run = Run(cfg)

# %%
# --- Train
loss = 1.0
with open(run.dir / "metrics.jsonl", "w") as f:
    for epoch in range(cfg.epochs):
        for step in range(cfg.steps):
            loss *= 1 - cfg.lr * random.random()
            logging.debug("epoch=%d step=%d loss=%.4f", epoch, step, loss)
        f.write(json.dumps({"epoch": epoch, "loss": loss}) + "\n")
        logging.info("epoch=%d loss=%.4f", epoch, loss)

run.done()
