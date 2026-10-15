"""
Word counts over a text, showing config features: a shared project config
that changes base defaults, every supported field type, and YAML configs.

    python demos/02_config.py --mode chars --top-k 5 --no-lowercase
    python demos/02_config.py --stopwords the a of --input-file README.md
    python demos/02_config.py --dump configs/words.yaml   # write config, exit
    python demos/02_config.py --config configs/words.yaml --overwrite
"""

# %%
# --- Imports
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from rundir import Run, RunConfig

TEXT = """The cue is in the context. The context routes the cue to the verb,
and the verb takes the cue from its object."""


# %%
# --- Project config: fields and defaults shared by all scripts of a project
@dataclass
class ProjectConfig(RunConfig):
    log_level: str = "DEBUG"  # override base defaults
    log_file: str = "run.log"
    data_dir: Path = Path("data")  # add a shared field


# %%
# --- Config
@dataclass
class Config(ProjectConfig):
    output_dir: str = "runs/words"
    input_file: Path | None = None  # None: use the built-in TEXT
    mode: Literal["words", "chars"] = "words"
    top_k: int = 3
    lowercase: bool = True
    stopwords: list[str] = field(default_factory=list)


cfg = Config()
run = Run(cfg)

# %%
# --- Count
text = cfg.input_file.read_text() if cfg.input_file else TEXT
if cfg.lowercase:
    text = text.lower()

tokens = text.split() if cfg.mode == "words" else [c for c in text if not c.isspace()]
tokens = [t.strip(".,") for t in tokens]
tokens = [t for t in tokens if t and t not in cfg.stopwords]
logging.debug("Tokens: %s", tokens)

counts = Counter(tokens).most_common(cfg.top_k)
for token, n in counts:
    logging.info("%-10s %d", token, n)

(run.dir / "counts.json").write_text(json.dumps(dict(counts), indent=2))
run.done()
