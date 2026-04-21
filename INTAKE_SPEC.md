# INTAKE_SPEC.md

This file defines how initialization inputs are discovered, extracted, normalized, and handed to the executor.

The intake layer exists so that repository initialization can accept real project materials, not only clean text prompts.

## Objective

Convert heterogeneous project inputs into a stable intermediate representation that the initialization executor can consume.

The intake layer should separate extraction from interpretation.

## Supported Input Types

The intake layer should be able to handle:

- direct natural-language prompt
- local Markdown or text files
- local office documents
- local PDFs
- local HTML exports
- existing repository documents

## Recommended Format Support

### Phase 1

Support these formats first:

- `.md`
- `.txt`
- `.docx`
- `.pdf`
- `.html`

### Phase 2

Add these when needed:

- `.pptx`
- `.xlsx`
- `.csv`
- `.json`

## Intake Responsibilities

The intake layer should:

1. identify the input source or sources
2. detect file format
3. extract text and basic metadata
4. preserve the source reference
5. normalize the result into a common structure
6. emit warnings when extraction quality is uncertain

The intake layer should not decide initialization mode or rewrite policy. That is executor logic.

## Intermediate Representation

The normalized intake result should contain at least:

- `source_type`
- `source_path`
- `detected_format`
- `extracted_text`
- `extracted_text_path`
- `title`
- `sections`
- `confidence`
- `warnings`

Example:

```json
{
  "source_type": "file",
  "source_path": "docs/project-plan.docx",
  "detected_format": "docx",
  "extracted_text": "Project name: FlowLedger ...",
  "extracted_text_path": ".repoframe/intake/project-plan.extracted.md",
  "title": "FlowLedger Project Plan",
  "sections": ["Background", "Goals", "Scope", "Tech Stack"],
  "confidence": 0.88,
  "warnings": []
}
```

## Provenance Requirements

Every extracted result should preserve provenance:

- original source path
- extraction timestamp
- extraction tool or script version
- known limitations

This is required because extraction may lose formatting, tables, or embedded diagrams.

## Extraction Quality Rules

The intake layer should emit warnings when:

- OCR was required
- the file appears image-heavy
- tables may have been flattened
- headings could not be reliably detected
- the extracted text is unusually short for the source file

If confidence is low, the executor should prefer a conservative write policy.

## Repository Storage Convention

If extracted artifacts are stored in the repository, the recommended location is:

- `.repoframe/intake/`

Possible artifacts:

- extracted text
- metadata JSON
- extraction warnings

This folder is optional at the current specification stage, but the path convention should remain stable if later implemented.

## Script Boundary

This specification assumes a future implementation with at least two scripts:

- `extract_project_source.py`
- `normalize_project_intake.py`

Recommended responsibilities:

- `extract_project_source.py`: file-format-specific extraction
- `normalize_project_intake.py`: conversion into the intermediate representation

The exact implementation language is not fixed by this spec.

## Prompt-Only Intake

If the user provides only a natural-language prompt, the intake layer may bypass file extraction and directly emit a normalized representation with:

- `source_type: prompt`
- `detected_format: text`
- `source_path: none`

## Non-Goals

The intake layer is not responsible for:

- deciding project scope
- deciding initialization mode
- rewriting project plans
- updating repository collaboration files

## Future Skill Boundary

This specification is intended to become the intake contract for a future repository-initialization skill.

The future skill should implement extraction and normalization in scripts, then feed the normalized result into the executor defined in `INIT_EXECUTOR_SPEC.md`.
