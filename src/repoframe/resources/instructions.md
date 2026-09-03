# RepoFrame

Read the repository-local mode before multi-step work:

```bash
git config --local --get repoframe.mode
```

If it is unset, use Long Run when `.repoframe/state.json` exists; otherwise use Iteration.

## Iteration

Work quickly with the user and let Git record development. Do not create, read, or update execution state. Do not maintain a DAG, current-focus field, activity log, or per-save summary. Prefer small changes and frequent human acceptance.

## Long Run

1. Read `.repoframe/state.json` before starting or resuming.
2. Expand the DAG gradually from actual progress; it describes state, not permission.
3. Work in short design, development, and verification loops.
4. Update state at meaningful stage boundaries and immediately when blocked, materially replanned, or handed off.
5. Treat unresolved user interventions as durable input that can change the route.
6. Keep at most one node `active`; record short summaries and useful file, test, or commit evidence.
7. Do not record private reasoning, chat history, file saves, or details already clear from Git.
8. Run `repoframe validate` after changing state and end the execution path when the Goal is done.
