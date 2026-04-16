#!/usr/bin/env python3
"""
Copy and convert README.md from project root into docs/ for Sphinx.

Features:
- Copy root README.md to docs/README.md
- Copy all images from any */images/* directories into docs/images/
- Find image references in README.md and copy referenced local images into docs/images/
- Update image links in the copied README to point to images/<basename_or_renamed>
- Handle name collisions by appending a numeric suffix

Usage:
    python scripts/generate_docs_readme.py --src README.md --dest docs/README.md

This script is cross-platform and intended to be used both locally and in CI.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from typing import Dict


IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg"}


def find_images_in_repo(root: Path) -> list[Path]:
    """Find all files under any 'images' directory in the repository."""
    imgs = []
    # use a recursive glob that finds any images/ directory at any depth
    for p in root.rglob("**/images/*"):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            imgs.append(p)
    return imgs


def extract_image_paths_from_md(text: str) -> list[str]:
    # Markdown image syntax: ![alt](path "title")
    # capture the path part inside the first token of the parentheses (stops at whitespace or closing paren)
    pattern = re.compile(r"!\[[^\]]*\]\(\s*([^\s)]+)")
    paths = []
    for m in pattern.finditer(text):
        path = m.group(1).strip()
        # remove optional title after space: path "title"
        if " \"" in path or " '" in path:
            # naive split on first space if it's followed by quote
            path = re.split(r"\s+(['\"])", path)[0]
        paths.append(path)
    return paths


def is_remote(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://") or path.startswith("data:") or path.startswith("mailto:")


def copy_with_collision_handling(src: Path, dst_dir: Path, seen: Dict[str, int]) -> str:
    """Copy src into dst_dir. If basename collides, append -1,-2 etc. Return final basename."""
    base = src.name
    name = base
    stem = src.stem
    suffix = src.suffix
    i = seen.get(base, 0)
    target = dst_dir / name
    while target.exists():
        i += 1
        name = f"{stem}-{i}{suffix}"
        target = dst_dir / name
    # ensure parent exists
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    seen[base] = i
    return name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default="README.md", help="source README (relative to repo root)")
    parser.add_argument("--dest", default="docs/README.md", help="destination in docs/")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    src_path = (repo_root / args.src).resolve()
    dest_path = (repo_root / args.dest).resolve()
    docs_dir = dest_path.parent
    images_dir = docs_dir / "images"

    if not src_path.exists():
        print(f"Source README not found: {src_path}")
        return 2

    docs_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    # copy images from any images folders in repo
    seen: Dict[str, int] = {}
    repo_images = find_images_in_repo(repo_root)
    for img in repo_images:
        copy_with_collision_handling(img, images_dir, seen)

    # read README and extract image references
    text = src_path.read_text(encoding="utf-8")
    img_paths = extract_image_paths_from_md(text)

    replaced = text
    for img_ref in img_paths:
        img_clean = img_ref.split("#")[0].split("?")[0]
        if is_remote(img_clean):
            # skip remote
            continue
        # resolve relative to repo root
        candidate = (repo_root / img_clean).resolve()
        if not candidate.exists():
            # try resolving relative to README location
            candidate = (src_path.parent / img_clean).resolve()
        if candidate.exists() and candidate.suffix.lower() in IMG_EXTS:
            new_name = copy_with_collision_handling(candidate, images_dir, seen)
            # replace occurrences of the original path in the README content.
            # Use regex-based replacement to handle variations (./prefix, quoted title, etc.)
            # Replace raw occurrences of img_ref and img_clean with images/<new_name>
            replaced = re.sub(re.escape(img_ref), f"images/{new_name}", replaced)
            replaced = re.sub(re.escape(img_clean), f"images/{new_name}", replaced)
            # also handle occurrences that start with ./
            replaced = re.sub(re.escape(f"./{img_clean}"), f"images/{new_name}", replaced)
        else:
            print(f"Warning: referenced image not found or unsupported: {img_ref}")

    # write converted README
    dest_path.write_text(replaced, encoding="utf-8")
    print(f"Wrote converted README to {dest_path}")
    print(f"Copied images into {images_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

