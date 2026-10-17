import subprocess
import sys
from pathlib import Path

# ⭐ الكود لكل عملية
CODE1 = """
from core.state_editor import update_token_default
for i in range(10):
    ok, msg, _ = update_token_default('welcomeCardHeight', f'1{i:02d}')
    print(f'P1_write_{i}_ok={ok}_val=1{i:02d}', flush=True)
"""

CODE2 = """
from core.state_editor import update_token_default
for i in range(10):
    ok, msg, _ = update_token_default('welcomeCardHeight', f'2{i:02d}')
    print(f'P2_write_{i}_ok={ok}_val=2{i:02d}', flush=True)
"""

# ⭐ شغّل العمليتين في نفس الوقت
p1 = subprocess.Popen(
    [sys.executable, "-c", CODE1],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8"
)
p2 = subprocess.Popen(
    [sys.executable, "-c", CODE2],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8"
)

out1, err1 = p1.communicate(timeout=30)
out2, err2 = p2.communicate(timeout=30)

# ⭐ اطبع raw
print("=" * 60)
print("RAW OUTPUT — Process 1 (writes 100-109)")
print("=" * 60)
print(out1)
if err1:
    print("STDERR P1:", err1)

print("=" * 60)
print("RAW OUTPUT — Process 2 (writes 200-209)")
print("=" * 60)
print(out2)
if err2:
    print("STDERR P2:", err2)

# ⭐ افحص الملف
file_path = Path("../app/src/main/java/com/student/app/ui/theme/AppDimens.kt")
print("=" * 60)
print("FINAL FILE CONTENT (welcomeCardHeight line)")
print("=" * 60)
for line in file_path.read_text(encoding="utf-8").splitlines():
    if "welcomeCardHeight" in line:
        print(line.strip())

# ⭐ تحقق من Lock file
lock = Path("../.composebridge-state/.write.lock")
print("=" * 60)
print(f"LOCK FILE EXISTS AFTER TEST: {lock.exists()}")
print("=" * 60)
