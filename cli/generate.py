# -*- coding: utf-8 -*-
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from assembler import assemble_screen
from generators.theme import generate_theme
from generators.bridge_registries import generate_bridge_registries
from component_templates import generate_components_from_json


def copy_agent_module(output_dir):
    """Copies composebridge-agent module from repository."""
    repo_root = Path(__file__).parent.parent
    agent_src = repo_root / "agent"
    agent_dst = Path(output_dir) / "composebridge-agent"

    if agent_src.exists():
        if agent_dst.exists():
            shutil.rmtree(agent_dst)
        shutil.copytree(agent_src, agent_dst,
                        ignore=shutil.ignore_patterns('build', '*.bak'))
        print(f"  ✅ Copied: composebridge-agent/")
    else:
        print(f"  ⚠️ Agent not found at {agent_src}")


def copy_server_module(output_dir, package_name):
    """Copies bridge/ (Python server) from repository."""
    repo_root = Path(__file__).parent.parent
    server_src = repo_root / "server"
    server_dst = Path(output_dir) / "bridge"

    if server_src.exists():
        if server_dst.exists():
            shutil.rmtree(server_dst)
        shutil.copytree(
            server_src, server_dst,
            ignore=shutil.ignore_patterns('__pycache__', '*.bak', 'logs')
        )

        # Replace PROJECT_ROOT in all Python files
        project_root_str = str(Path(output_dir).absolute()).replace("\\", "\\\\")

        import re
        for py_file in server_dst.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                content = re.sub(
                    r'PROJECT_ROOT\s*=\s*Path\(r"[^"]*"\)',
                    lambda m: f'PROJECT_ROOT = Path(r"{project_root_str}")',
                    content
                )
                py_file.write_text(content, encoding="utf-8")
            except Exception as e:
                print(f"  ⚠️ Failed to update {py_file.name}: {e}")

        print(f"  ✅ Copied: bridge/")


def copy_android_templates(output_dir, config):
    """Copies Android files from templates/ with placeholder replacement."""
    templates_dir = Path(__file__).parent / "templates"

    if not templates_dir.exists():
        print(f"  ⚠️ Templates folder not found")
        return

    package = config["package"]
    package_path = package.replace(".", "/")

    # File paths mapping
    files_map = {
        "MainActivity.kt": f"app/src/main/java/{package_path}/MainActivity.kt",
        "AndroidManifest.xml": "app/src/main/AndroidManifest.xml",
        "GlobalPanels.kt": f"app/src/main/java/{package_path}/ui/panels/GlobalPanels.kt",
        "settings.gradle.kts": "settings.gradle.kts",
        "build.gradle.kts": "build.gradle.kts",
        "app_build.gradle.kts": "app/build.gradle.kts",
        "gradle.properties": "gradle.properties",
        "themes.xml": "app/src/main/res/values/themes.xml",
        "libs.versions.toml": "gradle/libs.versions.toml",
    }

    for template_name, dest_rel in files_map.items():
        src = templates_dir / template_name
        if not src.exists():
            print(f"  ⚠️ Template not found: {template_name}")
            continue

        content = src.read_text(encoding="utf-8")

        # Replace placeholders
        content = content.replace("{{PACKAGE}}", package)
        content = content.replace("{{PACKAGE_PATH}}", package_path)
        content = content.replace("{{APP_NAME}}", config.get("app_name", "TestApp"))
        content = content.replace("{{PROJECT_NAME}}", config.get("project_name", "TestApp"))

        dst = Path(output_dir) / dest_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")

    print(f"  ✅ Copied + adapted {len(files_map)} template files")


def main():
    print()
    print("=" * 60)
    print("  ComposeBridge - Dynamic UI Compiler")
    print("=" * 60)
    print()

    json_path = sys.argv[1] if len(sys.argv) > 1 else "screens/dashboard.json"

    print(f"  Reading: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        screen_json = json.load(f)

    project_name = "TestApp"
    app_name = "TestApp"
    package = screen_json["package"]
    output = Path(f"./output/{project_name}")
    source_root = output / "app" / "src" / "main" / "java"
    package_path = source_root / package.replace(".", "/")

    screen_json["output_dir"] = str(output)
    screen_json["source_root"] = str(source_root)
    screen_json["package_path"] = str(package_path)

    print("  Generating bridge registries...")
    generate_bridge_registries(screen_json)

    print("  Generating theme...")
    generate_theme(screen_json)

    print("  Generating components...")
    generate_components_from_json(screen_json, str(package_path))

    print(f"  Assembling: {screen_json['screen_name']}")
    kotlin_code = assemble_screen(screen_json)

    page_path = package_path / "ui/pages" / f"{screen_json['screen_name']}Page.kt"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(kotlin_code, encoding="utf-8")

    print("  📦 Copying ComposeBridge modules...")
    copy_agent_module(output)
    copy_server_module(output, package)

    print("  📄 Copying templates...")
    copy_android_templates(output, {
        "package": package,
        "app_name": app_name,
        "project_name": project_name,
    })

    print()
    print("=" * 60)
    print(f"  Project: {output}")
    print("=" * 60)
    print()
    print(f"  cd {output}")
    print("  # Open in Android Studio")
    print()


if __name__ == "__main__":
    main()
