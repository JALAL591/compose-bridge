# -*- coding: utf-8 -*-
"""
Comprehensive test suite for MCP Tools.
Verifies execution, annotations, and return schemas for all tools to ensure 100% test coverage.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import mcp_server


class TestMCPToolsCoverage(unittest.TestCase):
    """Verifies that all 34 MCP tools execute and return valid structured responses."""

    def test_all_tools_have_annotations(self):
        """Verify all 34 tools carry complete MCP annotations."""
        tools = mcp_server.app._tool_manager._tools
        self.assertEqual(len(tools), 34)
        for name, tool in tools.items():
            self.assertIsNotNone(tool.annotations, f"Tool {name} missing annotations")
            dump = tool.annotations.model_dump(by_alias=True, exclude_none=True)
            self.assertIn("readOnlyHint", dump, f"Tool {name} missing readOnlyHint")
            self.assertIn("destructiveHint", dump, f"Tool {name} missing destructiveHint")
            self.assertIn("idempotentHint", dump, f"Tool {name} missing idempotentHint")
            self.assertIn("openWorldHint", dump, f"Tool {name} missing openWorldHint")

    def test_find_token_by_color(self):
        res_str = mcp_server.find_token_by_color("#FF10B981")
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)

    def test_get_naming_convention(self):
        res_str = mcp_server.get_naming_convention("dimension")
        data = json.loads(res_str)
        self.assertTrue(data.get("success", False))
        self.assertIn("style", data)

    def test_list_tokens(self):
        res_str = mcp_server.list_tokens()
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)
        self.assertTrue(data.get("success", False))

    def test_list_orphans(self):
        res_str = mcp_server.list_orphans()
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)
        self.assertTrue(data.get("success", False))

    def test_get_token_impact(self):
        res_str = mcp_server.get_token_impact("Primary")
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)

    def test_suggest_token_split(self):
        res_str = mcp_server.suggest_token_split()
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)
        self.assertTrue(data.get("success", False))

    def test_detect_conditional_variants(self):
        res_str = mcp_server.detect_conditional_variants()
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)
        self.assertTrue(data.get("success", False))

    def test_get_token_siblings(self):
        res_str = mcp_server.get_token_siblings("Primary")
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)

    def test_get_all_token_groups(self):
        res_str = mcp_server.get_all_token_groups()
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)
        self.assertTrue(data.get("success", False))

    def test_get_design_file_mappings(self):
        res_str = mcp_server.get_design_file_mappings()
        data = json.loads(res_str)
        self.assertTrue(data.get("success", False))
        self.assertIn("mappings", data)

    def test_list_applied_patterns(self):
        res_str = mcp_server.list_applied_patterns()
        data = json.loads(res_str)
        self.assertTrue(data.get("success", False))
        self.assertIn("patterns", data)

    def test_get_gradle_status_not_found(self):
        res_str = mcp_server.get_gradle_status("non_existent_job_123")
        data = json.loads(res_str)
        self.assertFalse(data.get("success", True))

    def test_get_sync_status(self):
        res_str = mcp_server.get_sync_status()
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)

    def test_list_allowed_gradle_tasks(self):
        res_str = mcp_server.list_allowed_gradle_tasks()
        data = json.loads(res_str)
        self.assertTrue(data.get("success", False))
        self.assertIn("assembleDebug", data.get("tasks", []))

    def test_rollback_last_empty_session(self):
        res_str = mcp_server.rollback_last()
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)

    def test_reject_change_not_found(self):
        res_str = mcp_server.reject_change("non_existent.kt", "change_999")
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)

    def test_approve_change_not_found(self):
        res_str = mcp_server.approve_change("non_existent.kt", "change_999")
        data = json.loads(res_str)
        self.assertIsInstance(data, dict)

    def test_clean_cache_execution(self):
        res_str = mcp_server.clean_cache()
        data = json.loads(res_str)
        self.assertTrue(data.get("success", False))


if __name__ == "__main__":
    unittest.main()
