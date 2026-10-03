Run the full ship routine from CLAUDE.md §3 for my current branch, step by step:

1. Run `make check`. If anything fails, fix it inside my stream's paths only, then re-run. Do not continue while red.
2. `git fetch origin && git rebase origin/main`.
3. If there is a conflict in a file my stream owns, resolve it carefully. If a conflicted file belongs to another stream or is LOCKED, run `git rebase --abort`, stop, and tell me which file and whose it is.
4. Run `make check` again.
5. Update `docs/streams/<my-stream>.md` if anything public changed, and append one timestamped line to `docs/progress/<my-stream>.md`. Commit with `[<stream>] docs`.
6. `git push -u origin HEAD`.
7. Open a PR with `gh pr create --base main` titled `[<stream>] <summary>` with a body covering: what changed, how it was tested, docs updated.
8. Wait for the CI check. If green AND every changed file is inside my stream's paths, merge with `gh pr merge --squash --delete-branch`. Otherwise do not merge; tell me why.
9. `git checkout main && git pull --ff-only`, then tell me the next task from my prompt.
