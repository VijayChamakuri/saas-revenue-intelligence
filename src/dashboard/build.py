"""Assemble dashboard/index.html, a single offline file, from the warehouse marts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.dashboard.payload import build_payload

DASHBOARD_DIR = Path("dashboard")


def _inline(text: str) -> str:
    """Keep inlined script and JSON from closing their own <script> element."""
    return text.replace("</", "<\\/")


def build(output: Path = DASHBOARD_DIR / "index.html") -> Path:
    payload = build_payload()
    template = (DASHBOARD_DIR / "template.html").read_text(encoding="utf-8")
    html = (
        template.replace("/*STYLE*/", (DASHBOARD_DIR / "style.css").read_text(encoding="utf-8"))
        .replace("/*MEASURES*/", _inline((DASHBOARD_DIR / "measures.js").read_text(encoding="utf-8")))
        .replace("/*APP*/", _inline((DASHBOARD_DIR / "app.js").read_text(encoding="utf-8")))
        .replace("/*PAYLOAD*/", _inline(json.dumps(payload, separators=(",", ":"), allow_nan=False)))
    )
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DASHBOARD_DIR / "index.html")
    args = parser.parse_args()
    path = build(args.output)
    print(f"Wrote {path} ({path.stat().st_size / 1e6:.2f} MB)")
