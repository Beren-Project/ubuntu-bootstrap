"""Cleanup discovery must prove ownership by this invocation, not a name."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import podman_runner


class CleanupDiscoveryTests(unittest.TestCase):
    def test_interrupted_creation_requires_unique_run_label_and_full_ids(self):
        identifier = "a" * 64
        with patch.object(podman_runner, "run", return_value=SimpleNamespace(stdout=identifier + "\n")) as run:
            self.assertEqual(podman_runner.discover_created("unique-run"), [identifier])
        run.assert_called_once_with("ps", "-a", "--no-trunc", "--filter",
                                    "name=^ubuntu-bootstrap-integration$", "--filter",
                                    "label=org.beren-project.ubuntu-bootstrap.run=unique-run",
                                    "--format", "{{.ID}}", capture=True)

    def test_no_matching_run_does_not_claim_existing_project_container(self):
        with patch.object(podman_runner, "run", return_value=SimpleNamespace(stdout="")):
            self.assertEqual(podman_runner.discover_created("another-run"), [])
