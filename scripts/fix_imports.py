#!/usr/bin/env python3
"""Fix cross-subpackage imports in migrated cognition-api files.

Types that were in the flat social package now need explicit subpackage imports.
This script scans all cognition-api Java files, finds imports pointing to the
root cognition package, and redirects them to the correct subpackage based on
where the type actually lives.
"""
import re
from pathlib import Path

BASE = Path("/Users/mdproctor/claude/casehub/slots/203/neocortex/cognition-api/src/main/java/io/casehub/neocortex/cognition")
COGNITION_BASE = Path("/Users/mdproctor/claude/casehub/slots/203/neocortex/cognition/src/main/java/io/casehub/neocortex/cognition")

def build_type_index():
    index = {}
    for base in [BASE, COGNITION_BASE]:
        if not base.exists():
            continue
        for java_file in base.rglob("*.java"):
            rel = java_file.relative_to(base)
            parts = list(rel.parts)
            class_name = parts[-1].replace(".java", "")
            if len(parts) > 1:
                subpkg = ".".join(parts[:-1])
            else:
                subpkg = ""
            index[class_name] = subpkg
    return index

def fix_file(java_file, type_index, base_pkg="io.casehub.neocortex.cognition"):
    content = java_file.read_text()
    original = content

    rel = java_file.relative_to(BASE) if str(java_file).startswith(str(BASE)) else java_file.relative_to(COGNITION_BASE)
    parts = list(rel.parts)
    if len(parts) > 1:
        file_subpkg = ".".join(parts[:-1])
    else:
        file_subpkg = ""

    lines = content.split("\n")
    new_lines = []
    added_imports = set()

    for line in lines:
        m = re.match(r'^import\s+io\.casehub\.neocortex\.cognition\.(\w+);$', line)
        if m:
            type_name = m.group(1)
            if type_name in type_index:
                target_subpkg = type_index[type_name]
                if target_subpkg and target_subpkg != file_subpkg:
                    new_import = f"import {base_pkg}.{target_subpkg}.{type_name};"
                    if new_import not in added_imports:
                        new_lines.append(new_import)
                        added_imports.add(new_import)
                    continue
                elif target_subpkg == file_subpkg:
                    continue
            new_lines.append(line)
        else:
            new_lines.append(line)

    content = "\n".join(new_lines)

    unresolved = []
    for m in re.finditer(r'import\s+io\.casehub\.neocortex\.cognition\.(\w+);', content):
        type_name = m.group(1)
        if type_name not in type_index:
            unresolved.append(type_name)

    if content != original:
        java_file.write_text(content)
        return True, unresolved
    return False, unresolved

if __name__ == "__main__":
    type_index = build_type_index()
    print(f"Type index: {len(type_index)} types mapped")
    for name, subpkg in sorted(type_index.items()):
        if subpkg:
            print(f"  {name} -> {subpkg}")

    fixed = 0
    all_unresolved = {}
    for base in [BASE, COGNITION_BASE]:
        if not base.exists():
            continue
        for java_file in base.rglob("*.java"):
            changed, unresolved = fix_file(java_file, type_index)
            if changed:
                fixed += 1
                print(f"Fixed: {java_file.name}")
            if unresolved:
                all_unresolved[java_file.name] = unresolved

    print(f"\nFixed {fixed} files")
    if all_unresolved:
        print(f"Unresolved imports in {len(all_unresolved)} files:")
        for fname, types in all_unresolved.items():
            print(f"  {fname}: {', '.join(types)}")
