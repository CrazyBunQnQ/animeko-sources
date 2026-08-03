from __future__ import annotations

import unittest
from unittest.mock import patch

from animeko_sources.sync import DEFAULT_OUTPUT, DEFAULT_RESULT_OUT, ascii_url, discover_github_files, github_search_query


class AnimekoSyncTest(unittest.TestCase):
    def test_defaults_when_imported_then_publish_root_files(self) -> None:
        self.assertEqual("animeko.json", DEFAULT_OUTPUT)
        self.assertEqual("sync-summary.json", DEFAULT_RESULT_OUT)

    def test_github_search_query_when_exclude_repo_present_then_adds_negative_repo_filter(self) -> None:
        query = github_search_query(" CrazyBunQnQ/animeko-sources ")

        self.assertEqual("exportedMediaSourceDataList language:JSON -repo:CrazyBunQnQ/animeko-sources", query)

    def test_ascii_url_when_path_has_cjk_then_percent_encodes_request_path(self) -> None:
        url = "https://api.github.com/repos/example/repo/contents/动画/源.json?ref=main"

        encoded = ascii_url(url)

        self.assertEqual(
            "https://api.github.com/repos/example/repo/contents/%E5%8A%A8%E7%94%BB/%E6%BA%90.json?ref=main",
            encoded,
        )

    def test_discover_github_files_when_exclude_repo_matches_then_skips_configured_repo(self) -> None:
        payload = {
            "items": [
                {
                    "repository": {"full_name": "CrazyBunQnQ/animeko-sources"},
                    "path": "animeko.json",
                    "url": "https://api.github.com/repos/CrazyBunQnQ/animeko-sources/contents/animeko.json",
                    "html_url": "https://github.com/CrazyBunQnQ/animeko-sources/blob/main/animeko.json",
                },
                {
                    "repository": {"full_name": "external/animeko"},
                    "path": "sources.json",
                    "url": "https://api.github.com/repos/external/animeko/contents/sources.json",
                    "html_url": "https://github.com/external/animeko/blob/main/sources.json",
                },
            ]
        }

        with patch("animeko_sources.sync.fetch_json", return_value=payload):
            files = discover_github_files({}, 30, "crazybunqnq/animeko-sources")

        self.assertEqual(
            [
                {
                    "repo": "external/animeko",
                    "path": "sources.json",
                    "url": "https://api.github.com/repos/external/animeko/contents/sources.json",
                    "html_url": "https://github.com/external/animeko/blob/main/sources.json",
                }
            ],
            files,
        )


if __name__ == "__main__":
    unittest.main()
