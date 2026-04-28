#  MIT License
#  #
#  Copyright (c) 2026 Heiko Sippel
#  #
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#  #
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#  #
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.

import os
import re
import tempfile
from typing import TYPE_CHECKING

import pypublib

# Delay heavy imports to runtime so tests that only import this module
# won't fail if optional dependencies (like lxml) are missing.
if TYPE_CHECKING:
    from pypublib.book import Book
    from pypublib.chapter import Chapter

# ---------------------------------------- Logger ------------------------------------------------

LOGGER = pypublib.get_logger(__name__)


# -------------------------- Editing Utilities --------------------

def edit_chapter(chapter: "Chapter", replacements) -> None:
    """
    Replace all occurrences in chapter content according to replacements.

    Args:
        chapter (Chapter): The chapter to edit.
        replacements (list): List of strings in format 'old=new'.

    Example:
        >>> edit_chapter(chapter, ["Hello=Hi", "world=Earth"])
    """
    content = chapter.content
    for item in replacements:
        if '=' in item:
            old, new = item.split('=', 1)
            content = content.replace(old, new)
    chapter.content = content


def edit_chapters(chapter: list["Chapter"], replacements) -> None:
    """
    Apply replacements to a list of chapters.

    Args:
        chapter (list[Chapter]): List of Chapter instances to edit.
        replacements (list): List of strings in format 'old=new'.

    See Also:
        :func:`edit_chapter` for single chapter editing.
    """
    for chap in chapter:
        edit_chapter(chap, replacements)


def edit_all_chapters(book: "Book", replacements: list) -> None:
    """
    Edit all chapters of a book with the given replacements.

    Applies string replacements to the content of all chapters in the book.

    Args:
        book (Book): Book object with 'chapters' attribute (dictionary of Chapter objects).
        replacements (list): List of strings in format 'old=new'.

    Example:
        >>> edit_all_chapters(book, ["Chapter=Section", "Old=New"])
    """
    edit_chapters(book.chapters.values(), replacements)


def edit_chapter_tag(chapter, tag, element, old_value, value) -> None:
    """
    Replace all occurrences of a value in a specific tag's element/attribute.

    Finds all instances of a tag and replaces text or attribute values.

    Args:
        chapter (Chapter): The chapter to edit.
        tag (str): Tag name to find (e.g., 'img', 'a', 'p').
        element (str): Attribute or element name (e.g., 'src', 'href', or 'text').
        old_value (str): Value to be replaced.
        value (str): New value.

    Example:
        >>> edit_chapter_tag(chapter, 'img', 'src', 'old.jpg', 'new.jpg')
    """
    # Import lxml and chapter namespace lazily to avoid hard dependency at import-time
    from lxml import etree  # type: ignore
    from pypublib.chapter import NS  # local import to prevent circular imports at module import

    doc = etree.fromstring(chapter.html.encode("utf-8"))
    for el in doc.findall(f".//x:{tag}", namespaces=NS):
        if element == "text":
            if el.text and old_value in el.text:
                el.text = el.text.replace(old_value, value)
        else:
            attr = el.get(element)
            if attr and old_value in attr:
                el.set(element, attr.replace(old_value, value))

    chapter.html = etree.tostring(doc, encoding="unicode", method="html")


def edit_chapter_tags(chapter, replacements):
    """
    Replace values in specific tags in chapter content using regex patterns.

    Args:
        chapter (Chapter): Chapter object with 'html' attribute.
        replacements (list): List of strings in format 'tag=old=new'.

    Returns:
        Chapter: The modified chapter.

    Example:
        >>> edit_chapter_tags(chapter, ['p=old text=new text', 'strong=bad=good'])
    """
    content = chapter.html
    for item in replacements:
        if '=' in item:
            parts = item.split('=', 2)
            if len(parts) == 3:
                tag, old, new = parts
                # Only replace value inside the tag
                pattern = rf'(<{tag}[^>]*>)(.*?)(</{tag}>)'
                content = re.sub(pattern, lambda m: m.group(1) + m.group(2).replace(old, new) + m.group(3), content,
                                 flags=re.DOTALL)
    chapter.html = content
    return chapter


# -------------------------------- Removal of unnecessary files ---------------------


def _resource_candidates(path: str) -> set[str]:
    """Build comparable key variants for resource path matching."""
    if not path:
        return set()

    cleaned = path.strip().replace("\\", "/")
    cleaned = cleaned.split("#", 1)[0].split("?", 1)[0]
    cleaned = cleaned.lstrip("./")

    if not cleaned:
        return set()

    parts = []
    for part in cleaned.split("/"):
        if not part or part == ".":
            continue
        if part == ".." and parts and parts[-1] != "..":
            parts.pop()
            continue
        parts.append(part)

    normalized = "/".join(parts)
    if normalized in {".", ""}:
        return set()

    candidates = {normalized, normalized.lstrip("/")}
    basename = normalized.split("/")[-1]
    if basename:
        candidates.add(basename)

    while normalized.startswith("../"):
        normalized = normalized[3:]
        if normalized:
            candidates.add(normalized)

    return {candidate for candidate in candidates if candidate}


def remove_unnecessary_files(book: "Book") -> "Book":
    """Remove unreferenced image and CSS files from the book.

    Keeps resources that are referenced by at least one chapter via stylesheet
    links or image tags. The cover image is always preserved if set.

    Args:
        book (Book): Book instance containing chapters, styles and images.

    Returns:
        Book: The same book instance with unreferenced assets removed.
    """
    used_styles = set()
    used_images = set()

    for chapter in book.chapters.values():
        for style in chapter.styles:
            used_styles.update(_resource_candidates(style))
        for image in chapter.images:
            used_images.update(_resource_candidates(image))

    if book.cover:
        used_images.update(_resource_candidates(book.cover))

    book.styles = {
        name: sheet
        for name, sheet in book.styles.items()
        if _resource_candidates(name) & used_styles
    }
    book.images = {
        name: image
        for name, image in book.images.items()
        if _resource_candidates(name) & used_images
    }

    return book


# ---------------------------------- CSS Cleaning Utilities -----------------


def collect_used_selectors(content_dir):
    """
    Collect all used CSS class and id selectors from XHTML/HTML files.

    Scans all HTML/XHTML files in a directory tree and extracts all
    class and id selectors that are actually used in the markup.

    Args:
        content_dir (str): Path to the directory containing content files.

    Returns:
        set: Set of used CSS selectors (e.g., {'.classname', '#idname'}).
    """
    used_selectors = set()
    xhtml_pattern = re.compile(r'class="([^"]+)"|id="([^"]+)"')
    for root, _, files in os.walk(content_dir):
        for file in files:
            if file.endswith('.xhtml') or file.endswith('.html'):
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    content = f.read()
                    for match in xhtml_pattern.findall(content):
                        if match[0]:
                            used_selectors.update(['.' + cls for cls in match[0].split()])
                        if match[1]:
                            used_selectors.add('#' + match[1])
    return used_selectors


def process_css_file(css_path, used_selectors):
    """
    Remove unused CSS selectors from a CSS file.

    Reads a CSS file, identifies rules with selectors not in the used set,
    and removes them, writing the cleaned CSS back to the file.

    Args:
        css_path (str): Path to the CSS file to process.
        used_selectors (set): Set of CSS selectors that are actually used.

    Returns:
        list: List of removed selectors.
    """
    css_rule_pattern = re.compile(r'([^{]+)\{[^}]*}', re.MULTILINE)
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()
    new_css = ''
    removed_selectors = []
    for rule in css_rule_pattern.finditer(css_content):
        selectors = [selector.strip() for selector in rule.group(1).split(',')]
        if any(selector in used_selectors for selector in selectors):
            new_css += rule.group(0) + '\n'
        else:
            removed_selectors.extend(selectors)
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(new_css)
    print(f"Removed selectors from {css_path}: {removed_selectors}")
    return removed_selectors


def clean_unused_styles(content_dir):
    """
    Clean all unused CSS selectors from CSS files in the content directory.

    Recursively processes all CSS files in a directory, identifying and
    removing selectors that are not used in any HTML/XHTML file.

    Args:
        content_dir (str): Path to the directory containing content files.
    """
    used_selectors = collect_used_selectors(content_dir)
    css_files = []
    for root, _, files in os.walk(content_dir):
        for file in files:
            if file.endswith('.css'):
                css_files.append(os.path.join(root, file))
    # Call through to epub.process_css_file so tests can patch the function
    import pypublib.epub as _epub
    for css in css_files:
        process_css_file(css, used_selectors)


def remove_unused_styles(book: "Book") -> "Book":
    """
    Remove unused CSS selectors from the book's styles.

    Analyzes which CSS selectors are actually used in the book's chapters
    and removes all unused selectors from the stylesheets. This reduces
    file size and improves EPUB efficiency.

    Args:
        book (Book): Book object with 'styles' attribute (dictionary of CSS content).

    Returns:
        Book: The book with cleaned stylesheets.

    Note:
        This function creates temporary files during processing. Any style
        files that become empty after cleaning are removed from the book.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Save styles to temporary files
        for name, sheet in book.styles.items():
            style_path = os.path.join(temp_dir, name)
            with open(style_path, "w", encoding="utf-8") as f:
                f.write(sheet)

        # Clean unused styles via epub wrapper so tests can patch it
        import pypublib.epub as _epub
        clean_unused_styles(temp_dir)

        # Load cleaned styles back into the book
        for name in list(book.styles.keys()):
            style_path = os.path.join(temp_dir, name)
            if os.path.isfile(style_path):
                with open(style_path, "r", encoding="utf-8") as f:
                    book.styles[name] = f.read()
            else:
                del book.styles[name]  # Style was removed

    finally:
        # Clean up temporary directory
        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(temp_dir)
    return book
