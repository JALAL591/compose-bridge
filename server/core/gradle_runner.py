# -*- coding: utf-8 -*-
"""
Gradle Runner — تشغيل مهام Gradle والتحقق من النتائج.

Safety:
- Whitelist للمهام المسموحة.
- Timeout قابل للتعديل.
- لا shell=True (منع injection).
"""

import subprocess
import time
import os
from pathlib import Path
from typing import Dict, Optional


# ⚠️ قائمة المهام المسموحة فقط
ALLOWED_TASKS = {
    ":composeApp:compileDebugKotlinAndroid",
    ":composeApp:compileDebugKotlin",
    ":composeApp:compileKotlinDesktop",
    ":composeApp:assembleDebug",
    ":app:compileDebugKotlin",
    ":app:compileDebugKotlinAndroid",
    ":app:assembleDebug",
    "compileDebugKotlin",
    "compileDebugKotlinAndroid",
    "compileKotlin",
    "compileKotlinDesktop",
    "build",
    "assembleDebug",
    "clean",
    "test",
}


def _find_gradlew(project_root: Path) -> Optional[Path]:
    """ابحث عن gradlew / gradlew.bat."""
    candidates = [
        project_root / "gradlew.bat",
        project_root / "gradlew",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def run_gradle_build(
    project_root: Path,
    task: str = "compileDebugKotlin",
    timeout_seconds: int = 300,
) -> Dict:
    """
    Run a gradle task and return structured result.
    
    Args:
        project_root: root of the Gradle project.
        task: gradle task (must be in ALLOWED_TASKS).
        timeout_seconds: max execution time (default 5 min).
    
    Returns:
        {
            "success": bool,
            "task": str,
            "exit_code": int,
            "duration_ms": int,
            "timed_out": bool,
            "errors": [...],       # lines with "e:" or "FAILED" or "error:"
            "warnings": [...],     # lines with "w:"
            "output_tail": str,    # آخر 30 سطر
        }
    """
    if task not in ALLOWED_TASKS:
        return {
            "success": False,
            "task": task,
            "error": f"Task '{task}' is not in whitelist. Allowed: {sorted(ALLOWED_TASKS)}",
        }
    
    gradlew = _find_gradlew(project_root)
    if not gradlew:
        return {
            "success": False,
            "task": task,
            "error": f"gradlew not found in {project_root}",
        }
    
    start = time.time()
    timed_out = False
    exit_code = -1
    output = ""
    
    try:
        # ⚠️ لا نستخدم shell=True
        cmd = [str(gradlew), task, "--console=plain", "--no-daemon"]
        
        process = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "GRADLE_OPTS": "-Dorg.gradle.daemon=false"},
        )
        
        try:
            output, _ = process.communicate(timeout=timeout_seconds)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = -1
            if os.name == "nt":
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
                except Exception:
                    process.kill()
            else:
                process.kill()
            try:
                output, _ = process.communicate(timeout=3)
            except Exception:
                pass
    
    except Exception as e:
        return {
            "success": False,
            "task": task,
            "error": str(e),
            "duration_ms": int((time.time() - start) * 1000),
        }
    
    duration_ms = int((time.time() - start) * 1000)
    
    # ⭐ استخراج الأخطاء والتحذيرات
    errors = []
    warnings = []
    for line in output.splitlines():
        if line.startswith("e:") or " error: " in line or "FAILED" in line.upper():
            errors.append(line.strip())
        elif line.startswith("w:") or " warning: " in line:
            warnings.append(line.strip())
    
    success = exit_code == 0 and not timed_out
    
    return {
        "success": success,
        "task": task,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "timed_out": timed_out,
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "errors": errors[:20],
        "warnings": warnings[:20],
        "output_tail": "\n".join(output.splitlines()[-30:]),
    }
