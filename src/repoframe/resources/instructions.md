# RepoFrame

## Iteration

Use Iteration for rapid collaboration with a user. Work normally and use Git as the development record. Do not create, read, or update `.repoframe/state.json` for Iteration. Do not maintain a DAG, current-focus field, activity log, or per-save summary.

## Long Run

Use Long Run for a longer autonomous Goal that must survive interruption or handoff.

1. Before starting or resuming, read `.repoframe/state.json`.
2. Expand the DAG gradually from actual progress; it describes state, not permission to work.
3. Update state when a meaningful stage starts or completes, or immediately when blocked, materially replanned, or handed off.
4. Keep at most one node `active`; use short summaries and useful file, test, or commit evidence.
5. Do not record private reasoning, chat history, file saves, or details already clear from Git.
6. Run `repoframe validate` after changing state and end the execution path when the Goal is done.
