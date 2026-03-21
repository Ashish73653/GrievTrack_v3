# Contributing

Thanks for helping improve GrievTrack!

## How to get started
1. Fork and create a feature branch.
2. Set up a Python 3.10+ virtualenv.
3. Install deps: `pip install -r requirements.txt`.
4. Initialize the demo DB: `python db.py`.
5. Run tests: `python -m pytest`.

## Development tips
- Use `GRIEVTRACK_LEDGER_BACKEND=fabric_stub` to write anchors to `fabric_stub/anchored_log.jsonl` while keeping SQLite verification.
- Keep changes focused; avoid modifying DB schema unless agreed.
- Update docs in `docs/` and README when behavior changes.

## Submitting changes
- Ensure tests pass locally.
- Describe the change, motivation, and any demo steps in the PR template.
- Follow the Code of Conduct.
