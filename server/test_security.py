# -*- coding: utf-8 -*-
"""
Security tests for ComposeBridge MCP Server and Gradle Runner.
Verifies task allowlist enforcement, injection prevention, and dry_run support.
"""

import unittest
import json
import sys
from pathlib import Path

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent))

import mcp_server
from core.gradle_runner import is_task_allowed, ALLOWED_TASKS


class TestSecurity(unittest.TestCase):

    def test_allowed_gradle_tasks_direct(self):
        """Valid direct tasks from allowlist should be accepted."""
        for task in ["assembleDebug", "assembleRelease", "test", "lint", "clean"]:
            self.assertTrue(mcp_server.is_gradle_task_allowed(task), f"Task '{task}' should be allowed")
            self.assertTrue(is_task_allowed(task), f"Task '{task}' should be allowed in runner")

    def test_allowed_gradle_tasks_subproject(self):
        """Subproject tasks matching allowlist should be accepted."""
        for task in [
            ":composeApp:assembleDebug",
            ":composeApp:test",
            ":app:lint",
            ":app:clean",
            ":feature:login:assembleDebug",
        ]:
            self.assertTrue(mcp_server.is_gradle_task_allowed(task), f"Subproject task '{task}' should be allowed")
            self.assertTrue(is_task_allowed(task), f"Subproject task '{task}' should be allowed in runner")

    def test_disallowed_gradle_tasks(self):
        """Unauthorized tasks should be strictly rejected."""
        disallowed = [
            "publishToMavenLocal",
            "uploadArchives",
            "installDebug",
            "run",
            "exec",
            "help",
            ":app:dependencies",
        ]
        for task in disallowed:
            self.assertFalse(mcp_server.is_gradle_task_allowed(task), f"Task '{task}' should NOT be allowed")
            self.assertFalse(is_task_allowed(task), f"Task '{task}' should NOT be allowed in runner")

            # Check that run_gradle_build returns error JSON without executing
            result_json = mcp_server.run_gradle_build(task)
            result = json.loads(result_json)
            self.assertFalse(result["success"])
            self.assertIn("not allowed", result["error"])

    def test_gradle_command_injection_rejected(self):
        """Dangerous shell/flag characters must be strictly rejected."""
        malicious_payloads = [
            "assembleDebug; rm -rf /",
            "clean && echo hacked",
            "test | cat /etc/passwd",
            "assembleDebug --daemon",
            "assembleDebug -PcustomFlag=1",
            "`whoami`",
            "$(whoami)",
            "clean\nmalicious",
            "assembleDebug;calc.exe",
            "test & notepad.exe",
            "   ",
            "",
            None,
        ]
        for payload in malicious_payloads:
            self.assertFalse(
                mcp_server.is_gradle_task_allowed(payload),
                f"Malicious payload '{payload}' must be rejected",
            )
            result_json = mcp_server.run_gradle_build(payload)
            result = json.loads(result_json)
            self.assertFalse(result["success"])

    def test_list_allowed_gradle_tasks_tool(self):
        """list_allowed_gradle_tasks MCP tool returns the exact allowed tasks."""
        result_json = mcp_server.list_allowed_gradle_tasks()
        result = json.loads(result_json)
        self.assertTrue(result["success"])
        self.assertEqual(
            set(result["tasks"]),
            {"assembleDebug", "assembleRelease", "test", "lint", "clean"},
        )

    def test_replace_pattern_dry_run_not_found(self):
        """replace_pattern with non-existent pattern returns error safely."""
        result_json = mcp_server.replace_pattern("non_existent_pattern_123", dry_run=True)
        result = json.loads(result_json)
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])


if __name__ == "__main__":
    unittest.main()