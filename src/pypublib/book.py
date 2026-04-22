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


from __future__ import annotations

import uuid
from os.path import splitext, basename
from string import Template
from typing import List, Dict

import pypublib
from lxml import etree
from pypublib.chapter import Chapter

# ---------------------------------------- Logger ------------------------------------------------

LOGGER = pypublib.get_logger(__name__)

# ---------------------------- Template for Navigation (nav.xhtml) ------------------------------

TEMPLATE_NAV = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epublib="http://www.idpf.org/2007/ops" lang="de-DE" xml:lang="de-DE">
<head>
  <title>$title</title>
  <meta charset="utf-8" />
  <link href="sgc-nav.css" rel="stylesheet" type="text/css"/></head>
<body epublib:type="frontmatter">
  <nav epublib:type="toc" id="toc" role="doc-toc">
    <h1>$title</h1>
    <ol>
      $nav_items
    </ol>
  </nav>
  <nav epublib:type="landmarks" id="landmarks" hidden="">
    <h2>Orientierungsmarken</h2>
    <ol>
      <li>
        <a epublib:type="toc" href="#toc">Inhaltsverzeichnis</a>
      </li>
    </ol>
  </nav>
</body>
</html>
'''

# ----------------------------- Template for TOC NCX -----------------------------------

TEMPLATE_TOC = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="$book_id"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>$title</text>
  </docTitle>
  <navMap>
    $nav_points
  </navMap>
</ncx>'''

# -----------------------------  Template for EPUB OPF  -----------------------------

TEMPLATE_OPF = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:opf="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">
    $metadata_items
  </metadata>
  <manifest>
    $manifest_items
  </manifest>
  <spine toc="toc.ncx"> 
    $spine_items
  </spine>
    $guide
</package>"""

# ------------------------------------- Constants ---------------------------------------------

DC_METADATA = ['title', 'creator', 'description', 'date', 'language', 'publisher', 'identifier']
CALIBRE_METADATA = ['series', 'series_index']


# ---------------------------------- EPUB Book Class ---------------------------------------------

class Book:
    """
    Represents an EPUB book container holding:

    A Book instance manages all data needed for an EPUB publication:
        - metadata: Dublin Core and custom metadata
        - chapters: mapping of chapter href to Chapter instances
        - styles: global CSS stylesheets
        - images: image assets
        - fonts: embedded font files
        - guide: optional navigation aids
        - cover: filename of the cover image

    Notes:
        - A generated UUID is added as identifier if none is provided.
        - Convenience properties expose common metadata as attributes.
        - All data are stored in memory. This includes chapters, style sheets, images,
          and font data as binaries.
        - Use :func:`publish_book` from the epub module to store all data in an EPUB file.
          The necessary OPF file is then created on the fly from the data in the Book structure.

    Attributes:
        metadata (dict): Dublin Core and custom metadata key-value pairs.
        chapters (dict): Mapping of href to Chapter instances.
        styles (dict): Mapping of filename to CSS content.
        images (dict): Mapping of filename to binary image data.
        fonts (dict): Mapping of filename to binary font data.
        guide (list): List of guide reference items.
        cover (str): Filename of the cover image.
    """

    def __init__(self, metadata: Dict | None = None) -> None:
        """
        Initialize a new Book with optional metadata dict.

        Ensures an 'identifier' exists by generating a UUID if missing.

        Args:
            metadata (dict, optional): Initial metadata dictionary. Additional metadata
                can be added later. Defaults to None.
        """
        self.metadata = metadata or {}
        self.chapters = {}
        self.styles = {}
        self.images = {}
        self.fonts = {}
        self.guide = []
        self.cover = None
        if not self.identifier:
            self.identifier = "pypublib:" + str(uuid.uuid4())
        self.add_metadata("generator", "pypublib 0.1.0")

    def from_contents(self, contents: Dict) -> None:
        """
        Populate the Book from a contents dictionary, typically extracted from an existing EPUB.

        Args:
            contents (dict): Dictionary with book components. Should have keys:
                'metadata', 'chapters', 'styles', 'images', 'fonts', 'guide', 'cover'.
        """
        self.metadata = contents.get("metadata", {})
        for chapter in contents.get("chapters", []):
            self.add_chapter(chapter)
        for name, sheet in contents.get("styles", {}).items():
            self.add_style(name, sheet)
        for name, image in contents.get("images", {}).items():
            self.add_image(name, image)
        for name, font in contents.get("fonts", {}).items():
            self.add_font(name, font)
        self.guide = contents.get("guide", [])
        if "cover" in contents:
            self.set_cover(contents["cover"])

    # ----------------------------- Chapter Management -------------------------------------

    def add_chapter(self, chapter: Chapter, href: str = None) -> None:
        """
        Add a new chapter, or replace a chapter using its href as the key.

        Args:
            chapter (Chapter): The chapter to add.
            href (str, optional): Custom href to use as key. If None, uses chapter.href. Defaults to None.
        """
        if href:
            self.chapters[href] = chapter
        else:
            self.chapters[chapter.href] = chapter

    def add_chapters(self, *chapters: Chapter) -> None:
        """
        Add multiple chapters in order.

        Args:
            *chapters (Chapter): Variable length argument list of Chapter instances to add.
        """
        for chapter in chapters:
            self.add_chapter(chapter)

    def get_chapter(self, href):
        """
        Return the chapter by href or None if not found.

        Args:
            href (str): The href of the chapter to retrieve.

        Returns:
            Chapter | None: The chapter with the specified href, or None if not found.
        """
        return self.chapters.get(href)

    def remove_chapter(self, chapter: Chapter | str) -> None:
        """
        Removes the chapter from the book.

        Args:
            chapter (str): The chapter or the href of the chapter to remove.

        Returns:
            None.
        """
        if isinstance(chapter, Chapter):
            href = chapter.href
        else:
            href = chapter
        if href in self.chapters:
            del self.chapters[href]

    # ---------------------------- Stylesheet Management ----------------------------------

    def add_style(self, name: str, sheet: str) -> None:
        """
        Add a global stylesheet.

        Args:
            name (str): Target filename inside the EPUB.
            sheet (str | bytes): CSS content as string or bytes.
        """
        self.styles[name] = sheet

    def add_styles(self, styles: Dict) -> None:
        """
        Add multiple styles from a dict of {name: sheet}.

        Args:
            styles (dict): Dictionary mapping stylesheet names to CSS content.
        """
        for name, sheet in styles.items():
            self.add_style(name, sheet)

    def add_style_from_file(self, file: str) -> None:
        """
        Add a global stylesheet from a CSS file.

        Reads the file content and uses the filename as the key.

        Args:
            file (str): Path to a CSS file.
        """
        with open(file, "r", encoding="utf-8") as f:
            self.styles[basename(file)] = f.read()

    # ------------------------------ Image Management -----------------------------------

    def add_image(self, name: str, image: bytes | bytearray) -> None:
        """
        Add an image asset.

        Args:
            name (str): Target filename inside the EPUB.
            image (bytes | bytearray): Binary image data.
        """
        self.images[name] = image

    def add_images(self, images: Dict) -> None:
        """
        Add multiple images from a dict of {name: image}.

        Args:
            images (dict): Dictionary mapping image names to binary image data.
        """
        for name, image in images.items():
            self.add_image(name, image)

    def add_image_from_file(self, file: str) -> None:
        """
        Add an image asset from a file.

        Reads the file as binary and uses the filename as the key.

        Args:
            file (str): Path to an image file.
        """
        with open(file, "rb") as f:
            self.images[basename(file)] = f.read()

    # --------------------------------- Cover Management -------------------------------------

    def add_cover(self, cover: str, image: bytes | bytearray) -> None:
        """
        Add a cover image and set it as the book cover.

        Also prepends a synthetic 'Cover.xhtml' chapter.

        Args:
            cover (str): Filename of the cover image.
            image (bytes | bytearray): Binary image data.
        """
        self.images[cover] = image
        self.set_cover(cover)

    def set_cover(self, cover: str) -> None:
        """
        Set the cover image filename and ensure a cover chapter is the first entry.

        Args:
            cover (str): Filename of the cover image.
        """
        self.cover = cover
        cover_chapter = Chapter.from_cover(cover)
        # Prepend cover chapter to existing chapters
        self.chapters = {cover_chapter.href: cover_chapter, **self.chapters}

    @property
    def cover_image(self) -> bytes | bytearray | None:
        """
        Return the raw cover image content.

        Returns:
            bytes | bytearray | None: The binary cover image data, or None if no cover is set.
        """
        return self.images[self.cover]

    # ----------------------------- Font management --------------------------------------

    def add_font(self, name, font):
        """
        Add an embedded font file.

        Args:
            name (str): Target filename inside the EPUB.
            font (bytes | bytearray): Binary font data.
        """
        self.fonts[name] = font

    # ------------------------- All Metadata Properties (Dublin Core - DC) ------------------------

    @property
    def title(self) -> str:
        """
        Get the human-readable title of the book.

        Returns:
            str: The book title.
        """
        return self.metadata.get("title", "")

    @title.setter
    def title(self, value: str) -> None:
        """
        Set the book title.

        Args:
            value (str): The new title.
        """
        self.metadata["title"] = value.strip()

    @property
    def creator(self) -> str:
        """
        Get the primary creator/author.

        Returns:
            str: The creator name.
        """
        return self.metadata.get("creator")

    @creator.setter
    def creator(self, value: str) -> None:
        """
        Set the primary creator/author.

        Args:
            value (str): The creator/author name.
        """
        self.metadata["creator"] = value.strip()

    @property
    def author(self) -> str:
        """
        Get the primary creator/author (alias for creator).

        Returns:
            str: The creator name.
        """
        return self.metadata.get("creator")

    @author.setter
    def author(self, value: str) -> None:
        """
        Set the primary creator/author (alias for creator).

        Args:
            value (str): The creator/author name.
        """
        self.metadata["creator"] = value.strip()

    @property
    def language(self) -> str:
        """
        Get the language code.

        Returns:
            str: Language code (e.g., 'en', 'de').
        """
        return self.metadata.get("language", "")

    @language.setter
    def language(self, value: str) -> None:
        """
        Set the language code.

        Args:
            value (str): Language code (e.g., 'en', 'de').
        """
        self.metadata["language"] = value.strip()

    @property
    def identifier(self) -> str:
        """
        Get the unique identifier.

        Returns:
            str: Unique identifier (e.g., UUID, ISBN).
        """
        return self.metadata.get("identifier", "")

    @identifier.setter
    def identifier(self, value: str) -> None:
        """
        Set the unique identifier.

        Args:
            value (str): Unique identifier (e.g., UUID, ISBN).
        """
        self.metadata["identifier"] = value.strip()

    @property
    def description(self) -> str:
        """
        Get the book description.

        Returns:
            str: Short description or abstract.
        """
        return self.metadata.get("description", "")

    @description.setter
    def description(self, value: str) -> None:
        """
        Set the book description.

        Args:
            value (str): Short description or abstract.
        """
        self.metadata["description"] = value.strip()

    @property
    def publisher(self) -> str:
        """
        Get the publisher name.

        Returns:
            str: Publisher name.
        """
        return self.metadata.get("publisher", "")

    @publisher.setter
    def publisher(self, value: str) -> None:
        """
        Set the publisher name.

        Args:
            value (str): Publisher name.
        """
        self.metadata["publisher"] = value.strip()

    @property
    def date(self) -> str:
        """
        Get the publication date.

        Returns:
            str: Publication date as string (ISO-8601 recommended).
        """
        return self.metadata.get("date", "")

    @date.setter
    def date(self, value: str) -> None:
        """
        Set the publication date.

        Args:
            value (str): Publication date (ISO-8601 recommended).
        """
        self.metadata["date"] = value.strip()

    @property
    def subject(self) -> List[str]:
        """
        Get the list of subjects/keywords.

        Returns:
            set: Subject keywords.
        """
        return self.metadata.get("subject", set())

    @subject.setter
    def subject(self, subjects: str | tuple[str]) -> None:
        """
        Add subject/keyword to the metadata.

        Multiple subjects can be added at once using a tuple.

        Args:
            subjects (str | tuple[str]): A single subject string or tuple of subjects.
        """
        if "subject" not in self.metadata:
            self.metadata["subject"] = set()

        subjects = subjects if isinstance(subjects, tuple) else (subjects,)
        for subject in subjects:
            if subject.strip():
                self.metadata["subject"].add(subject.strip())

    # -------------------------  Calibre/Extended Metadata -------------------------------

    @property
    def series(self) -> str:
        """
        Get the series name.

        Returns:
            str: The name of the series this book belongs to.
        """
        return self.metadata.get("series", "")

    @series.setter
    def series(self, value):
        """
        Set the series name and optionally the series index.

        Args:
            value (str | tuple): Either a string (series name only) or a tuple of
                (series_name, series_index).

        Example:
            >>> pypublib.book.series = "My Series"
            >>> pypublib.book.series = ("My Series", 1)
        """
        if isinstance(value, tuple):
            self.metadata["series"] = value[0].strip()
            if len(value) > 1 and value[1] is not None:
                self.metadata["series_index"] = value[1]
        else:
            self.metadata["series"].append(str(value).strip())

    # Generic metadata helpers

    def add_metadata(self, key, value):
        """
        Add or replace an arbitrary metadata key/value pair.

        Args:
            key (str): The metadata key.
            value: The metadata value.
        """
        self.metadata[key] = value

    def set_metadata(
            self, creator=None, title=None, language="de", identifier=None,
            description=None, publisher=None, date=None):
        """
        Bulk metadata setter for common Dublin Core metadata.

        Only non-empty values are applied. Useful for setting multiple metadata
        fields at once during book initialization.

        Args:
            creator (str, optional): Creator/author name. Defaults to None.
            title (str, optional): Book title. Defaults to None.
            language (str, optional): Language code. Defaults to "de".
            identifier (str, optional): Unique identifier. Defaults to None.
            description (str, optional): Book description. Defaults to None.
            publisher (str, optional): Publisher name. Defaults to None.
            date (str, optional): Publication date. Defaults to None.
        """
        if creator:
            self.metadata["creator"] = creator.strip()
        if title:
            self.metadata["title"] = title.strip()
        if language:
            self.metadata["language"] = language.strip()
        if identifier:
            self.metadata["identifier"] = identifier.strip()
        if description:
            self.metadata["description"] = description.strip()
        if publisher:
            self.metadata["publisher"] = publisher.strip()
        if date:
            self.metadata["date"] = date.strip()

    # -----------------------  Navigation and table of contents properties ----------------------------

    @property
    def nav(self) -> str:
        """
        Generate the nav.xhtml content for EPUB3.

        Creates the navigation document with table of contents and landmarks.

        Returns:
            str: XHTML content for nav.xhtml file.
        """
        title = "Inhaltsverzeichnis" if self.language == "de" else "Table of Contents"

        nav_items = "\n".join(
            f'<li><a href="{chapter.href}">{chapter.title}</a></li>'
            for _, chapter in self.chapters.items()
        )
        nav = Template(TEMPLATE_NAV).substitute(title=title, nav_items=nav_items)
        return nav

    @property
    def toc(self) -> str:
        """
        Generate the table of contents.

        Alias for the ncx property.

        Returns:
            str: TOC NCX XML content.
        """
        return self.ncx

    @property
    def ncx(self) -> str:
        """
        Generate the toc.ncx content for EPUB2 compatibility.

        Creates the Navigation Center eXtended (NCX) document used for navigation
        in EPUB2 and as a fallback in EPUB3.

        Returns:
            str: NCX XML content.
        """
        title = "Inhaltsverzeichnis" if self.language == "de" else "Table of Contents"

        nav_points = ""
        for i, (_, chapter) in enumerate(self.chapters.items(), 1):
            nav_points += f"""
        <navPoint id="navPoint-{i}" playOrder="{i}">
        <navLabel>
          <text>{chapter.title}</text>
        </navLabel>
        <content src="{chapter.href}"/>
        </navPoint>"""

        toc = Template(TEMPLATE_TOC).substitute(book_id=getattr(self, "uid", "bookid"), title=title,
                                                nav_points=nav_points)

        return toc

    # ------------------------------------- Manifest ---------------------------------------

    @property
    def manifest(self) -> List[Dict[str, str]]:
        """
        Generate the manifest entries for the OPF file.

        Creates a list of manifest item dictionaries for all chapters, styles,
        images, and fonts in the book.

        Returns:
            list: List of manifest item dictionaries with keys 'id', 'href', and 'media-type'.

        Note:
            Cover images are marked with the 'cover-image' property.
        """
        manifest = [{"id": f"{splitext(c.href)[0]}", "href": c.href, "media-type": "application/xhtml+xml"} for _, c in
                    self.chapters.items()]
        if self.cover:
            manifest.append({"id": "Cover", "href": "Cover.xhtml", "media-type": "application/xhtml+xml"})

        manifest += [{"id": "nav", "href": "nav.xhtml", "media-type": "application/xhtml+xml", "properties": "nav"}]
        manifest += [{"id": "toc.ncx", "href": "toc.ncx", "media-type": "application/x-dtbncx+xml"}]
        manifest += [{"id": f"{splitext(href)[0]}", "href": href, "media-type": "text/css"} for i, href in
                     enumerate(self.styles)]
        manifest += [{"id": f"{splitext(href)[0]}", "href": href, "media-type": f"image/{splitext(href)[1][1:]}",
                      **({"properties": "cover-image"} if self.cover and href == self.cover else {})} for href in
                     self.images]
        manifest += [{"id": f"{splitext(href)[0]}", "href": href, "media-type": f"font/{splitext(href)[1][1:]}"} for
                     i, href
                     in enumerate(self.fonts)]
        return manifest

    # ------------------------------------- OPF Property ----------------------------------------

    @property
    def opf(self) -> str:
        """
        Generate the complete OPF (Open Packaging Format) XML content.

        Creates the content.opf file which defines the EPUB package structure,
        including metadata, manifest, spine, and guide sections.

        Returns:
            str: Complete OPF XML as a string.

        Note:
            The OPF file is the central descriptor of an EPUB archive structure.
        """

        spine = [href for (href, chapter) in self.chapters.items() if
                 href != "nav.xhtml" and href != "toc.ncx"]

        metadata_items = "\n".join(
            f'<dc:{key}>{value}</dc:{key}>' for key, value in self.metadata.items() if value and key in DC_METADATA)

        metadata_items += "\n".join(
            f'<dc:subject>{value}</dc:subject>' for value in self.subject)

        metadata_items += "\n".join(
            f'<meta name = "calibre:{key}" content = "{value}"/>' for key, value in self.metadata.items() if
            value and key in CALIBRE_METADATA)

        metadata_items += "\n".join(
            f'<meta name = "{key}" content = "{value}"/>' for key, value in self.metadata.items() if
            value and key not in DC_METADATA and key not in CALIBRE_METADATA)

        manifest_items = "\n".join(
            f'  <item id="{item["id"]}" href="{item["href"]}" media-type="{item["media-type"]}"'
            + (f' properties=\"{item["properties"]}\" />' if item.get("properties") else "/>")
            for item in self.manifest
        )

        spine_items = '<itemref idref="nav" linear="false" />' + "\n".join(
            f'<itemref idref="{splitext(idref)[0]}" />' for idref in spine)

        guide = "<guide>" + "\n".join(
            f'  <reference type="{item["type"]}" title="{item["title"]}" href="{item["href"]}" />' for item in
            self.guide) + "</guide>" if self.guide and len(self.guide) else ""

        opf = TEMPLATE_OPF.replace("$metadata_items", metadata_items).replace("$manifest_items",
                                                                              manifest_items).replace("$spine_items",
                                                                                                      spine_items).replace(
            "$guide", guide)

        return opf

    # ----------------------------- Debug representation ---------------------------

    def __repr__(self):
        """
        Return a compact debug string representation of the book.

        Returns:
            str: Compact representation including title, author, and asset counts.
        """
        return (
            f"Book(title = {self.title}, author = {self.author}, "
            f"chapters={len(self.chapters)}, styles={len(self.styles)}, "
            f"images={len(self.images)}, fonts={len(self.fonts)})"
        )


# ------------------------------------ OPF Parser ---------------------------------------

class Opf:
    """
    A parser for the OPF (Open Packaging Format) file of an EPUB (content.opf).

    Parses the OPF XML and provides access to its components including metadata,
    manifest items, spine references, and guide entries.

    Attributes:
        xml (etree.Element): The root element of the OPF XML document.

    Methods:
        manifest: Reads all <item> elements from <manifest> and returns them as a list of dicts.
        metadata: Returns all metadata tags from <metadata> as a dict {name: text}.
        spine: Returns all idref values from <spine>/<itemref> as a list.
        guide: Reads all <reference> elements from <guide> and returns them as a list of dicts.
        cover: Returns the href of the cover image if marked with cover-image property.
    """

    def __init__(self, opf_xml) -> None:
        """
        Initialize an Opf parser by parsing the provided OPF XML string.

        Args:
            opf_xml (str): OPF XML as a string.

        Raises:
            etree.ParserError: If the XML cannot be parsed.
        """
        self.xml = etree.fromstring(opf_xml)

    @classmethod
    def from_file(cls, opf_file: str) -> "Opf":
        """
        Create an Opf instance by reading the contents of an OPF file.

        Args:
            opf_file (str): Path to the OPF file.

        Returns:
            Opf: A new Opf instance parsed from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            etree.ParserError: If the XML cannot be parsed.
        """
        with open(opf_file, "r", encoding="utf-8") as f:
            opf_xml = f.read()
            return cls(opf_xml)

    @property
    def cover(self) -> str | None:
        """
        Get the href of the cover image.

        Returns the href of the cover item from the <manifest> section if it has
        the 'cover-image' property, otherwise returns None.

        Returns:
            str | None: The cover image href, or None if no cover is marked.
        """
        cover_item = self.xml.xpath(".//*[local-name()='manifest']/*[local-name()='item'][@properties='cover-image']")
        return cover_item[0].get("href") if cover_item else None

    @property
    def guide(self) -> List[Dict[str, str]]:
        """
        Get all guide reference items from the OPF.

        Reads all <reference> elements from the <guide> section and returns them
        as a list of dictionaries with keys 'type', 'title', and 'href'.

        Returns:
            list[dict[str, str]]: List of guide reference items.
        """
        return [
            {"type": el.get("type"), "title": el.get("title"), "href": el.get("href")}
            for el in self.xml.xpath(".//*[local-name()='guide']/*[local-name()='reference']")
        ]

    @property
    def manifest(self) -> Dict[str, Dict[str, str]]:
        """
        Get all manifest items from the OPF.

        Reads all <item> elements from the <manifest> section and returns them as
        a dictionary keyed by item id with values containing 'href' and
        'media-type'.

        Returns:
            dict[str, dict[str, str | None]]: Manifest item mapping keyed by id.
        """
        return {
            el.get("id"): {"href": el.get("href"), "media-type": el.get("media-type")}
            for el in self.xml.xpath(".//*[local-name()='manifest']/*[local-name()='item']")
        }

    @property
    def metadata(self) -> Dict[str, str | List[str]]:
        """
        Get all metadata from the OPF.

        Reads all metadata elements from the <metadata> section and returns them as
        a dictionary. Multiple <dc:subject> elements are collected into a set.

        Returns:
            dict[str, str | list[str]]: Dictionary with metadata key-value pairs.

        Note:
            Multiple subject tags are merged into a single 'subject' key containing a set.
        """
        meta = {}
        subjects = set()
        for el in self.xml.xpath(".//*[local-name()='metadata']/*"):
            tag = el.tag.split('}')[-1]
            text = (el.text or '').strip()
            if not text:
                continue
            if tag == "subject":
                subjects.add(text)
            else:
                meta[tag] = text
        if subjects:
            meta["subject"] = subjects
        return meta

    @property
    def spine(self) -> List[str]:
        """
        Get all spine item references from the OPF.

        Returns all idref values from <spine>/<itemref> elements, which define
        the reading order of the document.

        Returns:
            list[str]: List of item idrefs in spine order.
        """
        return [
            el.get("idref")
            for el in self.xml.xpath(".//*[local-name()='spine']/*[local-name()='itemref']")
            if el.get("idref")
        ]

    def __repr__(self) -> str:
        """Return a compact debug representation of parsed OPF content."""
        metadata = self.metadata
        title = metadata.get("title", "")
        creator = metadata.get("creator", "")
        return (
            f"Opf(title={title!r}, creator={creator!r}, cover={self.cover!r}, "
            f"manifest={len(self.manifest)}, spine={len(self.spine)}, guide={len(self.guide)})"
        )
