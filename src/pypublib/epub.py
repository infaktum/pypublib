# MIT License
#
# Copyright (c) 2025 Heiko Sippel
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re
import os

import zipfile
import tempfile
from lxml import etree
from pypublib.book import Book, Chapter, Opf, NS

#------------------------------------- Templates -----------------------

# XML template for EPUB container file
TEMPLATE_CONTAINER = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''

#------------------------------ EPUB Reading and Creation -----------------

def read_book(file_path: str) -> Book | None:
    """
    Reads an EPUB file and returns a Book instance.
    """
    try:
        # Check for valid file path
        if not isinstance(file_path, str) or not file_path.strip():
            print("[read_book] Invalid file path.")
            return None
        if not os.path.isfile(file_path):
            print(f"[read_book] File not found: {file_path}")
            return None
        if not zipfile.is_zipfile(file_path):
            print(f"[read_book] Not a valid ZIP/EPUB file: {file_path}")
            return None

        contents = extract_epub_content(file_path)
        book = create_book(contents)
        print(f"EPUB parsed successfully: {book}")
        return book

    except zipfile.BadZipFile as e:
        print(f"[read_book] Invalid EPUB container: {e}")
    except UnicodeDecodeError as e:
        print(f"[read_book] Encoding error while reading EPUB: {e}")
    except KeyError as e:
        print(f"[read_book] Missing required data in EPUB: {e}")
    except PermissionError as e:
        print(f"[read_book] Permission denied: {e}")
    except Exception as e:
        print(f"[read_book] Unexpected error: {e}")

    return None

def create_book(contents):
    """
    Creates a Book object from extracted EPUB contents.
    """
    book = Book(contents["metadata"])
    for href, chapter in contents['chapters'].items():
        os.path.basename(href)
        chapter = Chapter.from_xhtml(href, chapter)
        book.chapters[chapter.href] = chapter

    book.styles = contents['styles']
    book.images = contents['images']
    book.fonts = contents['fonts']
    book.metadata = contents['metadata']
    book.spine = contents['spine']
    book.guide = contents['guide']
    if contents['cover']:
        book.cover = contents['cover']

    return book

def extract_epub_content(file_path):
    """
    Extracts all relevant content from an EPUB file.
    """
    chapters, styles, images, fonts = {}, {}, {}, {}
    manifest, spine, metadata = [], [], {}
    cover, guide = None, []

    with zipfile.ZipFile(file_path, 'r') as epub:
        # Find OPF file path
        opf_path = next((name for name in epub.namelist() if name.endswith('content.opf')), None)
        for name in epub.namelist():
            href = os.path.basename(name)
            # Read chapters
            if href.endswith('.xhtml') or href.endswith('.html'):
                chapters[href] = epub.read(name).decode('utf-8')
            # Read stylesheets
            elif href.endswith('.css'):
                styles[href] = epub.read(name).decode('utf-8')
            # Read images
            elif href.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.svg')):
                images[href] = epub.read(name)
            # Read fonts
            elif href.lower().endswith(('.ttf', '.otf', '.woff', '.woff2')):
                fonts[href] = epub.read(name)
        # Parse OPF file if present
        if opf_path:
            xml_str = epub.read(opf_path).decode('utf-8').encode("utf-8")
            opf = Opf(xml_str)
            manifest = opf.manifest
            spine = opf.spine
            metadata = opf.metadata
            cover = opf.cover
            guide = opf.guide

    return {
        'metadata': metadata,
        'chapters': chapters,
        'styles': styles,
        'images': images,
        'fonts': fonts,
        'manifest': manifest,
        'spine': spine,
        'guide': guide,
        'cover': cover
    }

#----------------------------------- EPUB Writing -----------------------

def publish_book(book: Book, file_path):
    """
    Saves the book in EPUB format to the specified file.
    """
    save_book(book, file_path)

def save_book(book: Book, file_path):
    """
    Writes the Book object to an EPUB file.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write mimetype file (must be first and uncompressed)
        mimetype_path = os.path.join(tmpdir, "mimetype")
        with open(mimetype_path, "w", encoding="utf-8") as f:
            f.write("application/epub+zip")

        # Write META-INF/container.xml
        meta_inf_dir = os.path.join(tmpdir, "META-INF")
        os.makedirs(meta_inf_dir, exist_ok=True)
        with open(os.path.join(meta_inf_dir, "container.xml"), "w", encoding="utf-8") as f:
            f.write(TEMPLATE_CONTAINER)

        # Create OEBPS directory for content
        oebps_dir = os.path.join(tmpdir, "OEBPS")
        os.makedirs(oebps_dir, exist_ok=True)

        # Save chapters
        for href, chapter in book.chapters.items():
            chapter_path = os.path.join(oebps_dir, chapter.href).replace("?", "")
            with open(chapter_path, "w", encoding="utf-8") as f:
                f.write(chapter.html)

        # Save navigation file
        nav = book.nav
        nav_path = os.path.join(oebps_dir, "nav.xhtml")
        with open(nav_path, "w", encoding="utf-8") as f:
            f.write(nav)

        # Save styles
        for name, sheet in book.styles.items():
            style_path = os.path.join(oebps_dir, name)
            with open(style_path, "w", encoding="utf-8") as f:
                f.write(sheet)

        # Save images
        for name, image in book.images.items():
            image_path = os.path.join(oebps_dir, name)
            with open(image_path, "wb") as f:
                f.write(image)

        # Save fonts
        for name, font in book.fonts.items():
            font_path = os.path.join(oebps_dir, name)
            with open(font_path, "wb") as f:
                f.write(font)

        # Write OPF file
        with open(os.path.join(oebps_dir, "content.opf"), "w", encoding="utf-8") as f:
            f.write(pretty_print_xml(book.opf))

        # Write NCX file (optional, for TOC)
        with open(os.path.join(oebps_dir, "toc.ncx"), "w", encoding="utf-8") as f:
            f.write(book.toc)

        # Archive files as EPUB (ZIP)
        with zipfile.ZipFile(file_path, "w") as epub:
            epub.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, tmpdir)
                    if rel_path != "mimetype":
                        epub.write(full_path, rel_path, compress_type=zipfile.ZIP_DEFLATED)

    print(f"Book has been saved as {file_path}")

#------------------------------- Validation -----------------------


def validate_metadata(book):
    mandatory_metadata = ["title", "creator"]
    optional_metadata = ["language", "subject"]
    missing_mandatory = [field for field in mandatory_metadata if not field in book.metadata]
    missing_optional = [field for field in optional_metadata if not field in book.metadata]
    return missing_mandatory, missing_optional


def validate_toc(book):
    if not book.toc:
        raise ValueError("Table of content (TOC) is empty.")
    for entry in book.toc:
        if not any(chapter.src == entry.src for chapter in book.chapters):
            raise ValueError(f"Toc entry references invalid chapter: {entry.src}")

def validate_chapters(book):
    for chapter in book.chapters:
        if not chapter.title or not chapter.html:
            raise ValueError(f"Invalid chapter: {chapter}")


def validate_book(book: Book) -> list:
    """
    Validates the book structure and resources.
    Returns a list of issues found.
    """
    issues = []

    # Check for empty book
    if not book.chapters:
        issues.append("The book contains no chapters.")

    # Check for duplicate hrefs
    hrefs = [chapter.href for chapter in book.chapters.values()]
    duplicates = set([href for href in hrefs if hrefs.count(href) > 1])
    for dup in duplicates:
        issues.append(f"Duplicate chapter href found: '{dup}'.")

    # Check for chapters without titles or hrefs
    for chapter in book.chapters.values():
        if not chapter.title:
            issues.append(f"Chapter with href '{chapter.href}' is missing a title.")
        if not chapter.href:
            issues.append(f"Chapter titled '{chapter.title}' is missing an href.")

    # Validate metadata
    metadata_issues,_ = validate_metadata(book)
    if metadata_issues:
        issues.append(f'Book is missing required metadata fields: {", ".join(metadata_issues)}.')

    # Validate resources
    resource_issues = validate_book_resources(book)
    issues.extend(resource_issues)

    return issues


def validate_book_resources(book):
    missing = []
    book_images = set(book.images.keys())
    book_styles = set(book.styles.keys())

    for chapter in book.chapters.values():
        chapter_images = set(chapter.images)
        chapter_styles = set(chapter.styles)

        missing_images = chapter_images - book_images
        missing_styles = chapter_styles - book_styles

        if missing_images or missing_styles:
            missing.append({"chapter": chapter.title,"missing_images": list(missing_images),"missing_styles": list(missing_styles) })

    return missing

#-------------------------- Editing Utilities --------------------

def edit_chapter(chapter: Chapter, replacements) -> None:
    """
    Replaces all occurrences in chapter content according to replacements.
    """
    content = chapter.content
    for item in replacements:
        if '=' in item:
            old, new = item.split('=', 1)
            content = content.replace(old, new)
    chapter.content = content

def edit_chapters(chapter: list[Chapter], replacements) -> None:
    """
    Applies replacements to a list of chapters.
    """
    for chap in chapter:
        edit_chapter(chap, replacements)

def edit_all_chapters(book: Book, replacements: list) -> None:
    """
    Edits all chapters of a book with the given replacements.
    :param book: Book object with 'chapters' attribute (dictionary of Chapter objects)
    :param replacements: List of strings in format 'old=new'
    """
    edit_chapters(book.chapters.values(), replacements)

def edit_chapter_tag(chapter, tag, element, old_value, value) -> None:
    """
    Replaces all occurrences of old_value in the specified element/attribute of found tags with value.
    :param tag: Tag name (e.g. 'img')
    :param element: Attribute or element name (e.g. 'src' or 'text')
    :param old_value: Value to be replaced
    :param value: New value
    """
    doc = etree.fromstring(chapter.html.encode("utf-8"))
    for el in doc.findall(f".//x:{tag}", namespaces=NS):
        if element == "text":
            if el.text and old_value in el.text:
                el.text = el.text.replace(old_value, value)
        else:
            attr = el.get(element)
            if attr and old_value in attr:
                el.set(element, attr.replace(old_value, value))
    chapter.html = Chapter.serialize(doc)

def edit_chapter_tags(chapter, replacements):
    """
    Replaces values in specific tags in chapter content.
    :param chapter: Chapter object with 'html' attribute
    :param replacements: List of strings in format 'tag=old=new'
    """
    content = chapter.html
    for item in replacements:
        if '=' in item:
            parts = item.split('=', 2)
            if len(parts) == 3:
                tag, old, new = parts
                # Only replace value inside the tag
                pattern = rf'(<{tag}[^>]*>)(.*?)(</{tag}>)'
                content = re.sub(pattern, lambda m: m.group(1) + m.group(2).replace(old, new) + m.group(3), content, flags=re.DOTALL)
    chapter.html = content
    return chapter

#---------------------------------- CSS Cleaning Utilities -----------------


def collect_used_selectors(content_dir):
    """
    Collects all used CSS class and id selectors from XHTML/HTML files.
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
    Removes unused CSS selectors from a CSS file.
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
    Cleans all unused CSS selectors from CSS files in the content directory.
    """
    used_selectors = collect_used_selectors(content_dir)
    css_files = []
    for root, _, files in os.walk(content_dir):
        for file in files:
            if file.endswith('.css'):
                css_files.append(os.path.join(root, file))
    for css in css_files:
        process_css_file(css, used_selectors)


def remove_unused_styles(book: Book) -> Book:
    """
    Removes unused CSS selectors from the book's styles.
    :param book: Book object with 'styles' attribute (dictionary of CSS content)
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Save styles to temporary files
        for name, sheet in book.styles.items():
            style_path = os.path.join(temp_dir, name)
            with open(style_path, "w", encoding="utf-8") as f:
                f.write(sheet)

        # Clean unused styles
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
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))
        os.rmdir(temp_dir)
    return book


#----------------------------- Formatting Utilities -------------------

def pretty_print_xml(xml: str) -> str:
    """
    Creates a pretty printed xml string for the given xml string.
    """

    #parser = etree.XMLParser(remove_blank_text=True)
    #tree = etree.fromstring(xml_string.encode("utf-8"), parser)
    #return etree.tostring(tree, pretty_print=True, encoding="unicode")
    return xml
