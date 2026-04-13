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

import uuid
import re
from string import Template
from os.path import splitext, basename
from lxml import etree
import lxml.html as lhtml

# ---------------------------- Template for a Cover Page -----------------------------------

TEMPLATE_COVER="""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="de" xml:lang="de">
  <head>
  <title>Cover</title>
 </head>
  <body style='margin: 0em; padding: 0em;'>
    <img style='max-width: 100%; max-height: 100%;' src="$cover" alt="Cover"/>
 </body>
</html>
"""

TEMPLATE_CHAPTER = """<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.1//EN' 'http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd'>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="de">
<head>
    <title>$title</title>
    $styles
</head>
<body>
    $body
</body>
</html>
"""

#---------------------------- XML Namespace -----------------------------------

NS = {"x": "http://www.w3.org/1999/xhtml"}

# ---------------------------- EPUB Chapter Class -----------------------------------

class Chapter:

    """
    Represents a single chapter (XHTML document) within the EPUB.

    The Chapter can be referenced by its href.
    A Chapter in an EPUB book is an XHTML file which is rendered by ebook reader software.
    The Chapter structure stores only the BODY content of this file, which can simply be modified
    by accessing the content attribute. The HEAD part of the file is generated on the fly, by inserting
    the stored title and stylesheet attributes in a template. This happens every time when the read-only
    html property is accessed.
    """

    # ---------------------------- Initialization ----------------------------

    def __init__(self, href: str, title: str) -> None:
        """
        Initialize a new Chapter. The HTML content and styles can be set later.
        - href: filename inside the EPUB
        - title: chapter title
        """
        self.href = href
        self._title = title
        self.content = ""
        self.styles = []

    # ---------------------------- Factory methods ----------------------------


    @classmethod
    def from_content(cls, href: str, title: str, content: str, styles: str | list[str] | None = None) -> "Chapter":
        """
        Create a Chapter instance from raw HTML content string.

        Strips any existing <body> tags and wraps the content in a full XHTML structure.
        If styles are provided, they are linked in the <head>.

        - href: filename inside the EPUB
        - title: chapter title
        - content: raw HTML content (may include <body> tags)
        - styles: list of styles hrefs or a single href as string
        """
        content = re.sub(r"</?body[^>]*>", "", content, flags=re.IGNORECASE).strip()

        chapter = cls(href, title)
        chapter.content = content
        chapter.styles = styles if isinstance(styles, list) else ([styles] if styles else [])
        return chapter

    @classmethod
    def from_xhtml(cls, href: str, html: str) -> "Chapter":
        """
        Create a Chapter instance from a raw XHTML string.
        The parser is more stict than lxml.html and expects well-formed XML.
        """
        try:
            doc = etree.fromstring(html.encode("utf-8"))
        except etree.ParserError as e:
            raise ValueError(f"Invalid HTML: {e}") from e
        title = (doc.find(".//x:title", namespaces=NS).text or "") if doc.find(".//x:title", namespaces=NS) is not None else ""
        styles = [link.get("href")for link in doc.findall(".//x:link[@rel='stylesheet']", namespaces=NS) if link.get("href") ]
        content = etree.tostring(doc.find(".//x:body", namespaces=NS), encoding="utf-8", method="html").decode("utf-8") \
            if doc.find(".//x:body", namespaces=NS) is not None else ""
        return cls.from_content(href, title, content, styles)

    @classmethod
    def from_html(cls, href: str, html: str) -> "Chapter":
        """
        Create a Chapter instance from a raw HTML string using lxml.html.
        The parser is more forgiving than etree and can handle typical HTML errors.
        """
        # We remove xml declaration if present, as lxml.html does not handle it well.
        html = re.sub(r'^<\?xml[^>]+\?>', '', html).strip()
        doc = lhtml.fromstring(html)

        title_el = doc.find(".//title")
        title = title_el.text if title_el is not None else ""
        styles = [link.get("href") for link in doc.findall(".//link[@rel='stylesheet']") if link.get("href")]
        body_el = doc.find(".//body")
        content = lhtml.tostring(body_el, encoding="unicode", method="html") if body_el is not None else ""
        return cls.from_content(href, title, content, styles)


    @classmethod
    def from_cover(cls, name: str) -> "Chapter":
        """ Create a synthetic cover chapter. """
        html = Template(TEMPLATE_COVER).substitute(cover = name)
        return cls.from_xhtml("Cover.xhtml", html)

    # ---------------------------- Head management ----------------------------

    def add_style(self, style: str) -> None:
        """ Add a stylesheet href to the chapter. """
        if style not in self.styles:
            self.styles.append(style)

    # ---------------------------- Content management ----------------------------

    @property
    def html(self) -> str:
        """
        Get the full chapter HTML including HEAD and BODY, by inserting the necessary data into the TEMPLATE_CHAPTER.
        The HEAD is generated on the fly from the title and styles attributes.
        The BODY is the stored content attribute.
        """
        stylesheets = "\n".join(f'<link rel="stylesheet" type="text/css" href="{sheet}"/>' for sheet in self.styles)
        body = self.content or ""
        html = Template(TEMPLATE_CHAPTER).substitute(title=self.title, styles=stylesheets, body=body)
        return html

    @property
    def title(self) -> str:
        """Get the chapter title."""
        return self._title

    @title.setter
    def title(self, title: str) -> None:
        """
        Set the chapter title. The title tag in the head is set and the href is updated.
        :param title: new title string
        """
        self._title = title
        self.href = f"{title}.xhtml"

    @property
    def images(self) -> list[str]:
        """
        Returns all src strings from img tags in this chapter.
        """
        doc = etree.fromstring(self.html.encode("utf-8"))
        imgs = doc.findall(".//x:img", namespaces=NS)
        return [img.get("src") for img in imgs if img.get("src")]

    # ---------------------------- Debug representation ----------------------------

    def __repr__(self) -> str:
        """
        Compact debug string for the chapter.
        """
        return f"Chapter(title={self.title}, href={self.href}, styles={self.styles})"


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

#----------------------------- Template for TOC NCX -----------------------------------

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

#-----------------------------  Template for EPUB OPF  -----------------------------

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
    -

    All data are stored in memory. This includes not only the chapters,
    but also the style sheets and also the images and font data als binaries.

    Use publish_book from the epub package to store all data in an EPUB file.
    The necessary OPF file is then created on he fly from the data in the Book structure.
    """

    def __init__(self, metadata: dict | None = None) -> None:
        """
        Initialize a new Book with optional metadata dict.
        Ensures an 'identifier' exists by generating a UUID if missing.
        :param metadata: Optional initial metadata dictionary. Metadata may be added later.
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


    def from_contents(self, contents: dict) -> None:
        """
        Populate the Book from a contents dictionary, typically extracted from an existing EPUB.
        The contents dict should have keys: 'metadata', 'chapters', 'styles', 'images', 'fonts', 'guide', 'cover'.
        :param contents: Dictionary with book components.
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

    # ---------------------------- Chapter management ----------------------------

    def add_chapter(self, chapter: Chapter, href: str = None) -> None:
        """
        Add or replace a chapter using its href as the key.
        """
        if href:
            self.chapters[href] = chapter
        else:
            self.chapters[chapter.href] = chapter

    def add_chapters(self, *chapters: Chapter) -> None:
        """
        Add multiple chapters in order.
        """
        for chapter in chapters:
            self.add_chapter(chapter)

    def get_chapter(self, href):
        """
        Return the chapter by href or None if not found.
        """
        return self.chapters.get(href)

    # ---------------------------- Stylesheet management ----------------------------

    def add_style(self, name: str, sheet: str) -> None:
        """
        Add a global stylesheet.
        - name: target filename inside the EPUB
        - sheet: CSS content (str or bytes)
        """
        self.styles[name] = sheet

    def add_styles(self, styles: dict) -> None:
        """
        Add multiple styles from a dict of {name: sheet}.
        """
        for name, sheet in styles.items():
            self.add_style(name, sheet)

    def add_style_from_file(self, file: str) -> None:
        """
        Add a global stylesheet.
        - file: path to a CSS file
        Reads the file content and uses the filename (without extension) as the key.
        """
        with open(file, "r", encoding="utf-8") as f:
            self.styles[basename(file)] = f.read()

    # ---------------------------- Image management ----------------------------

    def add_image(self, name: str, image: bytes | bytearray) -> None:
        """
        Add an image asset.
        - name: target filename inside the EPUB
        - image: binary data (bytes/bytearray)
        """
        self.images[name] = image

    def add_images(self, images: dict) -> None:
        """
        Add multiple images from a dict of {name: image}.
        """
        for name, image in images.items():
            self.add_image(name, image)

    def add_image_from_file(self, file: str) -> None:
        """
        Add an image asset.
        - file: image filename
        """
        with open(file, "rb") as f:
            self.images[basename(file)] = f.read()

    # ---------------------------- Cover management ----------------------------

    def add_cover(self, cover: str, image: bytes | bytearray) -> None:
        """
        Add a cover image and set it as the book cover.
        Also prepends a synthetic 'Cover.xhtml' chapter.
        """
        self.images[cover] = image
        self.set_cover(cover)

    def set_cover(self, cover: str) -> None:
        """
        Set the cover image filename and ensure a cover chapter is the first entry.
        """
        self.cover = cover
        cover_chapter = Chapter.from_cover(cover)
        # Prepend cover chapter to existing chapters
        self.chapters = {cover_chapter.href: cover_chapter, **self.chapters}

    @property
    def cover_image(self) -> bytes | bytearray | None:
        """
        Return the raw cover image content.
        """
        return self.images[self.cover]

    # ---------------------------- Font management ----------------------------

    def add_font(self, name, font):
        """
        Add an embedded font file.
        """
        self.fonts[name] = font

    # ---------------------------- Metadata properties (Dublin Core) ----------------------------

    @property
    def title(self) -> str:
        """Human-readable title of the book."""
        return self.metadata.get("title", "")

    @title.setter
    def title(self, value: str) -> None:
        self.metadata["title"] = value.strip()

    @property
    def creator(self) -> str:
        """Primary creator/author."""
        return self.metadata.get("creator")

    @creator.setter
    def creator(self, value: str) -> None:
        self.metadata["creator"] = value.strip()

    @property
    def author(self) -> str:
        """Primary creator/author."""
        return self.metadata.get("creator")

    @author.setter
    def author(self, value: str) -> None:
        self.metadata["creator"] = value.strip()

    @property
    def language(self) -> str:
        """Language code (e.g., 'en', 'de')."""
        return self.metadata.get("language", "")

    @language.setter
    def language(self, value: str) -> None:
        self.metadata["language"] = value.strip()

    @property
    def identifier(self) -> str:
        """Unique identifier (e.g., UUID, ISBN)."""
        return self.metadata.get("identifier", "")

    @identifier.setter
    def identifier(self, value: str) -> None:
        self.metadata["identifier"] = value.strip()

    @property
    def description(self) -> str:
        """Short description or abstract."""
        return self.metadata.get("description", "")

    @description.setter
    def description(self, value: str) -> None:
        self.metadata["description"] = value.strip()

    @property
    def publisher(self) -> str:
        """Publisher name."""
        return self.metadata.get("publisher", "")

    @publisher.setter
    def publisher(self, value: str) -> None:
        self.metadata["publisher"] = value.strip()

    @property
    def date(self) -> str:
        """Publication date as string (ISO\-8601 recommended)."""
        return self.metadata.get("date", "")

    @date.setter
    def date(self, value: str) -> None:
        self.metadata["date"] = value.strip()

    @property
    def subject(self) -> list[str]:
        """List of subjects/keywords."""
        return self.metadata.get("subject", set())

    @subject.setter
    def subject(self, subjects: str | tuple[str]) -> None:
        """
        Add  subject/keyword to the metadata.
        """
        if "subject" not in self.metadata:
            self.metadata["subject"] = set()

        subjects = subjects if isinstance(subjects,tuple) else (subjects,)
        for subject in subjects:
            if subject.strip() :
                self.metadata["subject"].add(subject.strip())

    # ---------------------------- Calibre/extended metadata ----------------------------

    @property
    def series(self) -> str:
        """Gibt den Seriennamen zurück."""
        return self.metadata.get("series", "")

    @series.setter
    def series(self, value):
        """
        Setzt den Seriennamen und optional den Index.
        value: entweder String (nur Name) oder Tuple (Name, Index)
        """
        if isinstance(value, tuple):
            self.metadata["series"] = value[0].strip()
            if len(value) > 1 and value[1] is not None:
                self.metadata["series_index"] = value[1]
        else:
            self.metadata["series"].append(str(value).strip())
            

    # ---------------------------- Generic metadata helpers ----------------------------

    def add_metadata(self, key, value):
        """
        Add or replace an arbitrary metadata key/value pair.
        """
        self.metadata[key] = value

    def set_metadata(
        self, creator=None, title=None, language="de", identifier=None,
        description=None, publisher=None, date=None):
        """
        Bulk metadata setter. Only non\-empty values are applied.
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

    # ---------------------------------- Create Nav.xhtml ---------------------------------------

    @property
    def nav(self) -> str:
        title = "Inhaltsverzeichnis" if self.language == "de" else "Table of Contents"

        nav_items = "\n".join(
            f'<li><a href="{chapter.href}">{chapter.title}</a></li>'
            for _, chapter in self.chapters.items()
        )
        nav = Template(TEMPLATE_NAV).substitute(title=title,nav_items=nav_items)
        return nav

    # --------------------------------- Create TOC NCX -------------------------------------

    @property
    def toc(self) -> str:
        return self.ncx

    @property
    def ncx(self) -> str:
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

        toc = Template(TEMPLATE_TOC).substitute(book_id=getattr(self, "uid", "bookid"), title=title, nav_points=nav_points)

        return toc

    # -------------------------------------- Create Manifest----------------------------------------

    @property
    def manifest(self) -> list:
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
        manifest += [{"id": f"{splitext(href)[0]}", "href": href, "media-type": f"font/{splitext(href)[1][1:]}"} for i, href
                     in enumerate(self.fonts)]
        return manifest

    # ------------------------------------- Create OPF XML --------------------------------------


    @property
    def opf(self) -> str:

        spine = [chapter.href for chapter in self.chapters.values() if
                 chapter.href != "nav.xhtml" and chapter.href != "toc.ncx"]

        metadata_items = "\n".join(
            f'<dc:{key}>{value}</dc:{key}>' for key, value in self.metadata.items() if value and key in DC_METADATA)

        metadata_items += "\n".join(
            f'<dc:subject>{value}</dc:subject>' for value in self.subject )

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
                               manifest_items).replace("$spine_items", spine_items).replace("$guide", guide)

        return opf

    # ---------------------------- Debug representation ----------------------------

    def __repr__(self):
        """
        Compact debug string with selected metadata and asset counts.
        """
        return (
            f"Book(title = {self.title}, author = {self.author}, "
            f"chapters={len(self.chapters)}, styles={len(self.styles)}, "
            f"images={len(self.images)}, fonts={len(self.fonts)})"
        )


#------------------------------------ OPF Parser -------------------

class Opf:
    """
    A parser for the OPF file of an EPUB (content.opf). Parses the OPF XML and provides access to its components.
    Attributes:
        xml (etree.Element): The root element of the OPF XML.
    Methods:
        manifest: Reads all <item> elements from <manifest> and returns them as a list of dicts.
        metadata: Returns all metadata tags from <metadata> as a dict {name: text}.
        spine: Returns all idref values from <spine>/<itemref> as a list
        guide: Reads all <reference> elements from <guide> and returns them as a list of dicts.
    """
    def __init__(self, opf_xml) -> None:
        """
            Initializes the Opf object by parsing the provided OPF XML string.
            :param opf_xml: OPF XML as a string
        """
        self.xml = etree.fromstring(opf_xml)

    @classmethod
    def from_file(cls, opf_file: str) -> "Opf":
        """
        Creates an Opf instance by reading the contents of the Opf file.
        :param opf_file: path to file.
        :return: Opf instance
        """
        with open(opf_file, "r", encoding="utf-8") as f:
            opf_xml = f.read()
            return cls(opf_xml)

    @property
    def cover(self) -> str | None:
        """
        Returns the href of the cover item from <manifest>, if present.
        """
        cover_item = self.xml.xpath(".//*[local-name()='manifest']/*[local-name()='item'][@properties='cover-image']")
        return cover_item[0].get("href") if cover_item else None

    @property
    def guide(self) -> list[dict[str, str]]:
        """
        Reads all <reference> elements from <guide> and returns them as a list of dicts.
        """
        return [
            {"type": el.get("type"), "title": el.get("title"), "href": el.get("href")}
            for el in self.xml.xpath(".//*[local-name()='guide']/*[local-name()='reference']")
        ]

    @property
    def manifest(self) -> list[dict[str, str]]:
        """
        Reads all <item> elements from <manifest> and returns them as a list of dicts.
        """
        return [
            {"id": el.get("id"), "href": el.get("href"), "media-type": el.get("media-type")}
            for el in self.xml.xpath(".//*[local-name()='manifest']/*[local-name()='item']")
        ]

    @property
    def metadata(self) -> dict[str, str | list[str]]:
        """
        Gibt alle Metadaten-Tags aus <metadata> als Dict zurück.
        Mehrfache <dc:subject>-Tags werden als Liste gesammelt.
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
    def spine(self) -> list[str]:
        """
        Returns all idref values from <spine>/<itemref> as a list.
        """
        return [
            el.get("idref")
            for el in self.xml.xpath(".//*[local-name()='spine']/*[local-name()='itemref']")
            if el.get("idref")
        ]