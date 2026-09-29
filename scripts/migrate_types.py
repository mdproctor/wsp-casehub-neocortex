#!/usr/bin/env python3
"""Migrate Java files from blocks to neocortex with package replacement.

Usage: python3 scripts/migrate_types.py < migration_list.txt

Each line: src_rel_path | target_module | target_subpackage
Lines starting with # are comments.
"""
import re
import sys
from pathlib import Path

BLOCKS = Path("/Users/mdproctor/claude/casehub/slots/203/blocks/blocks-core")
NEO = Path("/Users/mdproctor/claude/casehub/slots/203/neocortex")

OLD_PKG_PREFIXES = [
    "io.casehub.blocks.agentic.social.drive.adaptation",
    "io.casehub.blocks.agentic.social.drive",
    "io.casehub.blocks.agentic.social.narrative",
    "io.casehub.blocks.agentic.social.goal",
    "io.casehub.blocks.agentic.social.emergence",
    "io.casehub.blocks.agentic.social.belief",
    "io.casehub.blocks.agentic.social.need",
    "io.casehub.blocks.agentic.social.prompt",
    "io.casehub.blocks.agentic.social",
]
NEW_PKG_PREFIX = "io.casehub.neocortex.cognition"

def replace_packages(content, target_subpkg):
    new_pkg = f"{NEW_PKG_PREFIX}.{target_subpkg}" if target_subpkg else NEW_PKG_PREFIX
    content = re.sub(r'^package\s+[\w.]+;', f"package {new_pkg};", content, count=1, flags=re.MULTILINE)
    for old in OLD_PKG_PREFIXES:
        content = content.replace(f"import {old}.", f"import {NEW_PKG_PREFIX}.")
    content = re.sub(
        r'import io\.casehub\.neocortex\.cognition\.(\w+)\.\1\.',
        r'import io.casehub.neocortex.cognition.\1.',
        content
    )
    return content

def migrate(src_rel, target_module, target_subpkg):
    src = BLOCKS / src_rel
    if not src.exists():
        print(f"SKIP (not found): {src.name}")
        return False
    content = src.read_text()
    content = replace_packages(content, target_subpkg)
    new_pkg = f"{NEW_PKG_PREFIX}.{target_subpkg}" if target_subpkg else NEW_PKG_PREFIX
    target_dir = NEO / target_module / "src/main/java" / new_pkg.replace(".", "/")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / src.name
    if target_file.exists():
        print(f"SKIP (exists): {src.name}")
        return False
    target_file.write_text(content)
    print(f"OK: {src.name} -> {target_module}/{target_subpkg}")
    return True

if __name__ == "__main__":
    ok = skip = fail = 0
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3:
            if migrate(parts[0], parts[1], parts[2]):
                ok += 1
            else:
                skip += 1
        else:
            print(f"BAD: {line}")
            fail += 1
    print(f"\nDone: {ok} migrated, {skip} skipped, {fail} errors")
