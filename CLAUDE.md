# animeko-sources Project Rules

## Purpose

This repository publishes a generated Animeko media source export at the repository root as `animeko.json`.

## Contracts

- `animeko.json` is the public artifact and must keep the Animeko export shape: `exportedMediaSourceDataList.mediaSources`.
- `sync-summary.json` records sync status, counts, skipped candidates, and redacted diagnostics.
- GitHub source discovery must exclude this repository. The CLI default reads `GITHUB_REPOSITORY`; workflows must also pass `--exclude-repo "${{ github.repository }}"` explicitly.
- The sync tool uses only the Python standard library unless a future change documents and tests a dependency first.
- Secrets are never written to command arguments, files, commits, logs, or summaries. Summary text must redact token-like values.

## Workflow

- Daily sync runs at 10:00 Asia/Shanghai, represented as `0 2 * * *` in GitHub Actions because cron is UTC.
- The workflow commits only `animeko.json` and `sync-summary.json` when generated content changes.
- No force push, no global dependency installation, no database or schema changes.

## Local Discipline

- Run `python -m unittest discover -s tests` before committing.
- Validate generated JSON with `python -m json.tool animeko.json` and `python -m json.tool sync-summary.json`.
- Keep this project independent. Do not import from or modify `H:\MyPrograms\TV`.
