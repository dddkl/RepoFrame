# Intake

Use this reference to normalize repository-initialization input before deciding what to write.

## Supported sources

- natural-language prompt
- local `.md`
- local `.txt`
- local `.docx`
- local `.pdf`
- local `.html`

## Separation of concerns

Keep these responsibilities separate:

- `extract_project_source.py`: extract raw text and file metadata
- `normalize_project_intake.py`: shape the extraction into the stable intake schema
- executor logic: choose mode and write policy

Do not let extraction scripts choose `greenfield`, `plan-ingest`, or `repo-hydrate`.

## Normalized intake schema

The normalized JSON must contain at least:

- `source_type`
- `source_path`
- `detected_format`
- `extracted_text`
- `extracted_text_path`
- `title`
- `sections`
- `confidence`
- `warnings`

Recommended additional fields:

- `word_count`
- `provenance`
- `metadata`

## Provenance rules

Preserve:

- original source path
- extraction timestamp
- extraction script name and version
- known extraction limitations

This matters because PDF, DOCX, and HTML extraction may lose hierarchy, tables, or embedded context.

## Warning rules

Emit warnings when:

- OCR would be required
- a PDF page has no extractable text
- table structure was flattened
- headings could not be detected reliably
- extracted text is unexpectedly short

Low-confidence intake should push the executor toward preservation and clarification.

## Storage guidance

When intermediate artifacts are persisted, prefer:

```text
.repoframe/intake/
```

Useful artifacts:

- raw extraction JSON
- normalized intake JSON
- extracted text snapshots

For the installable skill, the preferred repository-local artifact root is:

```text
.repo-init/
```

Storing artifacts is optional only when cleanup is explicitly requested. Otherwise keep the path stable and predictable.
