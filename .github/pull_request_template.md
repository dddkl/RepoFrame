## Summary

- describe the main change
- describe any important behavior or contract impact

## Validation

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python -m compileall -q src tests`
- [ ] Built and installed a wheel if package data or packaging changed
- [ ] Inspected the local viewer if browser behavior changed

List the exact commands you ran:

```bash
# commands here
```

## Protocol / Product Impact

- [ ] No state protocol changes
- [ ] Updated Schema, Python validation, and tests together if the protocol changed
- [ ] Preserved content outside RepoFrame adapter markers
- [ ] Kept Iteration independent of execution state
- [ ] Kept the viewer read-only or documented an explicitly approved boundary change

## Risk Notes

Call out anything that touches:

- schema-version compatibility
- atomic initialization or user-authored instruction files
- loopback HTTP security
- read-only Git inspection
- packaged browser resources
- Python 3.10 compatibility or runtime dependencies
