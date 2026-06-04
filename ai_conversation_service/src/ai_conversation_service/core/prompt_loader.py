from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "ai prompts"


@lru_cache(maxsize=32)
def load_prompt_file(file_name: str) -> str:
    path = PROMPTS_DIR / file_name
    return path.read_text(encoding="utf-8")
