# animeko-sources

Generated Animeko media source export.

The public artifact is [`animeko.json`](./animeko.json). Raw URL:

```text
https://raw.githubusercontent.com/CrazyBunQnQ/animeko-sources/main/animeko.json
```

## Sync

The GitHub workflow runs daily at 10:00 Asia/Shanghai and commits changed generated files back to `main`.

Local run:

```powershell
python -m animeko_sources.sync merge --exclude-repo CrazyBunQnQ/animeko-sources --output animeko.json --result-out sync-summary.json
```

Tests:

```powershell
python -m unittest discover -s tests
```

The sync uses GitHub code search for JSON files containing `exportedMediaSourceDataList`, downloads candidates, excludes official-source duplicates, deduplicates GitHub candidates by source identity, and keeps the newest candidate when duplicates exist.

`GITHUB_TOKEN` is read from the environment when present. Do not put tokens in commands, files, commits, logs, or issues.

## Files

- `animeko.json`: Animeko export consumed by clients.
- `sync-summary.json`: sync status and redacted diagnostics.
- `animeko_sources/`: standard-library sync implementation.
- `.github/workflows/sync-animeko-sources.yml`: daily and manual publishing workflow.

## Disclaimer

This repository does not host, cache, or provide media content. It only publishes metadata discovered from public JSON source exports. Use sources responsibly and comply with applicable laws, platform terms, and content rights.
