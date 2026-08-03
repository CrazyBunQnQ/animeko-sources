from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Mapping, Sequence, TypeAlias

Json: TypeAlias = None | bool | int | float | str | Sequence["Json"] | Mapping[str, "Json"]
MediaSource: TypeAlias = Mapping[str, Json]
AnimekoExport: TypeAlias = Mapping[str, Mapping[str, Sequence[MediaSource]]]

SECRET_PATTERNS: Final = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{12,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
)


class AnimekoSyncError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    media_sources: list[MediaSource]
    commit_date: datetime
    source_url: str


def parse_source_document(document: str) -> list[MediaSource] | None:
    try:
        parsed = json.loads(document)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None
    exported = parsed.get("exportedMediaSourceDataList")
    if not isinstance(exported, dict):
        return None
    media_sources = exported.get("mediaSources")
    if not isinstance(media_sources, list):
        return None

    return [source for source in media_sources if isinstance(source, dict)]


def _clean_string(value: Json) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return None


def source_identity(source: MediaSource) -> str:
    identity = _clean_string(source.get("identity"))
    if identity:
        return identity

    arguments = source.get("arguments")
    if isinstance(arguments, dict):
        name = _clean_string(arguments.get("name"))
        if name:
            return name
        search_config = arguments.get("searchConfig")
        if isinstance(search_config, dict):
            search_url = _clean_string(search_config.get("searchUrl"))
            if search_url:
                return search_url

    return json.dumps(
        [source.get("factoryId"), source.get("version"), source],
        ensure_ascii=True,
        sort_keys=True,
    )


def build_export(media_sources: list[MediaSource]) -> AnimekoExport:
    return {"exportedMediaSourceDataList": {"mediaSources": media_sources}}


def merge_candidates(
    official_sources: Sequence[MediaSource], candidates: Sequence[SourceCandidate]
) -> tuple[AnimekoExport, dict[str, int]]:
    official_ids = {source_identity(source) for source in official_sources}
    winners: dict[str, tuple[datetime, int, MediaSource]] = {}
    seen_sources = 0
    excluded_official = 0
    ordinal = 0

    for candidate in sorted(candidates, key=lambda item: item.commit_date, reverse=True):
        for source in candidate.media_sources:
            seen_sources += 1
            identity = source_identity(source)
            if identity in official_ids:
                excluded_official += 1
                continue
            current = winners.get(identity)
            if current is None or candidate.commit_date > current[0]:
                winners[identity] = (candidate.commit_date, ordinal, source)
            ordinal += 1

    media_sources = [entry[2] for entry in sorted(winners.values(), key=lambda item: item[1])]
    return build_export(media_sources), {
        "official_sources": len(official_sources),
        "candidate_sources": seen_sources,
        "excluded_official": excluded_official,
        "deduped_sources": seen_sources - excluded_official - len(media_sources),
        "output_sources": len(media_sources),
    }


def sanitize_summary(value: Json) -> Json:
    if isinstance(value, dict):
        return {key: sanitize_summary(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_summary(item) for item in value]
    if isinstance(value, str):
        redacted = value
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    return value


def write_json(path: Path, payload: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
