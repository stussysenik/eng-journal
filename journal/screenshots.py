from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _find_convert() -> str:
    for candidate in ("magick", "convert"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("ImageMagick is required to generate screenshots")


def render_text_screenshot(source: Path, target: Path, title: str) -> Path:
    convert = _find_convert()
    source_text = source.read_text(encoding="utf-8")
    banner = f"$ {title}\n\n"
    payload = banner + source_text
    temp = target.with_suffix(".render.txt")
    temp.write_text(payload, encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        convert,
        "-background",
        "#0b1220",
        "-fill",
        "#dbe7ff",
        "-font",
        "JetBrainsMono-NFM-Regular",
        "-pointsize",
        "24",
        "-interline-spacing",
        "6",
        f"label:@{temp}",
        "-bordercolor",
        "#111827",
        "-border",
        "40",
        str(target),
    ]
    subprocess.run(cmd, check=True)
    temp.unlink(missing_ok=True)
    return target

