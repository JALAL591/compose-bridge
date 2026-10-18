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



    def test_parser_thread_safety(self):
        """AST Parser is protected with PARSER_LOCK for thread safety."""
        import threading
        from core.ast_finder import PARSER_LOCK, parse_bytes

        self.assertIsNotNone(PARSER_LOCK)
        errors = []

        def worker():
            try:
                for _ in range(20):
                    tree = parse_bytes(b'val x = 1')
                    self.assertIsNotNone(tree)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Parser thread safety errors: {errors}")

    def test_dynamic_property_resolution_tree_sitter(self):
        """BridgeState properties are extracted dynamically via Tree-sitter without hardcoded patterns."""
        import core.state_editor as se
        self.assertFalse(hasattr(se, 'PROPERTY_PATTERNS'), 'PROPERTY_PATTERNS must be deleted')
        
        ok, new_val, info = se.update_bridge_state('cardPadding', '16.dp')
        self.assertTrue(ok)
        self.assertEqual(info['old_value'], '16.dp')
        self.assertTrue(info['byte_start'] < info['byte_end'])

    def test_composebridge_json_config(self):
        """composebridge.json configuration file exists and contains path mappings."""
        import core.state_editor as se
        cfg_paths = se.get_config_paths()
        self.assertIsInstance(cfg_paths, dict)
        self.assertIn('bridge_state', cfg_paths)

    def test_no_sleep_in_mcp_server(self):
        """time.sleep(0.8) must be removed from mcp_server.py."""
        server_path = Path(__file__).parent / 'mcp_server.py'
        text = server_path.read_text(encoding='utf-8')
        self.assertNotIn('time.sleep(0.8)', text)

    def test_atomic_write_helper_token_migrator(self):
        """_atomic_write_text in token_migrator writes atomically."""
        from core.token_migrator import _atomic_write_text
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'test.txt'
            _atomic_write_text(target, 'atomic content')
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding='utf-8'), 'atomic content')


if __name__ == "__main__":
    unittest.main()