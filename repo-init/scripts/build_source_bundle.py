#!/usr/bin/env python3
"""Build a multi-source intake bundle from prompt and project-plan files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from doctor import collect_runtime_status
from extract_project_source import extract_from_path
from normalize_project_intake import normalize_intake
from project_text import extract_use_stack, find_labeled_value, find_section, split_list_items
from repo_init_common import clamp, first_non_empty_line, normalize_text, slugify, unique, utc_now_iso, write_json


SUPPORTED_SUFFIXES = (".md", ".txt", ".docx", ".pdf", ".html", ".htm")
PRIORITY_BY_ROLE = {"authoritative": 3, "supporting": 2, "contextual": 1}
KEY_FIELDS = ("name", "goal", "users", "stack", "constraints", "stage")
LIST_FIELDS = {"stack", "constraints"}
GENERIC_TITLES = {
    "architecture",
    "background",
    "context",
    "overview",
    "plan",
    "project-plan",
    "project plan",
    "requirements",
    "source",
    "vision",
}

QUOTED_PATH_RE = re.compile(
    r"(?P<quote>['\"])(?P<path>[^'\"\n]+\.(?:md|txt|docx|pdf|html?))(?P=quote)",
    re.IGNORECASE,
)
UNQUOTED_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:\\[^\n,;]+?|(?:\.{1,2}[\\/]|[A-Za-z0-9_./\\-])[^\n,;]*)\.(?:md|txt|docx|pdf|html?))",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Repository root used to resolve relative source paths.")
    parser.add_argument("--prompt", help="Prompt text that may mention project files.")
    parser.add_argument("--prompt-file", help="Path to a text file containing the prompt.")
    parser.add_argument("--source", action="append", default=[], help="Project-plan file path. Repeat as needed.")
    parser.add_argument("--primary-source", help="Optional authoritative source path.")
    parser.add_argument("--artifacts-dir", required=True, help="Artifact directory for extracted text snapshots.")
    parser.add_argument("--output", help="Optional path to write the bundle JSON.")
    return parser.parse_args()


def load_prompt_text(prompt: str | None, prompt_file: str | None) -> str:
    """Load prompt text from CLI arguments."""
    if prompt:
        return prompt
    if prompt_file:
        return Path(prompt_file).read_text(encoding="utf-8")
    return ""


def clean_candidate_path(text: str) -> str:
    """Clean punctuation around a prompt-discovered path."""
    return text.strip().strip("()[]{}<>.,;:")


def resolve_source_path(repo_root: Path, candidate: str) -> Path:
    """Resolve a source path relative to the repository root when needed."""
    path = Path(candidate)
    if path.is_absolute():
        return path.resolve()
    return (repo_root / path).resolve()


def extract_prompt_source_candidates(prompt_text: str, repo_root: Path) -> list[Path]:
    """Extract file-path candidates from prompt text."""
    if not prompt_text:
        return []

    candidates: list[str] = []
    for match in QUOTED_PATH_RE.finditer(prompt_text):
        candidates.append(clean_candidate_path(match.group("path")))
    for match in UNQUOTED_PATH_RE.finditer(prompt_text):
        candidates.append(clean_candidate_path(match.group("path")))

    resolved: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        path = resolve_source_path(repo_root, candidate)
        key = str(path).lower()
        if key in seen:
            continue
        if path.exists() and path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            seen.add(key)
            resolved.append(path)
    return resolved


def detect_prompt_primary(prompt_text: str, source_paths: list[Path]) -> Path | None:
    """Detect an explicit primary-source hint from prompt text."""
    lowered = prompt_text.lower()
    for path in source_paths:
        variants = unique([str(path), path.name, path.as_posix()])
        for variant in variants:
            variant_lower = variant.lower()
            if not variant_lower or variant_lower not in lowered:
                continue
            patterns = [
                rf"{re.escape(variant_lower)}[^.\n]{{0,24}}(?:is|as)?[^.\n]{{0,12}}primary",
                rf"primary[^.\n]{{0,24}}{re.escape(variant_lower)}",
                rf"{re.escape(variant_lower)}[^\u3002\n]{{0,12}}\u4e3a\u4e3b",
                rf"\u4ee5[^\u3002\n]{{0,8}}{re.escape(variant_lower)}[^\u3002\n]{{0,8}}\u4e3a\u4e3b",
            ]
            if any(re.search(pattern, lowered) for pattern in patterns):
                return path
    return None


def classify_source_role(prompt_text: str, source_path: Path, primary_source: Path | None) -> str:
    """Classify a source role from prompt hints."""
    if primary_source and source_path == primary_source:
        return "authoritative"

    lowered = prompt_text.lower()
    variants = unique([source_path.name.lower(), source_path.as_posix().lower(), str(source_path).lower()])
    contextual_keywords = [
        "reference",
        "for reference",
        "context",
        "background",
        "appendix",
        "supporting note",
        "\u9644\u4ef6",
        "\u53c2\u8003",
        "\u80cc\u666f",
        "\u4ec5\u4f9b\u53c2\u8003",
    ]
    for variant in variants:
        if not variant or variant not in lowered:
            continue
        for keyword in contextual_keywords:
            if re.search(rf"{re.escape(variant)}[^.\n]{{0,20}}{re.escape(keyword)}", lowered) or re.search(
                rf"{re.escape(keyword)}[^.\n]{{0,20}}{re.escape(variant)}", lowered
            ):
                return "contextual"
    return "supporting"


def split_sentences(text: str) -> list[str]:
    """Split text into simple sentences."""
    normalized = normalize_text(text)
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def infer_prompt_sections(text: str) -> list[str]:
    """Infer pseudo-sections from a rich prompt to support complexity assessment."""
    section_map = [
        ("API", "api"),
        ("Integration", "integration"),
        ("Database", "database"),
        ("Auth", "auth"),
        ("Sync", "sync"),
        ("Queue", "queue"),
        ("Pipeline", "pipeline"),
        ("Storage", "storage"),
        ("Service", "service"),
        ("Validation", "validation"),
        ("Release safety", "release safety"),
    ]
    lowered = text.lower()
    return [label for label, keyword in section_map if keyword in lowered]


def infer_project_name(title: str, text: str, default_name: str) -> str:
    """Infer a project name."""
    title = normalize_text(title).lstrip("#").strip()
    patterns = [
        r"\bcalled\s+([A-Z][A-Za-z0-9_-]+)",
        r"\bnamed\s+([A-Z][A-Za-z0-9_-]+)",
        r"^\s*project\s*[:\uFF1A]\s*([A-Za-z0-9 _-]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return normalize_text(match.group(1))
    if title and title.lower() not in {"prompt input", "project-plan", "untitled project input"} and title.lower() not in GENERIC_TITLES:
        cleaned = re.sub(r"\b(html|docx|pdf)\b.*$", "", title, flags=re.IGNORECASE).strip(" -")
        if cleaned:
            return cleaned
    return default_name


def infer_prompt_snapshot(prompt_text: str, repo_root: Path) -> dict[str, Any]:
    """Infer structured fields from prompt-only input."""
    text = normalize_text(prompt_text)
    sentences = split_sentences(text)
    name = infer_project_name(first_non_empty_line(text)[:120], text, repo_root.name or "Project")
    project_type = "project"
    type_match = re.search(r"initialize this repository as (?:an?|the)\s+(.+?)(?:\s+called|\s+named|\.|,|\n)", text, re.IGNORECASE)
    if type_match:
        project_type = type_match.group(1).strip()

    stage_match = re.search(r"(?:stage is|stage[:\uFF1A])\s+([A-Za-z0-9-]+)", text, re.IGNORECASE)
    stage = stage_match.group(1).lower() if stage_match else ""

    goal_match = re.search(r"goal is to\s+(.+?)(?:[.\n]|$)", text, re.IGNORECASE)
    goal = goal_match.group(1).strip() if goal_match else (sentences[1].rstrip(".") if len(sentences) > 1 else "")

    users = find_labeled_value(text, ["users", "target users", "audience"])
    stack = extract_use_stack(text)

    constraints = []
    if stack:
        constraints.append("Use " + ", ".join(stack) + ".")
    constraints.extend([sentence.rstrip(".") for sentence in sentences if sentence.lower().startswith("do not ")])

    assumptions = ["Prompt order is authoritative when no primary source is explicitly identified."]
    if not goal:
        assumptions.append("The primary project outcome should be clarified before implementation planning goes deeper.")

    return {
        "name": name,
        "project_type": project_type,
        "stage": stage,
        "goal": goal.rstrip("."),
        "users": users.rstrip("."),
        "stack": stack,
        "constraints": unique(constraints),
        "assumptions": assumptions,
    }


def infer_prompt_overrides(prompt_text: str) -> dict[str, Any]:
    """Infer only explicit prompt-provided fields when file sources already exist."""
    text = normalize_text(prompt_text)
    explicit_name = re.search(r"\b(?:called|named)\s+([A-Z][A-Za-z0-9_-]+)", text)
    name = normalize_text(explicit_name.group(1)) if explicit_name else ""

    type_match = re.search(r"initialize this repository as (?:an?|the)\s+(.+?)(?:\s+called|\s+named|\.|,|\n)", text, re.IGNORECASE)
    project_type = type_match.group(1).strip() if type_match else ""

    stage_match = re.search(r"(?:stage is|stage[:\uFF1A])\s+([A-Za-z0-9-]+)", text, re.IGNORECASE)
    stage = stage_match.group(1).lower() if stage_match else ""

    goal_match = re.search(r"goal is to\s+(.+?)(?:[.\n]|$)", text, re.IGNORECASE)
    goal = goal_match.group(1).strip() if goal_match else ""

    users = find_labeled_value(text, ["users", "target users", "audience"])
    stack = []
    constraints = [line.strip() for line in text.splitlines() if line.lower().startswith("do not ")]

    return {
        "name": name,
        "project_type": project_type,
        "stage": stage,
        "goal": goal.rstrip("."),
        "users": users.rstrip("."),
        "stack": stack,
        "constraints": unique(constraints),
        "assumptions": [],
    }


def infer_file_snapshot(intake: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Infer a safe structured snapshot from file-based intake."""
    if intake.get("confidence", 0) < 0.5 and not intake.get("extracted_text", "").strip():
        return {
            "name": "",
            "project_type": "",
            "stage": "",
            "goal": "",
            "users": "",
            "stack": [],
            "constraints": [],
            "assumptions": [],
        }

    text = intake["extracted_text"]
    title = intake.get("title") or ""
    goal = find_section(text, ["goal", "primary goal"]) or find_labeled_value(text, ["goal", "primary goal", "objective", "purpose"])
    users = find_section(text, ["users", "target users"]) or find_labeled_value(text, ["users", "target users", "audience"])
    stack = find_section(text, ["stack", "tech stack", "technology stack"]) or find_labeled_value(
        text,
        ["stack", "tech stack", "technology stack"],
    )
    constraints = find_section(text, ["constraints"]) or find_labeled_value(text, ["constraints"])
    stage = find_labeled_value(text, ["stage"])
    project_type = find_labeled_value(text, ["type", "project type"])

    return {
        "name": infer_project_name(title, text, ""),
        "project_type": project_type,
        "stage": stage.lower(),
        "goal": goal.rstrip("."),
        "users": users.rstrip("."),
        "stack": split_list_items(stack) if stack else [],
        "constraints": unique([line.strip("- ") for line in constraints.splitlines() if line.strip()]) if constraints else [],
        "assumptions": [],
    }


def canonicalize_value(field: str, value: Any) -> str:
    """Canonicalize a field value for comparison."""
    if field in LIST_FIELDS:
        items = [normalize_text(str(item)).lower() for item in value or [] if normalize_text(str(item))]
        return " | ".join(sorted(unique(items)))
    return normalize_text(str(value or "")).lower()


def format_value(value: Any) -> str:
    """Format a field value for reports."""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "none"
    return str(value or "none")


def choose_field_value(field: str, candidates: list[dict[str, Any]]) -> tuple[Any, str | None, list[str], list[dict[str, Any]]]:
    """Choose a field value and describe conflicts."""
    non_empty = [item for item in candidates if canonicalize_value(field, item["value"])]
    if not non_empty:
        return [] if field in LIST_FIELDS else "", None, [], []

    ranked = sorted(
        non_empty,
        key=lambda item: (
            -PRIORITY_BY_ROLE[item["role"]],
            item["order"],
            -(item.get("confidence") or 0),
        ),
    )
    chosen = ranked[0]
    adopted_defaults: list[str] = []
    if chosen["role"] != "authoritative":
        adopted_defaults.append(
            f"Filled `{field}` from `{chosen['label']}` because the primary source did not provide a usable value."
        )
    differing = [item for item in non_empty[1:] if canonicalize_value(field, item["value"]) != canonicalize_value(field, chosen["value"])]
    return chosen["value"], chosen["label"], adopted_defaults, differing


def estimate_bundle_confidence(source_entries: list[dict[str, Any]], prompt_snapshot: dict[str, Any], conflict_count: int) -> float:
    """Estimate bundle-level confidence."""
    confidences = [entry["confidence"] for entry in source_entries]
    if not confidences and prompt_snapshot.get("goal"):
        return 0.97
    if not confidences:
        return 0.55
    base = confidences[0]
    if len(confidences) > 1:
        base += min(0.08, 0.02 * (len(confidences) - 1))
    base -= min(0.25, 0.05 * conflict_count)
    return round(clamp(base, 0.15, 0.99), 2)


def build_source_bundle(
    repo_root: Path,
    artifacts_dir: Path,
    prompt_text: str = "",
    source_paths: list[str] | None = None,
    primary_source: str | None = None,
) -> dict[str, Any]:
    """Build a normalized multi-source bundle."""
    source_paths = source_paths or []
    prompt_text = normalize_text(prompt_text)
    explicit_paths = [resolve_source_path(repo_root, item) for item in source_paths]
    prompt_paths = extract_prompt_source_candidates(prompt_text, repo_root)

    ordered_paths: list[Path] = []
    seen: set[str] = set()
    for path in [*explicit_paths, *prompt_paths]:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            ordered_paths.append(path)

    if primary_source:
        primary_path = resolve_source_path(repo_root, primary_source)
        key = str(primary_path).lower()
        if key not in seen:
            ordered_paths.insert(0, primary_path)
            seen.add(key)
    else:
        primary_path = detect_prompt_primary(prompt_text, ordered_paths)

    source_entries: list[dict[str, Any]] = []
    bundle_warnings: list[str] = []
    for index, path in enumerate(ordered_paths):
        runtime = collect_runtime_status(str(path), [])
        if not runtime["ok"]:
            checks = [check["message"] for check in runtime["checks"] if not check["ok"]]
            raise RuntimeError(
                "Runtime is missing required dependencies. "
                + " ".join(checks or [f"Use Python {runtime['minimum_python_version']}+"])
                + f" Install with `{runtime['install_hint']}`."
            )

        raw = extract_from_path(path)
        extracted_path = artifacts_dir / f"{index:02d}-{slugify(path.stem)}.extracted.md"
        normalized = normalize_intake(raw, str(extracted_path))
        role = classify_source_role(prompt_text, path, primary_path) if ordered_paths else "authoritative"
        snapshot = infer_file_snapshot(normalized, repo_root)
        source_entries.append(
            {
                "path": str(path),
                "label": path.name,
                "role": role,
                "detected_format": normalized["detected_format"],
                "title": normalized["title"],
                "extracted_text": normalized["extracted_text"],
                "extracted_text_path": normalized["extracted_text_path"],
                "sections": normalized["sections"],
                "confidence": normalized["confidence"],
                "warnings": normalized["warnings"],
                "word_count": normalized["word_count"],
                "provenance": normalized["provenance"],
                "snapshot": snapshot,
                "order": index,
            }
        )
        bundle_warnings.extend(normalized["warnings"])

    prompt_snapshot = infer_prompt_snapshot(prompt_text, repo_root) if prompt_text else {}
    prompt_contributions = infer_prompt_overrides(prompt_text) if prompt_text and source_entries else prompt_snapshot

    merged_snapshot: dict[str, Any] = {
        "name": "",
        "project_type": "",
        "stage": "",
        "goal": "",
        "users": "",
        "stack": [],
        "constraints": [],
        "assumptions": [],
    }
    field_sources: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    clarification_questions: list[str] = []
    adopted_defaults: list[str] = []

    prompt_candidate_role = "authoritative" if not source_entries else "supporting"
    prompt_candidates = []
    if prompt_text:
        for field in ("name", "project_type", "stage", "goal", "users", "stack", "constraints"):
            value = prompt_contributions.get(field)
            if canonicalize_value(field, value):
                prompt_candidates.append(
                    {
                        "field": field,
                        "value": value,
                        "role": prompt_candidate_role,
                        "label": "prompt",
                        "confidence": 0.97,
                        "order": -1,
                    }
                )

    for field in ("name", "project_type", "stage", "goal", "users", "stack", "constraints"):
        candidates = [
            {
                "field": field,
                "value": entry["snapshot"].get(field),
                "role": entry["role"],
                "label": entry["label"],
                "confidence": entry["confidence"],
                "order": entry["order"],
            }
            for entry in source_entries
        ]
        candidates.extend([item for item in prompt_candidates if item["field"] == field])

        chosen_value, chosen_from, field_defaults, differing = choose_field_value(field, candidates)
        merged_snapshot[field] = chosen_value
        if chosen_from:
            field_sources[field] = chosen_from
        adopted_defaults.extend(field_defaults)

        for item in differing:
            conflicts.append(
                {
                    "field": field,
                    "chosen_from": chosen_from,
                    "chosen_value": format_value(chosen_value),
                    "discarded_from": item["label"],
                    "discarded_value": format_value(item["value"]),
                    "reason": "Primary or higher-priority source wins.",
                }
            )

    merged_snapshot["assumptions"] = unique(
        [
            *prompt_snapshot.get("assumptions", []),
            "Prompt order determines source priority when the user does not explicitly identify a primary file.",
        ]
    )

    primary_entry = next((entry for entry in source_entries if entry["role"] == "authoritative"), None)
    if source_entries and not primary_entry:
        primary_entry = source_entries[0]

    if primary_entry and primary_entry["confidence"] < 0.5:
        clarification_questions.append(
            f"The default primary source `{primary_entry['label']}` was extracted with low confidence. Confirm whether it should remain authoritative."
        )

    for conflict in conflicts:
        if conflict["field"] in KEY_FIELDS:
            clarification_questions.append(
                f"Sources disagree on `{conflict['field']}`. Current choice uses `{conflict['chosen_from']}` over `{conflict['discarded_from']}`. Confirm the authoritative value."
            )

    if not merged_snapshot["goal"]:
        clarification_questions.append("The project goal is still unclear. Confirm the primary outcome before implementation proceeds.")

    if source_entries and not merged_snapshot["name"]:
        clarification_questions.append("The project name could not be recovered from the source bundle. Confirm the canonical project name.")

    bundle_confidence = estimate_bundle_confidence(source_entries, prompt_snapshot, len(conflicts))
    clarification_questions = unique(clarification_questions)
    bundle_warnings = unique(bundle_warnings)
    sections = unique(
        [
            *(section for entry in source_entries for section in entry["sections"]),
            *infer_prompt_sections(prompt_text),
        ]
    )[:20]

    if source_entries:
        top_source_type = "bundle" if len(source_entries) > 1 else "file"
        top_source_path = str(primary_entry["path"]) if primary_entry else str(source_entries[0]["path"])
        top_format = primary_entry["detected_format"] if primary_entry else source_entries[0]["detected_format"]
        top_text = primary_entry["extracted_text"] if primary_entry else source_entries[0]["extracted_text"]
        top_text_path = primary_entry["extracted_text_path"] if primary_entry else source_entries[0]["extracted_text_path"]
        top_title = merged_snapshot["name"] or (primary_entry["title"] if primary_entry else source_entries[0]["title"])
    else:
        top_source_type = "prompt"
        top_source_path = None
        top_format = "text"
        top_text = prompt_text
        top_text_path = None
        top_title = merged_snapshot["name"] or "Prompt input"

    return {
        "source_type": top_source_type,
        "source_path": top_source_path,
        "detected_format": top_format,
        "extracted_text": top_text,
        "extracted_text_path": top_text_path,
        "title": top_title,
        "sections": sections,
        "confidence": bundle_confidence,
        "warnings": bundle_warnings,
        "word_count": len(top_text.split()),
        "metadata": {
            "source_count": len(source_entries),
            "field_sources": field_sources,
        },
        "provenance": {
            "bundle_timestamp": utc_now_iso(),
            "builder": "build_source_bundle.py",
        },
        "sources": source_entries,
        "primary_source": str(primary_entry["path"]) if primary_entry else None,
        "source_count": len(source_entries),
        "merged_snapshot": merged_snapshot,
        "field_sources": field_sources,
        "conflicts": conflicts,
        "clarification_questions": clarification_questions,
        "bundle_confidence": bundle_confidence,
        "adopted_defaults": unique(adopted_defaults),
        "prompt_input": prompt_text or None,
        "source_roles": [
            {
                "path": entry["path"],
                "label": entry["label"],
                "role": entry["role"],
                "confidence": entry["confidence"],
            }
            for entry in source_entries
        ],
    }


def main() -> int:
    """Run the bundle builder."""
    args = parse_args()
    try:
        repo_root = Path(args.repo).resolve()
        artifacts_dir = Path(args.artifacts_dir).resolve()
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        prompt_text = load_prompt_text(args.prompt, args.prompt_file)
        bundle = build_source_bundle(repo_root, artifacts_dir, prompt_text, args.source, args.primary_source)
        write_json(bundle, args.output)
        return 0
    except Exception as exc:  # pragma: no cover - CLI entry point
        print(f"build_source_bundle.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
