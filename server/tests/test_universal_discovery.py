# -*- coding: utf-8 -*-
"""
Unit tests for Universal Discovery & Design Scatter Scanner.
Validates:
1. Discovery of scattered tokens across arbitrary files.
2. Saving and reading design file mappings in .composebridge/config.json.
3. Graceful degradation: write protection returns NEEDS_MANUAL_MAPPING when no registry exists.
4. MCP discovery tools execution and formatting.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from analysis.universal_scanner import (
    scan_design_scatter,
    save_design_file_mapping,
    get_design_file_mappings,
    resolve_target_design_file,
)
from core.token_migrator import TokenMigrator
from mcp.tools.discovery import (
    analyze_design_scatter as mcp_analyze_design_scatter,
    set_design_file_mapping as mcp_set_design_file_mapping,
    get_design_file_mappings as mcp_get_design_file_mappings,
)


class TestUniversalDiscovery(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_universal_discovery_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scan_design_scatter_detects_tokens_and_recommends_registries(self):
        """Verify scanner locates scattered colors, dimensions, and strings."""
        theme_dir = self.root / "ui" / "theme"
        theme_dir.mkdir(parents=True, exist_ok=True)

        widgets_dir = self.root / "ui" / "widgets"
        widgets_dir.mkdir(parents=True, exist_ok=True)

        # 1. Colors file
        color_file = theme_dir / "Color.kt"
        color_file.write_text("""package com.example.app.ui.theme
import androidx.compose.ui.graphics.Color

val Purple80 = Color(0xFFD0BCFF)
val PurpleGrey80 = Color(0xFFCCC2DC)
val White = Color.White
""", encoding="utf-8")

        # 2. Dimens file
        dimen_file = theme_dir / "Dimens.kt"
        dimen_file.write_text("""package com.example.app.ui.theme
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val PaddingSmall = 8.dp
val PaddingLarge = 24.dp
val TitleSize = 18.sp
""", encoding="utf-8")

        # 3. Strings file
        string_file = theme_dir / "Strings.kt"
        string_file.write_text("""package com.example.app.ui.theme

object AppStrings {
    val Welcome = "Welcome to the App"
    val LoginBtn = "Sign In"
}
""", encoding="utf-8")

        # 4. Widget with mixed definitions
        widget_file = widgets_dir / "ProfileWidget.kt"
        widget_file.write_text("""package com.example.app.ui.widgets
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

fun ProfileWidget() {
    val HeaderColor = Color(0xFF336699)
    val AvatarSize = 64.dp
}
""", encoding="utf-8")

        report = scan_design_scatter(self.root)

        self.assertTrue(report.get("success"))
        summary = report["summary"]
        self.assertGreaterEqual(summary["total_colors"], 4)
        self.assertGreaterEqual(summary["total_dimensions"], 4)
        self.assertGreaterEqual(summary["total_strings"], 2)

        recommended = report["recommended_registries"]
        color_recs = [f.replace("\\", "/") for f in recommended["color"]]
        dimen_recs = [f.replace("\\", "/") for f in recommended["dimension"]]
        string_recs = [f.replace("\\", "/") for f in recommended["string"]]

        self.assertTrue(any("Color.kt" in r for r in color_recs), f"Color.kt not in {color_recs}")
        self.assertTrue(any("Dimens.kt" in r for r in dimen_recs), f"Dimens.kt not in {dimen_recs}")
        self.assertTrue(any("Strings.kt" in r for r in string_recs), f"Strings.kt not in {string_recs}")

    def test_set_and_get_design_file_mapping(self):
        """Verify saving and reading mappings in .composebridge/config.json."""
        color_path = "src/commonMain/kotlin/ui/Color.kt"
        dimen_path = "src/commonMain/kotlin/ui/Dimens.kt"

        save_res = save_design_file_mapping("color", color_path, self.root)
        self.assertTrue(save_res["success"])
        self.assertEqual(save_res["mapped_file"], color_path)

        save_res2 = save_design_file_mapping("dimension", dimen_path, self.root)
        self.assertTrue(save_res2["success"])

        mappings = get_design_file_mappings(self.root)
        self.assertEqual(mappings.get("color"), color_path)
        self.assertEqual(mappings.get("dimension"), dimen_path)

        cfg_file = self.root / ".composebridge" / "config.json"
        self.assertTrue(cfg_file.exists())
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        self.assertIn("design_files", data)
        self.assertEqual(data["design_files"]["color"], color_path)

    def test_resolve_target_design_file_prioritizes_mapping(self):
        """Verify that configured mapping takes priority over candidate discovery."""
        theme_dir = self.root / "theme"
        theme_dir.mkdir(parents=True, exist_ok=True)
        custom_dir = self.root / "custom_tokens"
        custom_dir.mkdir(parents=True, exist_ok=True)

        std_file = theme_dir / "Theme.kt"
        std_file.write_text("val DefaultColor = Color(0xFF000000)", encoding="utf-8")

        custom_file = custom_dir / "MyPalette.kt"
        custom_file.write_text("val CustomColor = Color(0xFF112233)", encoding="utf-8")

        # 1. Without mapping, standard candidate is resolved
        found_file, source = resolve_target_design_file("color", self.root)
        self.assertIsNotNone(found_file)
        self.assertEqual(found_file.name, "Theme.kt")
        self.assertEqual(source, "standard_candidate")

        # 2. With mapping, custom file takes priority
        rel_custom = "custom_tokens/MyPalette.kt"
        save_design_file_mapping("color", rel_custom, self.root)

        found_mapped, source_mapped = resolve_target_design_file("color", self.root)
        self.assertIsNotNone(found_mapped)
        self.assertEqual(found_mapped.name, "MyPalette.kt")
        self.assertEqual(source_mapped, "config_mapping")

    def test_graceful_degradation_blocks_write_when_no_registry(self):
        """Verify write guard stops execution and returns NEEDS_MANUAL_MAPPING if no registry exists."""
        # Project with only a Screen file, NO design system, NO Theme, NO AppColors
        screen_file = self.root / "HomeScreen.kt"
        screen_content = """package com.example.app
import androidx.compose.ui.graphics.Color
fun HomeScreen() {
    val bg = Color(0xFF123456)
}
"""
        screen_file.write_text(screen_content, encoding="utf-8")

        migrator = TokenMigrator(self.root)

        # Attempt to create color token
        res = migrator.create_color_token("BrandColor", "0xFF123456")

        # MUST fail safely with NEEDS_MANUAL_MAPPING
        self.assertFalse(res.get("success"))
        self.assertIn("NEEDS_MANUAL_MAPPING", res.get("error", "") + res.get("error_code", ""))

        # Verify HomeScreen.kt was NOT touched or corrupted
        self.assertEqual(screen_file.read_text(encoding="utf-8"), screen_content)

    def test_text_editor_stops_and_returns_needs_manual_mapping_without_registry(self):
        """Verify text editor stops and returns NEEDS_MANUAL_MAPPING if no centralized string file exists."""
        from editor.text_editor import update_text_in_source
        from mcp.tools.text import set_text

        # Project with only a Screen file, NO AppStrings.kt, NO Strings.kt
        screen_file = self.root / "HomeScreen.kt"
        screen_content = """package com.example.app
import androidx.compose.material.Text
import androidx.compose.runtime.Composable

@Composable
fun HomeScreen() {
    Text("Welcome to App")
}
"""
        screen_file.write_text(screen_content, encoding="utf-8")

        # 1. Direct function call check
        ok, msg, info = update_text_in_source(
            file_path="HomeScreen.kt",
            line=7,
            old_text="Welcome to App",
            new_text="Hello World",
            project_root=self.root,
        )

        self.assertFalse(ok)
        self.assertIn("NEEDS_MANUAL_MAPPING", msg)
        self.assertEqual((info or {}).get("error_code"), "NEEDS_MANUAL_MAPPING")

        # Verify HomeScreen.kt was NOT modified!
        self.assertEqual(screen_file.read_text(encoding="utf-8"), screen_content)

        # 2. MCP set_text tool check
        mcp_res = json.loads(set_text(
            token_name="Welcome to App",
            new_value="Hello World",
            file_path="HomeScreen.kt",
            line=7,
        ))
        self.assertFalse(mcp_res.get("success"))
        self.assertEqual(mcp_res.get("error_code"), "NEEDS_MANUAL_MAPPING")
        self.assertIn("NEEDS_MANUAL_MAPPING", mcp_res.get("error", ""))

        # Verify HomeScreen.kt remains strictly untainted!
        self.assertEqual(screen_file.read_text(encoding="utf-8"), screen_content)

    def test_dimension_editor_stops_and_returns_needs_manual_mapping_without_registry(self):
        """Verify dimension editor stops and returns NEEDS_MANUAL_MAPPING if no dimension registry exists."""
        from editor.dimension_editor import update_token_default

        ok, msg, info = update_token_default("PaddingLarge", "24.dp")
        self.assertFalse(ok)
        self.assertIn("NEEDS_MANUAL_MAPPING", msg)
        self.assertEqual((info or {}).get("error_code"), "NEEDS_MANUAL_MAPPING")

    def test_mcp_tools_discovery_execution(self):
        """Verify MCP tools format JSON cleanly and execute without exceptions."""
        ui_dir = self.root / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        color_file = ui_dir / "Color.kt"
        color_file.write_text("val Red = Color(0xFFFF0000)", encoding="utf-8")

        # Tool 1: analyze_design_scatter
        json_scatter = mcp_analyze_design_scatter(str(self.root))
        scatter_obj = json.loads(json_scatter)
        self.assertTrue(scatter_obj.get("success"))
        self.assertIn("summary", scatter_obj)

        # Tool 2: set_design_file_mapping
        json_set = mcp_set_design_file_mapping("color", "ui/Color.kt", str(self.root))
        set_obj = json.loads(json_set)
        self.assertTrue(set_obj.get("success"))
        self.assertEqual(set_obj.get("mapped_file"), "ui/Color.kt")

        # Tool 3: get_design_file_mappings
        json_get = mcp_get_design_file_mappings(str(self.root))
        get_obj = json.loads(json_get)
        self.assertTrue(get_obj.get("success"))
        self.assertEqual(get_obj["mappings"].get("color"), "ui/Color.kt")

    def test_non_ui_files_and_constants_are_excluded(self):
        """Verify non-UI data models (like SyncPacket.kt) and constants are excluded."""
        model_dir = self.root / "model"
        model_dir.mkdir(parents=True, exist_ok=True)

        # 1. Non-UI data model with @SerialName and PacketTypes constants
        sync_packet = model_dir / "SyncPacket.kt"
        sync_packet.write_text("""package com.example.model
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class SyncPacket(
    @SerialName("v")
    val protocolVersion: Int = 2,
    @SerialName("t")
    val type: String,
    @SerialName("p")
    val payload: String
)

object PacketTypes {
    const val REGISTER_STUDENT = "REG"
    const val REQUEST_LESSONS = "REQ_LSN"
    const val LESSON_PUSH = "PUSH_LSN"
}
""", encoding="utf-8")

        # 2. UI screen with real UI texts and invisible colors
        ui_dir = self.root / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        dashboard = ui_dir / "DashboardScreen.kt"
        dashboard.write_text("""package com.example.ui
import androidx.compose.runtime.Composable
import androidx.compose.material.Text
import androidx.compose.ui.graphics.Color

@Composable
fun DashboardScreen() {
    // Commented out: val OldColor = Color(0xFF999999)
    val TransparentColor = Color.Transparent
    val UnspecifiedColor = Color.Unspecified
    val RealColor = Color(0xFF10B981)

    Text("Welcome to Dashboard")
}
""", encoding="utf-8")

        report = scan_design_scatter(self.root)
        self.assertTrue(report["success"])

        scattered_files = [f["file"] for f in report["scatter_files"]]
        # SyncPacket.kt MUST NOT be in scattered files
        self.assertFalse(any("SyncPacket.kt" in f for f in scattered_files), f"SyncPacket.kt should not be scattered: {scattered_files}")

        # DashboardScreen.kt MUST be present
        self.assertTrue(any("DashboardScreen.kt" in f for f in scattered_files))

        # DashboardScreen MUST NOT have invisible colors counted (Transparent, Unspecified)
        dash_entry = next(f for f in report["scatter_files"] if "DashboardScreen.kt" in f["file"])
        self.assertEqual(dash_entry["counts"]["color"], 1)  # Only RealColor
        self.assertGreaterEqual(dash_entry["counts"]["string"], 1)  # Text("Welcome to Dashboard")
        self.assertFalse(dash_entry["is_candidate_registry"])  # Screens are NOT candidate registries!

    def test_mcp_categorized_reports_and_context_limits(self):
        """Verify MCP analyze_design_scatter supports categories and stays within context limits."""
        ui_dir = self.root / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        # Create a candidate registry
        (ui_dir / "DesignSystem.kt").write_text("val Brand = Color(0xFF112233)\nval Gap = 16.dp", encoding="utf-8")
        # Create 3 UI files needing fix
        for i in range(3):
            (ui_dir / f"Screen{i}.kt").write_text(f"""package com.example.ui
import androidx.compose.runtime.Composable
import androidx.compose.material.Text
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

@Composable
fun Screen{i}() {{
    val c = Color(0xFF00{i:02d}00)
    val d = {8 * (i+1)}.dp
    Text("Title {i}")
}}
""", encoding="utf-8")

        # 1. Test category="colors"
        res_colors = json.loads(mcp_analyze_design_scatter(category="colors", project_root=str(self.root), limit=2))
        self.assertTrue(res_colors["success"])
        self.assertIn("colors_report", res_colors)
        self.assertNotIn("dimensions_report", res_colors)
        self.assertNotIn("strings_report", res_colors)
        self.assertLessEqual(len(res_colors["colors_report"]), 2)
        # Candidate registry should not be in needing fix report
        self.assertFalse(any("DesignSystem.kt" in r["file"] for r in res_colors["colors_report"]))

        # 2. Test category="dimensions"
        res_dimens = json.loads(mcp_analyze_design_scatter(category="dimensions", project_root=str(self.root)))
        self.assertTrue(res_dimens["success"])
        self.assertIn("dimensions_report", res_dimens)

        # 3. Test category="strings"
        res_strings = json.loads(mcp_analyze_design_scatter(category="strings", project_root=str(self.root)))
        self.assertTrue(res_strings["success"])
        self.assertIn("strings_report", res_strings)

        # 4. Test category="all" (concise summary and strict limits)
        json_all = mcp_analyze_design_scatter(category="all", project_root=str(self.root), limit=10)
        res_all = json.loads(json_all)
        self.assertTrue(res_all["success"])
        self.assertIn("summary", res_all)
        self.assertEqual(res_all["summary"]["total_files_needing_fix"], 3)
        self.assertIn("colors_report", res_all)
        self.assertIn("dimensions_report", res_all)
        self.assertIn("strings_report", res_all)

        # Verify strict line and character limits for context safety
        self.assertLessEqual(len(json_all.splitlines()), 100)
        self.assertLess(len(json_all), 2000)


if __name__ == "__main__":
    unittest.main()

