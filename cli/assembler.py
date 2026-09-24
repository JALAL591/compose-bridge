# -*- coding: utf-8 -*-
from registry import get_renderer


def _indent(text, spaces):
    prefix = " " * spaces
    return "\n".join(prefix + line if line.strip() else line for line in text.split("\n"))


def _collect_imports(screen_json):
    package = screen_json["package"]

    imports = {
        "androidx.compose.foundation.background",
        "androidx.compose.foundation.layout.*",
        "androidx.compose.foundation.rememberScrollState",
        "androidx.compose.foundation.verticalScroll",
        "androidx.compose.material.icons.Icons",
        "androidx.compose.material.icons.filled.*",
        "androidx.compose.runtime.Composable",
        "androidx.compose.ui.Alignment",
        "androidx.compose.ui.Modifier",
        "androidx.compose.ui.unit.dp",
        f"{package}.ui.theme.AppColors",
        f"{package}.ui.theme.AppDimens",
    }

    used_types = set()
    if "header" in screen_json:
        used_types.add(screen_json["header"]["type"])
    if "hero" in screen_json:
        used_types.add(screen_json["hero"]["type"])
    if "bottom_bar" in screen_json:
        used_types.add(screen_json["bottom_bar"]["type"])
    for comp in screen_json.get("components", []):
        used_types.add(comp["type"])

    component_map = {
        "HeroCard": "HeroCard",
        "StatCard": "StatCard",
        "StatGrid": "StatCard",
        "SectionTitle": "SectionTitle",
        "DashboardHeader": "DashboardHeader",
        "FloatingBottomBar": "FloatingBottomBar",
    }

    for ctype in used_types:
        kt_name = component_map.get(ctype)
        if kt_name:
            imports.add(f"{package}.ui.components.{kt_name}")

    return sorted(imports)


def assemble_screen(screen_json):
    screen_name = screen_json["screen_name"]
    package = screen_json["package"]

    header_code = ""
    if "header" in screen_json:
        h = screen_json["header"]
        props = h.get("props", {})
        header_code = f"""DashboardHeader(
    name = "{props.get('name', '')}",
    level = "{props.get('level', '')}",
)
"""

    hero_code = ""
    if "hero" in screen_json:
        hero = screen_json["hero"]
        renderer = get_renderer(hero["type"])
        if renderer:
            hero_code = renderer(hero.get("props", {}))

    body_parts = []
    for comp in screen_json.get("components", []):
        renderer = get_renderer(comp["type"])
        if renderer:
            body_parts.append(renderer(comp.get("props", {})))

    body_code = "\nSpacer(Modifier.height(AppDimens.md))\n".join(body_parts)

    bottom_bar_code = ""
    if "bottom_bar" in screen_json:
        bottom_bar_code = """FloatingBottomBar(
    modifier = Modifier.align(Alignment.BottomCenter),
)"""

    imports = _collect_imports(screen_json)
    imports_block = "\n".join(f"import {imp}" for imp in imports)

    kotlin_code = f"""package {package}.ui.pages

{imports_block}

@Composable
fun {screen_name}Page(
    modifier: Modifier = Modifier,
) {{
    Box(modifier = modifier.fillMaxSize()) {{
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
        ) {{
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(AppColors.Primary)
            ) {{
{_indent(header_code, 16)}

                Spacer(Modifier.height(AppDimens.md))

{_indent(hero_code, 16)}

                Spacer(Modifier.height(AppDimens.md))
            }}

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = AppDimens.md, bottom = 100.dp)
            ) {{
{_indent(body_code, 16)}
            }}
        }}

{_indent(bottom_bar_code, 8)}
    }}
}}
"""
    return kotlin_code
