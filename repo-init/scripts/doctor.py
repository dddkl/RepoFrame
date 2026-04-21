#!/usr/bin/env python3
"""Verify runtime requirements for repo-init."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

MIN_PYTHON = (3, 10)

FORMAT_MODULES = {
    "docx": ("docx", "python-docx"),
    "pdf": ("pypdf", "pypdf"),
}

SUFFIX_FORMATS = {
    ".docx": "docx",
    ".pdf": "pdf",
}


def detect_required_formats(source_path: str | None, explicit_formats: list[str]) -> list[str]:
    """Determine which formats require runtime checks."""
    formats = [item.lower() for item in explicit_formats]
    if source_path:
        suffix = Path(source_path).suffix.lower()
        detected = SUFFIX_FORMATS.get(suffix)
        if detected and detected not in formats:
            formats.append(detected)
    return sorted(set(formats))


def collect_runtime_status(source_path: str | None = None, explicit_formats: list[str] | None = None) -> dict:
    """Collect runtime status for the current Python interpreter."""
    explicit_formats = explicit_formats or []
    formats = detect_required_formats(source_path, explicit_formats)
    checks: list[dict[str, str | bool]] = []
    ok = True

    for format_name in formats:
        module_name, package_name = FORMAT_MODULES[format_name]
        try:
            importlib.import_module(module_name)
            checks.append(
                {
                    "format": format_name,
                    "module": module_name,
                    "package": package_name,
                    "ok": True,
                    "message": f"{module_name} is available.",
                }
            )
        except Exception as exc:  # pragma: no cover - environment-specific
            ok = False
            checks.append(
                {
                    "format": format_name,
                    "module": module_name,
                    "package": package_name,
                    "ok": False,
                    "message": f"Missing dependency for {format_name}: install `{package_name}`. ({type(exc).__name__})",
                }
            )

    version_ok = sys.version_info >= MIN_PYTHON
    ok = ok and version_ok
    return {
        "ok": ok,
        "python_executable": sys.executable,
        "python_version": ".".join(str(part) for part in sys.version_info[:3]),
        "minimum_python_version": ".".join(str(part) for part in MIN_PYTHON),
        "version_ok": version_ok,
        "checks": checks,
        "install_hint": "python -m pip install pypdf python-docx",
    }


def render_text(status: dict) -> str:
    """Render a human-readable status report."""
    lines = [
        "# Repo Init Doctor",
        "",
        f"- Python: `{status['python_executable']}`",
        f"- Version: `{status['python_version']}`",
        f"- Minimum required: `{status['minimum_python_version']}`",
        f"- Version OK: `{status['version_ok']}`",
        "",
    ]
    if status["checks"]:
        lines.append("## Dependency Checks")
        lines.append("")
        for check in status["checks"]:
            lines.append(f"- `{check['format']}`: {'OK' if check['ok'] else 'MISSING'} - {check['message']}")
        lines.append("")
    else:
        lines.append("## Dependency Checks")
        lines.append("")
        lines.append("- No format-specific dependencies were requested.")
        lines.append("")

    if not status["ok"]:
        lines.append("## Action")
        lines.append("")
        lines.append(f"- Install missing dependencies with `{status['install_hint']}`.")
        lines.append("")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Optional source file path to infer required dependencies.")
    parser.add_argument(
        "--format",
        action="append",
        default=[],
        choices=sorted(FORMAT_MODULES.keys()),
        help="Explicit format to validate. Repeat as needed.",
    )
    parser.add_argument("--output", help="Optional path to write output.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser.parse_args()


def main() -> int:
    """Run the doctor."""
    args = parse_args()
    status = collect_runtime_status(args.source, args.format)
    text = json.dumps(status, indent=2, ensure_ascii=False) + "\n" if args.json else render_text(status)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
