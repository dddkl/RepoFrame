# RepoFrame

1. Before starting or resuming a multi-step goal, read `.repoframe/state.json`.
2. Choose the route freely; the DAG describes execution state, not permission to work.
3. Update state only when a stage starts, completes, blocks, skips, or materially changes.
4. Do not record file saves, private reasoning, chat history, or details already clear from Git.
5. Keep at most one node `active`.
6. Finish nodes with a short summary and useful file, test, or commit evidence when available.
7. Run `repoframe validate` after changing state.
8. On handoff, recover from state, repository contents, and Git history.

