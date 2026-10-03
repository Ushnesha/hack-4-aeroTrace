Bring my branch up to date without shipping:

1. Commit any finished work inside my stream's paths (never `git add .`).
2. `git fetch origin && git rebase origin/main`.
3. Resolve conflicts only in files my stream owns. For any other file: `git rebase --abort`, stop, and tell me.
4. Run `make check` and report the result.
5. Read `docs/requests/from-*.md` and tell me if any request is addressed to my stream.
