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

import os

import tempfile
import zipfile
from pathlib import Path
from typing import Dict

import logging
from pypublib.book import Book
from pypublib.book import Opf
from pypublib.chapter import Chapter

# ---------------------------------------- Logger ------------------------------------------------

LOGGER = logging.getLogger(__name__)

# ------------------------------------- Templates -----------------------

# XML template for EPUB container file
TEMPLATE_CONTAINER = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''


# ------------------------------ EPUB Reading and Creation -----------------

def read_book(file_path: str) -> Book | None:
    """
    Read an EPUB file and return a Book instance.

    Validates the file path and EPUB structure before parsing. Returns None if
    the file cannot be read or parsed.

    Args:
        file_path (str): Path to the EPUB file to read.

    Returns:
        Book | None: A Book instance if successful, None if an error occurs.

    Raises:
        Catches and logs the following exceptions:
            - FileNotFoundError: File does not exist
            - zipfile.BadZipFile: Invalid EPUB container
            - UnicodeDecodeError: Encoding errors in EPUB content
            - KeyError: Missing required EPUB data
            - PermissionError: File permission issues

    Example:
        >>> book = read_book("my_book.epub")
        >>> if book:
        ...     print(f"Loaded: {book.title}")
    """
    try:
        # Check for valid file path
        if not isinstance(file_path, str) or not file_path.strip():
            LOGGER.error("[read_book] Invalid file path.")
            return None
        if not os.path.isfile(file_path):
            LOGGER.error(f"[read_book] File not found: {file_path}")
            return None
        if not zipfile.is_zipfile(file_path):
            LOGGER.error(f"[read_book] Not a valid ZIP/EPUB file: {file_path}")
            return None

        contents = extract_epub_content(file_path)
        book = create_book(contents)
        LOGGER.info(f"EPUB parsed successfully: {book}")
        return book

    except zipfile.BadZipFile as e:
        LOGGER.error(f"[read_book] Invalid EPUB container: {e}")
    except UnicodeDecodeError as e:
        LOGGER.error(f"[read_book] Encoding error while reading EPUB: {e}")
    except KeyError as e:
        LOGGER.error(f"[read_book] Missing required data in EPUB: {e}")
    except PermissionError as e:
        LOGGER.error(f"[read_book] Permission denied: {e}")
    except Exception as e:
        LOGGER.error(f"[read_book] Unexpected error: {e}")

    return None


def create_book(contents):
    """
    Create a Book object from extracted EPUB contents.

    Populates a new Book instance with metadata, chapters, and resources
    from the extracted EPUB content dictionary.

    Args:
        contents (dict): Dictionary containing extracted EPUB data with keys:
            'metadata', 'chapters', 'styles', 'images', 'fonts', 'spine', 'guide', 'cover'.

    Returns:
        Book: A new Book instance populated with the extracted content.
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
    Extract all relevant content from an EPUB file.

    Reads all chapters, stylesheets, images, fonts, and metadata from the EPUB archive.
    Parses the OPF file to extract manifest, spine, and guide information.

    Args:
        file_path (str): Path to the EPUB file.

    Returns:
        dict: Dictionary containing:
            - 'metadata': Parsed metadata from OPF
            - 'chapters': Dict mapping hrefs to XHTML content
            - 'styles': Dict mapping filenames to CSS content
            - 'images': Dict mapping filenames to binary image data
            - 'fonts': Dict mapping filenames to binary font data
            - 'manifest': List of manifest items
            - 'spine': Reading order list
            - 'guide': Guide references
            - 'cover': Cover image filename or None
    """
    chapters, styles, images, fonts, metadata = {}, {}, {}, {}, {}
    manifest: Dict[str, Dict[str, str]] = {}
    spine = []
    cover, guide = None, []

    with zipfile.ZipFile(file_path, 'r') as epub:
        # Find OPF file path
        opf_path = next((name for name in epub.namelist() if name.endswith('content.opf')), None)

        # Parse OPF file if present
        if opf_path:
            xml_str = epub.read(opf_path).decode('utf-8').encode("utf-8")
            opf = Opf(xml_str)
            manifest = opf.manifest
            spine = opf.spine
            metadata = opf.metadata
            cover = opf.cover
            guide = opf.guide
        else:
            LOGGER.error("No OPF entry found in ebook!")
            raise ValueError()

        # Read chapters as listed in the spine, cross-referenced with the manifest, to keep sorting order
        for item in spine:
            href = manifest[item]['href']
            if href.endswith('.xhtml') or href.endswith('.html'):
                chapters[href] = epub.read(href).decode('utf-8')

        for _, item in manifest.items():
            href, media_type = item['href'], item['media-type']
            if 'css' in media_type:  # Read stylesheets
                styles[item['href']] = epub.read(href).decode('utf-8')

            if 'image' in media_type:  # Read images
                images[item['href']] = epub.read(href)

            if 'font' in media_type:  # Read fonts
                fonts[href] = epub.read(href)

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


# ----------------------------------- EPUB Writing -----------------------

def publish_book(book: Book, file_path):
    """
    Save the book in EPUB format to the specified file path.

    Convenience wrapper around save_book function.

    Args:
        book (Book): The Book instance to publish.
        file_path (str): Output file path for the EPUB file.

    See Also:
        :func:`save_book` for the actual implementation.
    """
    save_book(book, file_path)


def save_book(book: Book, file_path):
    """
    Write the Book object to an EPUB file.

    Creates a complete EPUB archive with all book components including chapters,
    navigation files, styles, images, fonts, and OPF metadata. The EPUB file
    is properly structured according to EPUB3 standards.

    The process:
        1. Creates temporary directory structure
        2. Writes mimetype file (uncompressed)
        3. Creates META-INF/container.xml
        4. Saves all chapters as XHTML files
        5. Generates and saves navigation files (nav.xhtml and toc.ncx)
        6. Saves stylesheets, images, and fonts
        7. Generates and saves content.opf
        8. Archives everything as a ZIP file

    Args:
        book (Book): The Book instance to save.
        file_path (str): Output file path for the EPUB file.

    Note:
        The mimetype file is stored uncompressed as per EPUB specification.
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
            chapter_path = Path(os.path.join(oebps_dir, chapter.href).replace("?", ""))
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            with open(chapter_path, "w", encoding="utf-8") as f:
                f.write(chapter.html)

        # Save navigation file
        nav = book.nav
        nav_path = os.path.join(oebps_dir, "nav.xhtml")
        with open(nav_path, "w", encoding="utf-8") as f:
            f.write(nav)

        # Save styles
        for name, sheet in book.styles.items():
            style_path = Path(os.path.join(oebps_dir, name))
            style_path.parent.mkdir(parents=True, exist_ok=True)
            with open(style_path, "w", encoding="utf-8") as f:
                f.write(sheet)

        # Save images
        for name, image in book.images.items():
            image_path = Path(os.path.join(oebps_dir, name))
            image_path.parent.mkdir(parents=True, exist_ok=True)
            with open(image_path, "wb") as f:
                f.write(image)

        # Save fonts
        for name, font in book.fonts.items():
            font_path = Path(os.path.join(oebps_dir, name))
            font_path.parent.mkdir(parents=True, exist_ok=True)
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

    LOGGER.info(f"Book has been saved as {file_path}")


# ------------------------------- Validation -----------------------


def validate_metadata(book):
    """
      Validate that a book has required and optional metadata fields.

      Checks for mandatory fields (title, creator) and optional fields
      (language, subject).

      Args:
          book (Book): The Book instance to validate.

      Returns:
          tuple: A tuple of (missing_mandatory, missing_optional) where each is
              a list of field names.

      Example:
          >>> mandatory, optional = validate_metadata(book)
          >>> if mandatory:
          ...     print(f'Missing mandatory fields: {mandatory}')
      """
    mandatory_metadata = ["title", "creator"]
    optional_metadata = ["language", "subject"]
    missing_mandatory = [field for field in mandatory_metadata if not field in book.metadata]
    missing_optional = [field for field in optional_metadata if not field in book.metadata]
    return missing_mandatory, missing_optional


def validate_chapters(book: Book) -> None:
    """
    Validate that all chapters have required title and content.

    Args:
        book (Book): The Book instance to validate.

    Raises:
        ValueError: If any chapter is missing a title or HTML content.
    """
    for chapter in book.chapters:
        if not chapter.title or not chapter.html:
            raise ValueError(f"Invalid chapter: {chapter}")


def validate_book(book: Book) -> list:
    """
    Validate the book structure and resources.

    Performs comprehensive validation including:
        - Checks for empty books
        - Detects duplicate chapter hrefs
        - Validates chapter titles and hrefs
        - Validates metadata completeness
        - Checks resource references

    Args:
        book (Book): The Book instance to validate.

    Returns:
        list: List of issue strings found. Empty list if book is valid.

    Example:
        >>> book_issues = validate_book(book)
        >>> if issues:
        ...     for issue in book_issues:
        ...         print(f'Warning: {issue}')
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
    metadata_issues, _ = validate_metadata(book)
    if metadata_issues:
        issues.append(f'Book is missing required metadata fields: {", ".join(metadata_issues)}.')

    # Validate resources
    resource_issues = validate_book_resources(book)
    issues.extend(resource_issues)

    return issues


def validate_book_resources(book):
    """
    Validate that all resources referenced in chapters are available in the book.

    Checks for missing images and stylesheets referenced by chapters.

    Args:
        book (Book): The Book instance to validate.

    Returns:
        list: List of dictionaries, each containing:
            - 'chapter': Chapter title
            - 'missing_images': List of missing image filenames
            - 'missing_styles': List of missing stylesheet filenames
    """
    missing = []
    book_images = set(book.images.keys())
    book_styles = set(book.styles.keys())

    for chapter in book.chapters.values():
        chapter_images = set(chapter.images)
        chapter_styles = set(chapter.styles)

        missing_images = chapter_images - book_images
        missing_styles = chapter_styles - book_styles

        if missing_images or missing_styles:
            missing.append({"chapter": chapter.title, "missing_images": list(missing_images),
                            "missing_styles": list(missing_styles)})

    return missing


def pretty_print_xml(xml):
    """
    Formats an XML string into a nice format.
    At the moment unimplemented.

    Args:
        xml (str): XML string to format.

    Returns:
        str: Formatted XML string.
    """
    return xml
