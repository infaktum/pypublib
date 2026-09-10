# PyPubLib

## A Python library for ePub files

[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![EPUB](https://img.shields.io/badge/EPUB-supported-green.svg)](https://www.w3.org/publishing/epub32/epub-spec.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI](https://github.com/infaktum/pypublib/actions/workflows/tests.yml/badge.svg)](https://github.com/infaktum/pypublib/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/infaktum/pypublib/branch/main/graph/badge.svg)](https://codecov.io/gh/infaktum/pypublib)

This project provides tools and utilities for generating and manipulating EPUB files using Python. It includes functions
to create essential EPUB components such as `nav.xhtml`, `toc.ncx`, and the manifest, making it easier to build valid
EPUB 2 and EPUB 3 ebooks programmatically.

![PyPubLib Banner](https://raw.githubusercontent.com/infaktum/pypublib/main/docs/banner.png)

## What is EPUB?

EPUB (Electronic Publication) is a widely used open standard for e-books, maintained by the W3C. EPUB files are
essentially ZIP archives containing XHTML content, images, stylesheets, and metadata. The format supports reflowable
content, making it suitable for various screen sizes and devices.

## The structure of an EPUB file

The structure of an EPUB is rather simple: An EPUB file is a ZIP archive with a specific directory structure and
required files.

The content of a book is stored in XHTML files, with CSS styles and images stored in separate directories.

The single most important file in an EPUB is the **OPF** file (_Open Publication Format_), which describes the structure
of the book, including

* the **metadata**: tile, author, language, publisher, etc.
* the **manifest**: the list of included files
* the **spine**: defines the reading order of the book
* an optional **guide**: defines references to key parts of the book

Summarizing, an EPUB file contains:

- **OPF (Open Packaging Format):** Describes the structure and resources of the book.
- **XHTML files:** The actual content of the book.
- **Images and stylesheets:** For media and formatting.
- **nav.xhtml:** Used in EPUB 3 for navigation.
- **NCX (Navigation Center eXtended):** Used in EPUB 2 for the table of contents.

## Features of pypublib

As mentioned before the structure of an EPUB book is rather simple, and there are already some Python libs that can help
you create EPUB files. Furthermore, there are some GUI tools that can help you create EPUB files, notably

- [Sigil](https://sigil-ebook.com/): A great tool for visually organizing and editing single EPUB files
- [Calibre](https://calibre-ebook.com/): A powerful eBook management tool that can convert various formats to EPUB and
  vice versa

`pypublib` aims to provide a simple and easy-to-use interface for creating and manipulating EPUB files programmatically.
It focuses on generating the essential components of an EPUB file, such as `content.opf`, `nav.xhtml`, and `toc.ncx`,
while allowing for easy integration with existing Python projects. EPUB books can be created from scratch or imported
for modification.

Key features include:

- Create and manipulate EPUB files programmatically.
- Import existing EPUB files for modification.
- Parsing and generating `content.opf` files.
- Generate `nav.xhtml` for EPUB 3 navigation.
- Generate `toc.ncx` for EPUB 2 table of contents.
- Create and manage the manifest and spine in the OPF file.
- Support for adding metadata to the EPUB file.
- Easy integration with existing Python projects.

## Editing existing EPUBs

Books loaded with `read_book()` retain every original archive entry, including unknown resources, complete OPF metadata
and attributes, and authored navigation. Saving an unchanged book preserves each entry's contents byte for byte. The ZIP
archive itself is rewritten; its original entry order, compression methods, timestamps, and comments are retained.

### Complete workflow: open, edit a chapter, save

Use the public API; `ArchiveState` and the helpers in `_utils.py` are used automatically. No manual extraction or
rebuilding of the EPUB is necessary.

Set the input/output filenames, chapter key and replacement text for your book. The chapter listing shows the keys
available in the imported EPUB; these paths are relative to its OPF file, for example `Text/chapter1.xhtml`.

```python
from html import escape

from lxml import etree
from pypublib import read_book, publish_book

source = "original.epub"
destination = "edited.epub"
chapter_href = "Text/chapter1.xhtml"  # Choose a key from the listing below.
old_text = "old text"
new_text = "new text & more"

# 1. Open the EPUB and list the available chapters.
book = read_book(source)
if book is None:
    raise ValueError(f"Could not read EPUB: {source}")

for href, item in book.chapters.items():
    print(f"{href}: {item.title}")

# 2. Select a chapter by its exact key.
chapter = book.get_chapter(chapter_href)
if chapter is None:
    raise KeyError(f"Chapter not found: {chapter_href}")

# 3. Edit the existing object. content contains the body's XHTML fragment.
if old_text not in chapter.content:
    raise ValueError(f"Text not found in {chapter_href}: {old_text!r}")
chapter.content = chapter.content.replace(old_text, escape(new_text, quote=False))
chapter.title = "Revised chapter title"

# 4. Check that the edited chapter still produces well-formed XHTML.
etree.fromstring(
    chapter.html.encode("utf-8"),
    parser=etree.XMLParser(resolve_entities=False, no_network=True),
)

# 5. Save the modified book. No add_chapter() call is needed.
publish_book(book, destination)
print(f"Saved: {destination}")
```

`get_chapter()` returns the object stored in `book.chapters`, so changes to it are already part of the book.
`chapter.content` is the XHTML **inside the body**;
`chapter.html` represents the complete document. Escape literal replacement text containing `&` or `<`, as above. String
replacement acts on the markup itself, can also affect attributes, and does not match text split across tags. For
replacements restricted to specific elements, parse and edit the XHTML tree.

Changing `chapter.title` updates the document's `<title>` element, not a heading inside its body or an existing
table-of-contents label. Edit these separately if needed. The XML check above checks well-formedness, not full EPUB
compliance.

`read_book()` returns `None` when reading fails; `get_chapter()` returns `None`
for an unknown key. `publish_book()` returns `None` on success and propagates save errors. It is a convenience wrapper
around `pypublib.epub.save_book()`.

To overwrite the input EPUB, set `destination = source`. For imported books, saving writes a temporary archive beside
the destination and replaces the destination only after a successful write. The destination directory must exist. To
inspect the saved result, load it again with `read_book(destination)`.

Chapter edits retain the surrounding XHTML, including head elements, namespaces, body attributes, and embedded styles.
Changing an imported chapter's title keeps its filename. Metadata changes update the corresponding existing XML
elements; repeated authors and metadata refinements remain present. Adding or removing chapters updates the manifest,
spine, and existing table of contents without replacing its authored hierarchy. Existing navigation labels are preserved
when chapter titles change. Imported books are saved through a temporary file followed by atomic replacement, so the
original survives a failed save.

For edits beyond the convenience properties, imported books expose:

- `book.archive_entries`: a dictionary of archive paths to file contents as bytes, including navigation documents and
  resources not represented by typed fields.
- `book.package_document`: the full OPF as an `lxml.etree.ElementTree`, including repeated metadata elements,
  namespaces, extension elements, and attributes.
- `book.spine`: the original reading-order IDs. Non-spine XHTML documents are available in `book.chapters` without
  automatically becoming spine entries.

Use `package_document` for precise OPF edits and `archive_entries` for raw file or navigation edits. Explicit changes
through chapter/resource properties take precedence over raw entry changes to the same file. The `metadata` dictionary
remains a convenience view: for repeated fields other than subjects, it exposes the last value; use `package_document`
to edit a particular author or refinement. Resources that cannot be decoded or parsed remain available as original
bytes. New `Book` instances continue to generate their EPUB structure when saved.

Resource references are resolved relative to the referring document. For example,
`book.get_resource("../Images/cover.png", "Text/chapter.xhtml")` returns the image registered as `Images/cover.png`. The
reader, resource validation, and resource cleanup use this same resolution, including percent escapes, queries, and
fragments. Matching never falls back to filenames from unrelated directories.

Saving rejects colliding resource paths (including differently spelled URLs that resolve to the same ZIP entry), paths
outside the archive, and attempts to overwrite unrelated original entries. Edited OPF documents must have unique
manifest IDs and local resource paths, existing local targets, and valid spine references. Conflicting model and
manifest/spine edits raise `ValueError` before replacing the destination. If you remove a manifest item directly through
`package_document`, also remove its spine references; an unchanged chapter model no longer recreates the deleted item.

Metadata keys distinguish XML namespaces: `title` refers to Dublin Core, while extension fields use expanded names such
as `{urn:custom}title`. An OPF `meta`
element named `title` uses `{http://www.idpf.org/2007/opf}meta/title`, so editing the book title cannot accidentally
overwrite that separate metadata field.

When an imported chapter's `href` changes, saving updates links from XML-based documents and CSS to that chapter. Moving
it into a different directory also rebases its image, stylesheet, script, and inline CSS references. Generated links
encode special filename characters and preserve queries and fragments. XML
`xml:base` and XHTML `<base>` declarations are taken into account. Unchanged documents retain their original bytes; if a
document cannot be parsed safely during this update, saving fails before replacing the destination.

## The API

The library provides a simple API for creating and manipulating EPUB files.

### Classes

The main classes and functions include:

- `Book`: Represents an EPUB book, with methods to add chapters, images, and metadata.
- `Chapter`: Represents a chapter in the book, with methods to set the title and content.
- `Opf`: Parses an OPF file and exposes its metadata, manifest, spine and guide.

The `Book` and `Chapter` classes are the structures / containers for creating and manipulating EPUB files.

### Functions

The most important functions are:

- `read_book`: Imports an existing EPUB file and returns a `Book`, or `None` on failure.
- `publish_book` / `save_book`: Saves a generated or modified `Book` as an EPUB file.
- `validate_book`: Returns a list of detected metadata and resource issues.

## Usage

To create a new EPUB file, you simply

1. Create a `Book` object.
2. Create `Chapter` objects and add them to the book. The order of chapters defines the reading order.
3. Set HTML content and titles for each chapter. The content is simply the `BODY` of the XHTML file.
4. Add stylesheets and images to `Chapters` and `Book` as desired.
5. Set metadata for the book.
6. Finally, call `publish_book` to generate the EPUB file.

### Example - Create a simple EPUB file

```python
from pypublib.book import Book, Chapter
from pypublib.epub import publish_book, validate_book

book = Book()
chapter1 = Chapter.from_content(href="Chapter1.xhtml", title="Chapter 1", content="<h1>Hello world!</h1>",
                                styles="styles.css")
chapter1.content += "<p>This is the first chapter of the book.</p>"
book.add_chapter(chapter1)
book.add_style("styles.css", "body { font-family: Arial, sans-serif; }")
book.title = "My First EPUB"
book.author = "John Doe"
book.language = "en"
validate_book(book)
publish_book(book, "book.epub")
```

## Further Examples

The directory `examples` contains some example scripts demonstrating the use of the library to create and manipulate
EPUB files.

## Requirements

pypublib needs only lxml for parsing and generating XML/HTML files. It supports Python 3.10 and higher.

- Python 3.10 or higher
- lxml 6.0.4 or higher
