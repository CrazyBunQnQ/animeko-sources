from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from animeko_sources.merge import (
    SourceCandidate,
    build_export,
    merge_candidates,
    parse_source_document,
    sanitize_summary,
    source_identity,
    write_json,
)


class AnimekoMergeTest(unittest.TestCase):
    def test_parse_source_document_when_valid_export_then_returns_media_sources(self) -> None:
        document = json.dumps(build_export([{"identity": "alpha"}, {"identity": "beta"}]))

        sources = parse_source_document(document)

        self.assertEqual([{"identity": "alpha"}, {"identity": "beta"}], sources)

    def test_parse_source_document_when_malformed_then_returns_none(self) -> None:
        document = json.dumps({"exportedMediaSourceDataList": {"items": []}})

        sources = parse_source_document(document)

        self.assertIsNone(sources)

    def test_source_identity_when_fields_vary_then_uses_expected_fallback_order(self) -> None:
        self.assertEqual("id-a", source_identity({"identity": " ID-A "}))
        self.assertEqual("name-a", source_identity({"arguments": {"name": " Name-A "}}))
        self.assertEqual(
            "https://example.com/search",
            source_identity({"arguments": {"searchConfig": {"searchUrl": " https://example.com/search "}}}),
        )
        self.assertEqual(
            json.dumps(["factory", 1, {"factoryId": "factory", "version": 1}], ensure_ascii=True, sort_keys=True),
            source_identity({"factoryId": "factory", "version": 1}),
        )

    def test_merge_candidates_when_duplicates_and_official_overlap_then_keeps_newest_non_official(self) -> None:
        official_sources = [{"identity": "official-only"}]
        older = SourceCandidate(
            media_sources=[{"identity": "dup", "value": "old"}, {"identity": "official-only"}],
            commit_date=datetime(2024, 1, 1, tzinfo=UTC),
            source_url="https://github.com/example/old.json",
        )
        newer = SourceCandidate(
            media_sources=[{"identity": "dup", "value": "new"}, {"identity": "unique"}],
            commit_date=datetime(2024, 2, 1, tzinfo=UTC),
            source_url="https://github.com/example/new.json",
        )

        export, summary = merge_candidates(official_sources, [older, newer])

        self.assertEqual(
            [{"identity": "dup", "value": "new"}, {"identity": "unique"}],
            export["exportedMediaSourceDataList"]["mediaSources"],
        )
        self.assertEqual(
            {
                "official_sources": 1,
                "candidate_sources": 4,
                "excluded_official": 1,
                "deduped_sources": 1,
                "output_sources": 2,
            },
            summary,
        )

    def test_sanitize_summary_when_secret_like_values_then_redacts_tokens(self) -> None:
        summary = {
            "github": "ghp_1234567890abcdef",
            "openai": "sk-12345678abcdef",
            "auth": "Bearer abc.def-ghi",
        }

        sanitized = sanitize_summary(summary)

        self.assertEqual({"github": "[REDACTED]", "openai": "[REDACTED]", "auth": "[REDACTED]"}, sanitized)

    def test_write_json_when_parent_missing_then_creates_formatted_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "result.json"

            write_json(path, {"status": "ok"})

            self.assertEqual("{\n  \"status\": \"ok\"\n}\n", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
