"""
Unit tests for data sources: LocalLoader and GitHubClient.
"""
import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from sources.local_loader import LocalLoader
from sources.github_client import GitHubClient


class TestSources(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.file1 = os.path.join(self.temp_dir, "test.py")
        with open(self.file1, "w") as f:
            f.write("def foo(): pass\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_local_loader(self):
        loader = LocalLoader(self.temp_dir)
        files = loader.load_all_files()
        self.assertIn("test.py", files)
        self.assertEqual(files["test.py"], "def foo(): pass\n")

    def test_github_client_slug_parsing(self):
        client = GitHubClient("psf/requests")
        self.assertEqual(client.owner, "psf")
        self.assertEqual(client.repo, "requests")

        client_url = GitHubClient("https://github.com/psf/requests")
        self.assertEqual(client_url.owner, "psf")
        self.assertEqual(client_url.repo, "requests")

        with self.assertRaises(ValueError):
            GitHubClient("invalid_slug")

    @patch("requests.get")
    def test_github_client_tree_fetch(self, mock_get):
        # Mock default branch
        mock_branch_resp = MagicMock()
        mock_branch_resp.status_code = 200
        mock_branch_resp.json.return_value = {"default_branch": "main"}

        # Mock git trees
        mock_tree_resp = MagicMock()
        mock_tree_resp.status_code = 200
        mock_tree_resp.json.return_value = {
            "tree": [
                {"path": "core.py", "type": "blob"},
                {"path": "README.md", "type": "blob"}
            ]
        }

        # Mock raw file content
        mock_raw_resp = MagicMock()
        mock_raw_resp.status_code = 200
        mock_raw_resp.text = "def core_func(): return 1\n"

        mock_get.side_effect = [mock_branch_resp, mock_tree_resp, mock_raw_resp]

        client = GitHubClient("test_owner/test_repo")
        files = client.load_all_files()

        self.assertIn("core.py", files)
        self.assertEqual(files["core.py"], "def core_func(): return 1\n")
        self.assertNotIn("README.md", files)  # not in supported code extensions


if __name__ == "__main__":
    unittest.main()
