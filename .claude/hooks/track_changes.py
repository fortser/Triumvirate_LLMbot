"""PostToolUse hook: tracks changed .py and .md files to a temp file."""
import json
import os
import re
import sys

SKIP_PATTERNS = ["CHANGELOG", "LLM_report", "TESTING_GUIDE", "оглавление", "оглавление"]
TMP_FILE = os.path.join(os.environ.get("TEMP", "/tmp"), "claude_changelog_changed.txt")

data = json.load(sys.stdin)
fp = data.get("tool_input", {}).get("file_path", "")

if not fp:
    sys.exit(0)

is_py = re.search(r"\.py$", fp)
is_md = re.search(r"\.md$", fp) and not any(x in fp for x in SKIP_PATTERNS)

if is_py or is_md:
    with open(TMP_FILE, "a", encoding="utf-8") as f:
        f.write(fp + "\n")
