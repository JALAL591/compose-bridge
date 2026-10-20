import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from core.scanner_kotlin_parser import scan_file_dimensions, scan_file_usages, scan_file_colors

class TestScannerScopeAndTypeFiltering(unittest.TestCase):

    def test_ignore_bare_numbers_in_dimensions(self):
        code = """
        object AppDimens {
            val validDp = 16.dp
            val validSp = 14.sp
            val validFloat = 2.5.f
            val bareNumber = 15
            val bareFloat = 20.0
        }
        """
        dims = scan_file_dimensions(code)
        dim_names = {d["name"] for d in dims}
        self.assertIn("validDp", dim_names)
        self.assertIn("validSp", dim_names)
        self.assertIn("validFloat", dim_names)
        self.assertNotIn("bareNumber", dim_names)
        self.assertNotIn("bareFloat", dim_names)

    def test_ignore_local_variables_in_functions(self):
        code = """
        @Composable
        fun MyChart() {
            Canvas(modifier = Modifier.fillMaxSize()) {
                val strokeWidth = 15.dp.toPx()
                val radius = 100.dp
            }
        }
        """
        dims = scan_file_dimensions(code)
        self.assertEqual(len(dims), 0, "Local variables inside functions/composables must not be registered as tokens")

    def test_qualified_scope_usages_resolution(self):
        usage_code = """
        package com.example.ui
        
        import androidx.compose.material3.CircularProgressIndicator
        
        @Composable
        fun ChatView() {
            // Parameter named strokeWidth should NOT match token strokeWidth
            CircularProgressIndicator(strokeWidth = 2.dp)
            
            // Qualified reference SHOULD match
            val color = AppColors.Primary
        }
        """
        # Search for strokeWidth
        usages_stroke = scan_file_usages(usage_code, {"strokeWidth"}, {"strokeWidth": None})
        self.assertEqual(len(usages_stroke), 0, "Named argument strokeWidth = 2.dp must not produce false positive")

        # Search for Primary with scope AppColors
        usages_color = scan_file_usages(usage_code, {"Primary"}, {"Primary": "AppColors"})
        self.assertEqual(len(usages_color), 1)
        self.assertEqual(usages_color[0]["token_name"], "Primary")

if __name__ == "__main__":
    unittest.main()
