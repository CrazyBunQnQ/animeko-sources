from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowContractTest(unittest.TestCase):
    def test_workflow_when_read_then_publishes_root_files_and_excludes_current_repo(self) -> None:
        workflow = Path(".github/workflows/sync-animeko-sources.yml").read_text(encoding="utf-8")

        self.assertIn("cron: '0 2 * * *'", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("--exclude-repo \"${{ github.repository }}\"", workflow)
        self.assertIn("--output animeko.json", workflow)
        self.assertIn("--result-out sync-summary.json", workflow)
        self.assertIn("git add animeko.json sync-summary.json", workflow)
        self.assertNotIn("output/animeko", workflow)
        self.assertNotIn("HEAD:animeko", workflow)
        self.assertNotIn("push --force", workflow)


if __name__ == "__main__":
    unittest.main()
