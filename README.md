# PyPubLib

## A Python library for ePub files

[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![EPUB](https://img.shields.io/badge/EPUB-supported-green.svg)](https://www.w3.org/publishing/epub32/epub-spec.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI](https://github.com/infaktum/pypublib/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/infaktum/pypublib/actions/workflows/ci-tests.yml)
[![codecov](https://codecov.io/gh/infaktum/pypublib/branch/main/graph/badge.svg)](https://codecov.io/gh/infaktum/pypublib)

This project provides tools and utilities for generating and manipulating EPUB files using Python.
It includes functions to create essential EPUB components such as `nav.xhtml`, `toc.ncx`, and the manifest, making it
easier to build valid EPUB 2 and EPUB 3 ebooks programmatically.

![Cover.jpg](images/Cover.jpg)

## What is EPUB?

EPUB (Electronic Publication) is a widely used open standard for e-books, maintained by the W3C.
EPUB files are essentially ZIP archives containing XHTML content, images, stylesheets, and metadata. The format supports
reflowable content, making it suitable for various screen sizes and devices.

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

## The API

The library provides a simple API for creating and manipulating EPUB files.

### Classes

The main classes and functions include:

- `Book`: Represents an EPUB book, with methods to add chapters, images, and metadata.
- `Chapter`: Represents a chapter in the book, with methods to set the title and content.
- `OPF`: Represents the OPF file, with methods to add metadata, manifest items, and spine items. Used to import an EPUB
  book by parsing the OPF file.

The `Book` and `Chapter` classes are the structures / containers for creating and manipulating EPUB files.

### Functions

The most important functions are:

- `read_epub`: Imports an existing EPUB file and returns a `Book` object with all chapters, styles and images.
- `publish_epub`: Publishes a generated or modified `Book` object as an EPUB file.
- `validate_epub`: Validates the structure and contents of an EPUB file.

## Usage

To create a new EPUB file, you simply

1. Create a `Book` object.
2. Create `Chapter` objects and add them to the book. The order of chapters defines the reading order.
3. Set HTML content and titles for each chapter. The content is simply the `BODY` of the XHTML file.
4. Add stylesheets and images to `Chapters` and `Book` as desired.
5. Set metadata for the book.
6. Finally, call `publish_epub` to generate the EPUB file.

### Example - Create a simple EPUB file

```python
from pypublib.book import Book, Chapter
from pypublib.epub import publish_book, validate_book

book = Book()
chapter1 = Chapter.from_content(href="Chapter1.xhtml", title="Chapter 1", content="<1>Hello world!</h1>",
                                styles="styles.css")
chapter1.content += "<p>This is the first chapter of the book.</p>"
book.add_chapter(chapter1)
book.add_style("styles.css", "body { font-family: Arial, sans-serif; }")
book.title = "My First EPUB"
book.author = "John Doe"
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