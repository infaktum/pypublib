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
#
#
#

# MIT License
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
#
from __future__ import annotations

import mimetypes
import uuid
from datetime import datetime, timezone
from os.path import basename
from typing import List, Dict

from lxml import etree

from . import get_logger
from ._utils import archive_path, metadata_key
from .chapter import Chapter

# ---------------------------------------- Logger ------------------------------------------------

LOGGER = get_logger(__name__)

# XML namespaces used when building EPUB documents.
XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
XML_NS = "http://www.w3.org/XML/1998/namespace"

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
        - A generated UUID is added as an identifier if none is provided.
        - Convenience properties expose common metadata as attributes.
        - All data are stored in memory. This includes chapters, style sheets, images,
          and font data as binaries.
        - Use: func:`publish_book` from the epub module to store all data in an EPUB file.
          The necessary OPF file is then created on the fly from the data in the Book structure.

    Attributes:
        metadata (dict): Dublin Core and custom metadata key-value pairs.
        chapters (dict): Mapping of href to Chapter instances.
        styles (dict): Mapping of filename to CSS content.
        images (dict): Mapping of filename to binary image data.
        fonts (dict): Mapping of filename to binary font data.
        guide (list): List of guide reference items.
        cover (str): Filename of the cover image.
        archive_entries (dict[str, bytes]): Original archive files for imported books.
        package_document (etree._ElementTree | None): Complete editable imported OPF.
        spine (list[str]): Imported reading-order manifest IDs.
    """

    def __init__(self, metadata: Dict | None = None) -> None:
        """
        Initialize a new Book with an optional metadata dict.

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
        self.spine = []
        self.archive_entries = {}
        self.package_document = None
        self._archive = None
        if not self.identifier:
            self.identifier = "pypublib:" + str(uuid.uuid4())
        self.add_metadata("generator", "pypublib 0.1.0")

    def from_contents(self, contents: Dict) -> None:
        """
        Populate the Book from a content dictionary, typically extracted from an existing EPUB.

        Args:
            contents (dict): Dictionary with book components. Should have keys:
                'metadata', 'chapters', 'styles', 'images', 'fonts', 'guide', 'cover'.
        """
        if contents.get("archive_records"):
            from .epub import create_book
            self.__dict__.update(create_book(contents).__dict__)
            return
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
        Add a new chapter or replace a chapter using its href as the key.

        Args:
            chapter (Chapter): The chapter to add.
            href (str, optional): Set the chapter's output href. Defaults to chapter.href.
        """
        target = chapter.href if href is None else href
        if not isinstance(target, str) or not target.strip():
            raise ValueError('A chapter href must be a non-empty string')
        chapter.href = target
        for key, existing in list(self.chapters.items()):
            if existing is chapter:
                if self._archive is not None and self._archive.groups['chapters'].get(key) is chapter:
                    # Preserve the import key so ArchiveState can rewrite references.
                    return
                if key != target:
                    del self.chapters[key]
        self.chapters[target] = chapter

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

    def resolve_resource(self, href: str, base_href: str | None = None) -> str | None:
        """
        Resolve a resource reference to its normalized archive path.

        Args:
            href (str): Resource URL, possibly containing percent escapes, a
                query string, or a fragment.
            base_href (str | None): OPF-relative href of the referring chapter
                or stylesheet. If omitted, the href is relative to the OPF itself.

        Returns:
            str | None: Archive path, or None for an external or data URL.

        Example:
            >>> Book().resolve_resource('../Images/cover.png', 'Text/one.xhtml')
            'OEBPS/Images/cover.png'
        """
        package_path = self._archive.path if self._archive is not None else 'OEBPS/content.opf'
        base = archive_path(package_path, base_href) if base_href is not None else package_path
        return archive_path(base, href) if base is not None else None

    def resource_key(self, resources: Dict, href: str, base_href: str | None = None) -> str | None:
        """
        Find a resource-map key by comparing fully resolved paths.

        Args:
            resources (dict): Resource mapping whose keys are OPF-relative hrefs.
            href (str): Reference to locate in the mapping.
            base_href (str | None): OPF-relative referring document, if applicable.

        Returns:
            str | None: Original mapping key, or None if no local match exists.
            Matching is case-sensitive and never falls back to the basename.
        """
        target = self.resolve_resource(href, base_href)
        if target is None:
            return None
        return next((key for key in resources if self.resolve_resource(key) == target), None)

    def get_resource(self, href: str, base_href: str | None = None) -> bytes:
        """
        Read a local resource through its resolved reference.

        Args:
            href (str): Resource URL to read.
            base_href (str | None): OPF-relative referring chapter or stylesheet.

        Returns:
            bytes: Resource contents. Editable text resources are UTF-8 encoded.
                Resources unavailable in typed maps use the original archive bytes.

        Raises:
            KeyError: If the resource is missing or refers to an external URL.
        """
        for group in ('styles', 'images', 'fonts', 'chapters'):
            resources = getattr(self, group)
            key = self.resource_key(resources, href, base_href)
            if key is not None:
                value = resources[key].html if group == 'chapters' else resources[key]
                return value.encode('utf-8') if isinstance(value, str) else bytes(value)
        path = self.resolve_resource(href, base_href)
        if path is not None and path in self.archive_entries:
            return self.archive_entries[path]
        raise KeyError(href)

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

        Reads the file as a binary and uses the filename as the key.

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
        self.chapters = {cover_chapter.href: cover_chapter,
                         **{href: chapter for href, chapter in self.chapters.items()
                            if href != cover_chapter.href}}

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
            >>> book.series = "My Series"
            >>> book.series = ("My Series", 1)
        """
        if isinstance(value, tuple):
            self.metadata["series"] = value[0].strip()
            if len(value) > 1 and value[1] is not None:
                self.metadata["series_index"] = value[1]
        else:
            self.metadata["series"] = str(value).strip()

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

        Creates the navigation document with the table of contents and landmarks.

        Returns:
            str: XHTML content for nav.xhtml file.
        """
        if self._archive is not None:
            for href, kind in self._archive.navigation.items():
                if kind == "nav":
                    return self._archive.navigation_bytes(self, href).decode("utf-8")
        title = "Inhaltsverzeichnis" if self.language == "de" else "Table of Contents"

        root = etree.Element(etree.QName(XHTML_NS, "html"),
                             nsmap={None: XHTML_NS, "epublib": EPUB_NS})
        root.set("lang", "de-DE")
        root.set(etree.QName(XML_NS, "lang"), "de-DE")
        head = etree.SubElement(root, etree.QName(XHTML_NS, "head"))
        etree.SubElement(head, etree.QName(XHTML_NS, "title")).text = title
        etree.SubElement(head, etree.QName(XHTML_NS, "meta"), charset="utf-8")
        if 'sgc-nav.css' in self.styles:
            etree.SubElement(head, etree.QName(XHTML_NS, "link"),
                             href="sgc-nav.css", rel="stylesheet", type="text/css")
        body = etree.SubElement(root, etree.QName(XHTML_NS, "body"))
        body.set(etree.QName(EPUB_NS, "type"), "frontmatter")
        nav = etree.SubElement(body, etree.QName(XHTML_NS, "nav"), id="toc", role="doc-toc")
        nav.set(etree.QName(EPUB_NS, "type"), "toc")
        etree.SubElement(nav, etree.QName(XHTML_NS, "h1")).text = title
        items = etree.SubElement(nav, etree.QName(XHTML_NS, "ol"))
        for chapter in self.chapters.values():
            item = etree.SubElement(items, etree.QName(XHTML_NS, "li"))
            etree.SubElement(item, etree.QName(XHTML_NS, "a"), href=chapter.href).text = chapter.title
        landmarks = etree.SubElement(body, etree.QName(XHTML_NS, "nav"), id="landmarks", hidden="")
        landmarks.set(etree.QName(EPUB_NS, "type"), "landmarks")
        etree.SubElement(landmarks, etree.QName(XHTML_NS, "h2")).text = "Orientierungsmarken"
        items = etree.SubElement(landmarks, etree.QName(XHTML_NS, "ol"))
        item = etree.SubElement(items, etree.QName(XHTML_NS, "li"))
        link = etree.SubElement(item, etree.QName(XHTML_NS, "a"), href="#toc")
        link.set(etree.QName(EPUB_NS, "type"), "toc")
        link.text = "Inhaltsverzeichnis"
        return etree.tostring(root, encoding="utf-8", xml_declaration=True,
                              doctype="<!DOCTYPE html>", pretty_print=True).decode("utf-8")

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
        if self._archive is not None:
            for href, kind in self._archive.navigation.items():
                if kind == "ncx":
                    return self._archive.navigation_bytes(self, href).decode("utf-8")
        title = "Inhaltsverzeichnis" if self.language == "de" else "Table of Contents"

        root = etree.Element(etree.QName(NCX_NS, "ncx"), nsmap={None: NCX_NS}, version="2005-1")
        head = etree.SubElement(root, etree.QName(NCX_NS, "head"))
        for name, value in (("dtb:uid", getattr(self, 'uid', self.identifier)),
                            ("dtb:depth", "1"), ("dtb:totalPageCount", "0"),
                            ("dtb:maxPageNumber", "0")):
            etree.SubElement(head, etree.QName(NCX_NS, "meta"), name=name, content=str(value))
        doc_title = etree.SubElement(root, etree.QName(NCX_NS, "docTitle"))
        etree.SubElement(doc_title, etree.QName(NCX_NS, "text")).text = title
        nav_map = etree.SubElement(root, etree.QName(NCX_NS, "navMap"))
        for i, chapter in enumerate(self.chapters.values(), 1):
            point = etree.SubElement(nav_map, etree.QName(NCX_NS, "navPoint"),
                                     id=f"navPoint-{i}", playOrder=str(i))
            label = etree.SubElement(point, etree.QName(NCX_NS, "navLabel"))
            etree.SubElement(label, etree.QName(NCX_NS, "text")).text = chapter.title
            etree.SubElement(point, etree.QName(NCX_NS, "content"), src=chapter.href)
        return etree.tostring(root, encoding="utf-8", xml_declaration=True,
                              pretty_print=True).decode("utf-8")

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
        if self._archive is not None:
            root = etree.fromstring(self._archive.package(self))
            return [dict(item.attrib) for item in root.findall("{*}manifest/{*}item")]
        navigation = [
            {"id": "nav", "href": "nav.xhtml", "media-type": "application/xhtml+xml", "properties": "nav"},
            {"id": "toc.ncx", "href": "toc.ncx", "media-type": "application/x-dtbncx+xml"},
        ]
        manifest = []
        paths = {item['href'] for item in navigation}
        for group, media_type in ((self.chapters, 'application/xhtml+xml'),
                                  (self.styles, 'text/css'), (self.images, None), (self.fonts, None)):
            for href in group:
                if href in paths:
                    raise ValueError(f'Duplicate manifest resource: {href!r}')
                paths.add(href)
                item = {'id': f'resource-{len(manifest)}', 'href': href,
                        'media-type': media_type or mimetypes.guess_type(href)[0] or 'application/octet-stream'}
                if group is self.images and href == self.cover:
                    item['properties'] = 'cover-image'
                manifest.append(item)
            if group is self.chapters:
                manifest.extend(navigation)
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

        if self._archive is not None:
            return self._archive.package(self).decode("utf-8")
        root = etree.Element(etree.QName(OPF_NS, "package"), nsmap={None: OPF_NS}, version="3.0")
        root.set('unique-identifier', 'publication-id')
        metadata = etree.SubElement(root, etree.QName(OPF_NS, "metadata"),
                                    nsmap={"opf": OPF_NS, "dc": DC_NS,
                                           "calibre": "http://calibre.kovidgoyal.net/2009/metadata"})
        for key, value in self.metadata.items():
            if not value or key in {"subject", "dcterms:modified"}:
                continue
            if key in DC_METADATA:
                element = etree.SubElement(metadata, etree.QName(DC_NS, key))
                element.text = str(value)
                if key == 'identifier':
                    element.set('id', 'publication-id')
            else:
                name = f"calibre:{key}" if key in CALIBRE_METADATA else str(key)
                etree.SubElement(metadata, etree.QName(OPF_NS, "meta"), name=name, content=str(value))
        for value in self.subject:
            etree.SubElement(metadata, etree.QName(DC_NS, "subject")).text = str(value)
        etree.SubElement(metadata, etree.QName(OPF_NS, 'meta'),
                         property='dcterms:modified').text = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        manifest = etree.SubElement(root, etree.QName(OPF_NS, "manifest"))
        items = self.manifest
        identifiers = {item['href']: item['id'] for item in items}
        for item in items:
            etree.SubElement(manifest, etree.QName(OPF_NS, "item"), attrib=item)
        spine = etree.SubElement(root, etree.QName(OPF_NS, "spine"), toc="toc.ncx")
        etree.SubElement(spine, etree.QName(OPF_NS, "itemref"), idref="nav", linear="no")
        for href in self.chapters:
            if href not in {"nav.xhtml", "toc.ncx"}:
                etree.SubElement(spine, etree.QName(OPF_NS, "itemref"), idref=identifiers[href])
        if self.guide:
            guide = etree.SubElement(root, etree.QName(OPF_NS, "guide"))
            for item in self.guide:
                etree.SubElement(guide, etree.QName(OPF_NS, "reference"),
                                 attrib={key: str(item[key]) for key in ("type", "title", "href")})
        return etree.tostring(root, encoding="utf-8", xml_declaration=True,
                              pretty_print=True).decode("utf-8")

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

    Parses the OPF XML and provides access to its components, including metadata,
    manifest items, spine references, and guide entries.

    Attributes:
        xml (etree.Element): The root element of the OPF XML document.

    Methods:
        manifest: Reads all <item> elements from <manifest> and returns them as a list of dicts.
        metadata: Returns all metadata tags from <metadata> as a dict {name: text}.
        spine: Returns all idref values from <spine>/<itemref> as a list.
        guide: Reads all <reference> elements from <guide> and returns them as a list of dicts.
        cover: Returns the href of the cover image if marked with a cover-image property.
    """

    def __init__(self, opf_xml) -> None:
        """
        Initialize an Opf parser by parsing the provided OPF XML string.

        Args:
            opf_xml (str): OPF XML as a string.

        Raises:
            etree.ParserError: If the XML cannot be parsed.
        """
        self.xml = etree.fromstring(opf_xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))

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
        with open(opf_file, "rb") as f:
            opf_xml = f.read()
            return cls(opf_xml)

    @property
    def cover(self) -> str | None:
        """
        Get the href of the cover image.

        Returns the href of the cover item from the <manifest> section if it has
        the 'cover-image' property among its property tokens, otherwise returns None.

        Returns:
            str | None: The cover image href, or None if no cover is marked.
        """
        cover_item = [item for item in self.xml.findall("{*}manifest/{*}item")
                      if 'cover-image' in item.get('properties', '').split()]
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
            dict(el.attrib)
            for el in self.xml.xpath(".//*[local-name()='guide']/*[local-name()='reference']")
        ]

    @property
    def manifest(self) -> Dict[str, Dict[str, str]]:
        """
        Get all manifest items from the OPF.

        Reads all <item> elements from the <manifest> section and returns them as
        a dictionary keyed by item id. Values preserve every item attribute
        except the id used as the dictionary key, including properties,
        media-overlay, fallback, and namespaced extension attributes.

        Returns:
            dict[str, dict[str, str | None]]: Manifest item mapping keyed by id.
        """
        return {
            el.get("id"): {key: value for key, value in el.attrib.items() if key != "id"}
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
            Repeated scalar fields expose their last value in this convenience view.
            The original XML tree retains every element, attribute, and refinement.
        """
        meta = {}
        subjects = set()
        for el in self.xml.xpath(".//*[local-name()='metadata']/*"):
            tag = metadata_key(el)
            if tag is None:
                continue
            text = (el.get('content', el.text) or '').strip()
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
