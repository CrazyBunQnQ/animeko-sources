from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Mapping

from animeko_sources.merge import (
    AnimekoSyncError,
    Json,
    MediaSource,
    SourceCandidate,
    merge_candidates,
    parse_source_document,
    sanitize_summary,
    write_json,
)

OFFICIAL_URL: Final = "https://sub.creamycake.org/v1/css1.json"
GITHUB_QUERY: Final = "exportedMediaSourceDataList language:JSON"
DEFAULT_OUTPUT: Final = "animeko.json"
DEFAULT_RESULT_OUT: Final = "sync-summary.json"


class HttpRequestError(RuntimeError):
    pass


def fetch_text(url: str, headers: Mapping[str, str]) -> str:
    request = urllib.request.Request(ascii_url(url), headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise HttpRequestError(f"HTTP {error.code} for {url}") from error
    except urllib.error.URLError as error:
        raise HttpRequestError(f"request failed for {url}: {error.reason}") from error


def github_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "animeko-sources-sync",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def ascii_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((
        parts.scheme,
        parts.netloc,
        urllib.parse.quote(parts.path, safe="/%"),
        urllib.parse.quote(parts.query, safe="=&%:+"),
        urllib.parse.quote(parts.fragment, safe="/%"),
    ))


def fetch_json(url: str, headers: Mapping[str, str]) -> Json:
    try:
        return json.loads(fetch_text(url, headers))
    except json.JSONDecodeError as error:
        raise AnimekoSyncError(f"response is not JSON: {url}") from error


def github_search_query(exclude_repo: str | None) -> str:
    if exclude_repo and exclude_repo.strip():
        return f"{GITHUB_QUERY} -repo:{exclude_repo.strip()}"
    return GITHUB_QUERY


def discover_github_files(
    headers: Mapping[str, str], max_results: int, exclude_repo: str | None = None
) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({"q": github_search_query(exclude_repo), "per_page": str(min(max_results, 100))})
    payload = fetch_json(f"https://api.github.com/search/code?{query}", headers)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []

    files: list[dict[str, str]] = []
    excluded_repo = exclude_repo.strip().lower() if exclude_repo else ""
    for item in items[:max_results]:
        if not isinstance(item, dict):
            continue
        repository = item.get("repository")
        path = item.get("path")
        url = item.get("url")
        if not isinstance(repository, dict) or not isinstance(path, str) or not isinstance(url, str):
            continue
        full_name = repository.get("full_name")
        if isinstance(full_name, str):
            if excluded_repo and full_name.lower() == excluded_repo:
                continue
            files.append({"repo": full_name, "path": path, "url": url, "html_url": str(item.get("html_url") or url)})
    return files


def latest_commit_date(headers: Mapping[str, str], repo: str, path: str) -> datetime:
    query = urllib.parse.urlencode({"path": path, "per_page": "1"})
    payload = fetch_json(f"https://api.github.com/repos/{repo}/commits?{query}", headers)
    if not isinstance(payload, list) or not payload:
        return datetime.min.replace(tzinfo=UTC)
    first_item = payload[0]
    if not isinstance(first_item, dict):
        return datetime.min.replace(tzinfo=UTC)
    commit = first_item.get("commit")
    if not isinstance(commit, dict):
        return datetime.min.replace(tzinfo=UTC)
    committer = commit.get("committer")
    if not isinstance(committer, dict):
        return datetime.min.replace(tzinfo=UTC)
    date = committer.get("date")
    if not isinstance(date, str):
        return datetime.min.replace(tzinfo=UTC)
    return _parse_datetime(date)


def download_github_file(headers: Mapping[str, str], api_url: str) -> str:
    payload = fetch_json(api_url, headers)
    download_url = payload.get("download_url") if isinstance(payload, dict) else None
    if not isinstance(download_url, str):
        raise AnimekoSyncError("GitHub content item has no download_url")
    return fetch_text(download_url, {})


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def run_merge(args: argparse.Namespace) -> int:
    github_token_env = str(args.github_token_env)
    official_url = str(args.official_url)
    output_path = Path(str(args.output))
    result_path = Path(str(args.result_out))
    max_results = int(args.max_results)
    exclude_repo = str(args.exclude_repo).strip() or None
    token = os.environ.get(github_token_env)
    headers = github_headers(token)
    skipped: list[dict[str, str]] = []
    files: list[dict[str, str]] = []

    official_sources = parse_source_document(fetch_text(official_url, {}))
    if official_sources is None:
        raise AnimekoSyncError("official Animeko source is not an exportedMediaSourceDataList JSON")

    try:
        files = discover_github_files(headers, max_results, exclude_repo)
    except HttpRequestError as error:
        summary = sanitize_summary({
            "status": "failed",
            "phase": "github_search",
            "official_sources": len(official_sources),
            "official_url": official_url,
            "github_query": github_search_query(exclude_repo),
            "excluded_repo": exclude_repo or "",
            "used_github_token": bool(token),
            "reason": str(error),
        })
        write_json(result_path, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    candidates: list[SourceCandidate] = []
    for file_info in files:
        try:
            candidates.append(SourceCandidate(
                media_sources=parse_candidate_media_sources(headers, file_info),
                commit_date=latest_commit_date(headers, file_info["repo"], file_info["path"]),
                source_url=file_info["html_url"],
            ))
        except (AnimekoSyncError, HttpRequestError) as error:
            skipped.append({"url": file_info["html_url"], "reason": str(error)})

    output, summary = merge_candidates(official_sources, candidates)
    safe_summary = sanitize_summary(summary | {
        "status": "ok" if not skipped else "partial",
        "official_url": official_url,
        "github_query": github_search_query(exclude_repo),
        "excluded_repo": exclude_repo or "",
        "github_files": len(files),
        "downloaded_candidates": len(candidates),
        "skipped_candidates": skipped,
        "used_github_token": bool(token),
    })
    write_json(output_path, output)
    write_json(result_path, safe_summary)
    print(json.dumps(safe_summary, ensure_ascii=False, indent=2))
    return 0


def parse_candidate_media_sources(
    headers: Mapping[str, str], file_info: Mapping[str, str]
) -> list[MediaSource]:
    media_sources = parse_source_document(download_github_file(headers, file_info["url"]))
    if media_sources is None:
        raise AnimekoSyncError("malformed_json")
    return media_sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge Animeko media source JSON files.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    merge = subparsers.add_parser("merge")
    merge.add_argument("--official-url", default=OFFICIAL_URL)
    merge.add_argument("--output", default=DEFAULT_OUTPUT)
    merge.add_argument("--result-out", default=DEFAULT_RESULT_OUT)
    merge.add_argument("--max-results", type=int, default=30)
    merge.add_argument("--github-token-env", default="GITHUB_TOKEN")
    merge.add_argument("--exclude-repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    merge.set_defaults(func=run_merge)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
