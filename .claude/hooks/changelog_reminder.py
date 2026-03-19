"""Stop hook: if .py/.md files were changed, remind to update CHANGELOG.md."""
import json
import os
import sys

TMP_FILE = os.path.join(os.environ.get("TEMP", "/tmp"), "claude_changelog_changed.txt")

if not os.path.exists(TMP_FILE):
    sys.exit(0)

with open(TMP_FILE, encoding="utf-8") as f:
    raw = f.read().strip().splitlines()

os.remove(TMP_FILE)

files = list(dict.fromkeys(raw))  # deduplicate, preserve order
if not files:
    sys.exit(0)

short_names = [os.path.basename(p) for p in files]
tail = " и ещё..." if len(short_names) > 8 else ""
names_str = ", ".join(short_names[:8]) + tail

msg = f"CHANGELOG.md — не забудь обновить! Изменены: {names_str}"
print(json.dumps({"systemMessage": msg}))
