#!/usr/bin/env python3
"""Normalize raw extraction output into the repo-init intake schema."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from repo_init_common import (
    clamp,
    first_non_empty_line,
    load_json,
    normalize_text,
    utc_now_iso,
    unique,
    write_json,
    write_text,
)


def extract_sections(text: str, metadata: dict[str, Any]) -> list[str]:
    """Extract likely section headings."""
    headings = metadata.get("headings") or []
    cleaned = [normalize_text(heading) for heading in headings if normalize_text(heading)]
    if cleaned:
        return unique(cleaned[:20])

    sections: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+.+", stripped):
            sections.append(re.sub(r"^#{1,6}\s+", "", stripped))
            continue
        if 3 <= len(stripped) <= 80 and stripped == stripped.title() and stripped.endswith(":") is False:
            sections.append(stripped)
    return unique(sections[:20])


def derive_title(raw: dict[str, Any], text: str, sections: list[str]) -> str:
    """Derive a stable title."""
    title = normalize_text(str(raw.get("title") or ""))
    if title:
        return title[:120]
    if sections:
        return sections[0][:120]
    return first_non_empty_line(text)[:120] or "Untitled project input"


def estimate_confidence(source_type: str, detected_format: str, text: str, sections: list[str], warnings: list[str]) -> float:
    """Estimate extraction confidence."""
    base_scores = {
        ("prompt", "text"): 0.97,
        ("file", "markdown"): 0.92,
        ("file", "text"): 0.88,
        ("file", "docx"): 0.84,
        ("file", "html"): 0.82,
        ("file", "pdf"): 0.72,
    }
    score = base_scores.get((source_type, detected_format), 0.7)

    if len(text) < 150:
        score -= 0.2
    elif len(text) > 500:
        score += 0.04

    if sections:
        score += 0.03
    else:
        score -= 0.08

    if source_type == "prompt":
        if len(text) >= 40:
            score += 0.16
        if not sections:
            score += 0.08

    score -= min(0.25, 0.05 * len(warnings))
    return round(clamp(score, 0.15, 0.99), 2)


def normalize_intake(raw: dict[str, Any], extracted_text_output: str | None = None) -> dict[str, Any]:
    """Normalize raw extraction output into the stable intake schema."""
    source_type = raw.get("source_type") or "file"
    detected_format = raw.get("detected_format") or "text"
    raw_text = normalize_text(str(raw.get("raw_text") or ""))
    warnings = unique([str(item) for item in raw.get("warnings", []) if str(item).strip()])
    metadata = raw.get("metadata") or {}
    sections = extract_sections(raw_text, metadata)
    title = derive_title(raw, raw_text, sections)
    extracted_text_path = write_text(raw_text + "\n", extracted_text_output)

    return {
        "source_type": source_type,
        "source_path": raw.get("source_path"),
        "detected_format": detected_format,
        "extracted_text": raw_text,
        "extracted_text_path": extracted_text_path,
        "title": title,
        "sections": sections,
        "confidence": estimate_confidence(source_type, detected_format, raw_text, sections, warnings),
        "warnings": warnings,
        "word_count": len(raw_text.split()),
        "metadata": metadata,
        "provenance": {
            **(raw.get("provenance") or {}),
            "normalized_timestamp": utc_now_iso(),
            "normalizer": "normalize_project_intake.py",
        },
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to the raw extraction JSON.")
    parser.add_argument(
        "--write-extracted-text",
        help="Optional path to persist normalized extracted text.",
    )
    parser.add_argument("--output", help="Optional path to write JSON output.")
    return parser.parse_args()


def main() -> int:
    """Run the normalizer."""
    args = parse_args()
    try:
        raw = load_json(args.input)
        normalized = normalize_intake(raw, args.write_extracted_text)
        write_json(normalized, args.output)
        return 0
    except Exception as exc:  # pragma: no cover - CLI entry point
        print(f"normalize_project_intake.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
