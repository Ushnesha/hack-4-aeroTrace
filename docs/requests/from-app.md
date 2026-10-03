# Requests from the app stream

## To analysis: make `run_id` change when the working tree changes (needed by Sat 19:00)

CONTRACTS §3 builds `run_id` from commit, variant, defines, include paths and analyzer versions.
For the staleness demo we edit a file and re-analyze. If that edit is uncommitted, none of those
inputs change, so the new run gets the same `run_id` and no claim can be compared or marked STALE.
Please include a hash of the analyzed sources (or at least the `dirty` flag plus a diff hash) in
the `run_id` inputs, or tell us the demo must commit between runs.

## To graph: support a blank query with `kinds` in `find_symbols` (needed by Sat 12:30)

The fake now lists every symbol of the given kinds when `query` is blank and `kinds` is set
(`[contracts] find_symbols`). The overview page uses it to count unresolved calls. Please make the
real repository do the same; a blank query with no `kinds` may still return nothing.
