# Project Compatibility

Use this reference when deciding how `PROJECT.md` should behave around existing user-authored project materials.

## Source modes

### `generated`

Use when:

- there is no prior project plan
- the repository is being initialized directly from prompt input

Behavior:

- `PROJECT.md` becomes the primary project-definition document
- write the standard structured fields directly in `PROJECT.md`

### `user-authored`

Use when:

- the user already provided the authoritative project plan in another file
- that file should remain the source of truth

Behavior:

- preserve the original source file
- use `PROJECT.md` as an agent-readable compatibility layer
- record the source path
- summarize key facts without copying the entire source text

### `mixed`

Use when:

- the repository already has partial `PROJECT.md` content
- the user also supplied an external plan or updated source material

Behavior:

- preserve user-owned text
- supplement `PROJECT.md` with a snapshot and linkage
- avoid full rewrites unless the user explicitly asks for them

## Minimum snapshot content

When `PROJECT.md` is acting as a compatibility layer, include at least:

- source mode
- original source path
- rewrite policy
- project identity
- primary goal
- key constraints
- explicit assumptions

## Preservation rules

- Do not rewrite user-authored project plans by default.
- Do not duplicate the full source plan inside `PROJECT.md`.
- If the user requests reformatting, preserve a reference to the original file whenever practical.
- If the source is weak or incomplete, add assumptions and a clarification task instead of inventing structure.
