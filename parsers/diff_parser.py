"""
Unified Git Diff Parser.
Extracts changed line numbers per file from unified diff text.
"""
import re
from typing import Dict, Set, Optional


def parse_unified_diff(diff_text: str) -> Dict[str, Set[int]]:
    """
    Parse unified git diff text and return a dictionary mapping:
    relative_file_path -> set of changed line numbers (in the new file version).
    """
    file_changes: Dict[str, Set[int]] = {}
    current_file: Optional[str] = None
    current_line: int = 0

    hunk_header_re = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@")

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            raw_path = line[6:].strip()
            current_file = raw_path.replace("\\", "/")
            if current_file not in file_changes:
                file_changes[current_file] = set()
            continue
        elif line.startswith("--- "):
            continue

        match = hunk_header_re.match(line)
        if match:
            current_line = int(match.group(1))
            continue

        if current_file is None or current_line == 0:
            continue

        if line.startswith("+"):
            file_changes[current_file].add(current_line)
            current_line += 1
        elif line.startswith("-"):
            # Line removed; associate with corresponding line in new file
            file_changes[current_file].add(current_line)
        elif line.startswith(" "):
            current_line += 1

    return file_changes
