## Summary

- describe the main change
- describe any important behavior or contract impact

## Validation

- [ ] `python -m py_compile ...` for touched scripts
- [ ] `python repo-init/scripts/smoke_initialize_repo.py`
- [ ] `python repo-init/scripts/doctor.py` if file-ingest behavior changed

List the exact commands you ran:

```bash
# commands here
```

## Contract / Template Impact

- [ ] No generated contract changes
- [ ] Updated `repo-init/references/` if generated output changed
- [ ] Updated `template/` if generated output changed

## Risk Notes

Call out anything that touches:

- mode selection
- write policy
- adaptive goal/task planning
- artifact compatibility
- runtime / dependency assumptions
