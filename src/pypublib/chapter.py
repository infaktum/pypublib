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
#
#
#


from __future__ import annotations

import re
from copy import deepcopy
from typing import List

import lxml.html as lhtml
from lxml import etree

from . import get_logger

# ---------------------------------------- Logger ------------------------------------------------

LOGGER = get_logger(__name__)

# ---------------------------- XML Namespace -----------------------------------

NS = {"x": "http://www.w3.org/1999/xhtml"}


# ---------------------------- EPUB Chapter Class -----------------------------------

class Chapter:
    """
    Represents a single chapter (XHTML document) within the EPUB.

    A Chapter in an EPUB book is an XHTML file rendered by ebook reader software.
    Imported XHTML is retained in full. Changes to content, title, or styles update
    only the corresponding nodes, preserving the remaining document. New chapters
    generate their HEAD and BODY using XML elements.

    Attributes:
        href (str): Filename inside the EPUB archive.
        content (str): The HTML body content of the chapter.
        styles (list[str]): List of stylesheet hrefs linked in the chapter head.
    """

    def __init__(self, href: str, title: str) -> None:
        """
        Initialize a new Chapter.

        The HTML content and styles can be set later via the content attribute
        and add_style method, or via factory methods.

        Args:
            href (str): Filename inside the EPUB archive.
            title (str): Chapter title, displayed in the document head.
        """
        self.href = href
        self._title = title
        self.content = ""
        self.styles = []
        self._original_html = None
        self._original_state = None

    # ------------------------------------ Factory Methods -------------------------------------

    @classmethod
    def from_content(cls, href: str, title: str, content: str, styles: str | List[str] | None = None) -> Chapter:
        """
        Create a Chapter instance from a raw HTML content string.

        Strips any existing <body> tags and wraps the content in a full XHTML structure.
        If styles are provided, they are linked in the <head>.

        Args:
            href (str): Filename inside the EPUB archive.
            title (str): Chapter title.
            content (str): Raw HTML content (may include <body> tags which will be stripped).
            styles (str | list[str] | None, optional): List of stylesheet hrefs or a single href as a string.
                Defaults to None.

        Returns:
            Chapter: A new Chapter instance with the provided content.

        Example:
            >>> chapter1 = Chapter.from_content("chapter1.xhtml", "Chapter 1","<p>Hello world</p>",["styles.css"])
        """
        content = re.sub(r"</?body[^>]*>", "", content, flags=re.IGNORECASE).strip()

        chapter = cls(href, title)
        chapter.content = content
        chapter.styles = styles if isinstance(styles, list) else ([styles] if styles else [])
        return chapter

    @classmethod
    def from_xhtml(cls, href: str, html: str) -> Chapter:
        """
        Create a Chapter instance from a raw XHTML string.

        The parser is stricter than lxml.html and expects well-formed XML.
        Uses etree.fromstring for parsing which enforces XML compliance.

        Args:
            href (str): Filename inside the EPUB archive.
            html (str): Well-formed XHTML string.

        Returns:
            Chapter: A new Chapter instance parsed from the XHTML string.

        Raises:
            ValueError: If the HTML is not valid XHTML or cannot be parsed.

        Note:
            This method expects strict XML compliance. For more forgiving parsing,
            use: meth:`from_html` instead.
        """
        try:
            doc = etree.fromstring(html.encode("utf-8"),
                                   parser=etree.XMLParser(resolve_entities=False, no_network=True))
        except etree.ParserError as e:
            raise ValueError(f"Invalid HTML: {e}") from e
        title = (doc.find(".//x:title", namespaces=NS).text or "") if doc.find(".//x:title",
                                                                               namespaces=NS) is not None else ""
        styles = [link.get("href") for link in doc.findall(".//x:link[@rel='stylesheet']", namespaces=NS) if
                  link.get("href")]
        body = doc.find(".//x:body", namespaces=NS)
        chapter = cls(href, title)
        chapter.styles = styles
        if body is not None:
            # Keep mixed text, tails, and namespace declarations in the fragment.
            text = etree.fromstring(b"<text/>")
            text.text = body.text
            chapter.content = (etree.tostring(text, encoding="unicode")[6:-7] if body.text else "")
            chapter.content += "".join(etree.tostring(child, encoding="unicode") for child in body)
        chapter._original_html = html
        chapter._original_state = (chapter.title, chapter.content, tuple(chapter.styles))
        return chapter

    @classmethod
    def from_html(cls, href: str, html: str) -> Chapter:
        """
        Create a Chapter instance from a raw HTML string using lxml.html.

        The parser is more forgiving than etree and can handle typical HTML errors.
        Automatically removes XML declarations if present.

        Args:
            href (str): Filename inside the EPUB archive.
            html (str): HTML string (may contain typical HTML errors or XML declarations).

        Returns:
            Chapter: A new Chapter instance parsed from the HTML string.

        Note:
            This method removes XML declarations automatically, making it suitable
            for non-strict HTML parsing. For strict XHTML validation, use :meth:`from_xhtml`.
        """
        # We remove xml declaration if present, as lxml.html does not handle it well.
        html = re.sub(r'^<\?xml[^>]+\?>', '', html).strip()
        doc = lhtml.fromstring(html)

        title_el = doc.find(".//title")
        title = title_el.text if title_el is not None else ""
        styles = [link.get("href") for link in doc.findall(".//link[@rel='stylesheet']") if link.get("href")]
        body_el = doc.find(".//body")
        content = lhtml.tostring(body_el, encoding="unicode", method="xml") if body_el is not None else ""
        return cls.from_content(href, title, content, styles)

    @classmethod
    def from_cover(cls, name: str) -> Chapter:
        """
        Create a synthetic cover chapter.

        Generates a Chapter containing a cover image displayed at full width and height.

        Args:
            name (str): Filename of the cover image (used in the img src attribute).

        Returns:
            Chapter: A new Chapter instance with cover styling applied.
        """
        image = etree.Element("img", src=name, alt="Cover",
                              style="max-width: 100%; max-height: 100%;")
        return cls.from_content("Cover.xhtml", "Cover",
                                etree.tostring(image, encoding="unicode", method="xml"))

    # ----------------------------------- Head Management -------------------------------------------

    @property
    def title(self) -> str:
        """
        Get the chapter title.

        Returns:
            str: The chapter title.
        """
        return self._title

    @title.setter
    def title(self, title: str) -> None:
        """
        Set the chapter title and update the href accordingly.

        New chapters update their href to "{title}.xhtml". Imported chapters keep
        their archive path so existing links and manifest references remain valid.

        Args:
            title (str): New title string.
        """
        self._title = title
        if self._original_html is None:
            self.href = f"{title}.xhtml"

    def add_style(self, style: str) -> None:
        """
        Add a stylesheet href to the chapter.

        Prevents duplicate stylesheets from being added.

        Args:
            style (str): The href of the stylesheet to add.
        """
        if style not in self.styles:
            self.styles.append(style)

    # ----------------------------------- Content Management -------------------------------------------

    @property
    def html(self) -> str:
        """
        Get the full chapter HTML including HEAD and BODY.

        Generates the HEAD section on the fly from the title and styles attributes
        and includes the stored body markup without escaping it as plain text.

        Returns:
            str: Complete XHTML document as string.
        """
        if self._original_html is not None:
            state = (self.title, self.content, tuple(self.styles))
            if state == self._original_state:
                return self._original_html
            root = etree.fromstring(self._original_html.encode("utf-8"),
                                    parser=etree.XMLParser(resolve_entities=False, no_network=True))
            head = root.find("x:head", NS)
            if head is None:
                head = etree.SubElement(root, etree.QName(NS["x"], "head"))
            if self.title != self._original_state[0]:
                title = head.find("x:title", NS)
                if title is None:
                    title = etree.SubElement(head, etree.QName(NS["x"], "title"))
                title.text = self.title
            if tuple(self.styles) != self._original_state[2]:
                links = head.findall("x:link[@rel='stylesheet']", NS)
                for link in links:
                    if link.get("href") not in self.styles:
                        head.remove(link)
                for sheet in self.styles:
                    if not any(link.get("href") == sheet for link in links):
                        etree.SubElement(head, etree.QName(NS["x"], "link"),
                                         rel="stylesheet", type="text/css", href=sheet)
            if self.content != self._original_state[1]:
                body = root.find("x:body", NS)
                if body is None:
                    body = etree.SubElement(root, etree.QName(NS["x"], "body"))
                # Serialize an empty copy to retain all in-scope namespaces.
                wrapper = deepcopy(body)
                wrapper.text = None
                for child in list(wrapper):
                    wrapper.remove(child)
                wrapper.text = "__PYPUBLIB_BODY__"
                markup = etree.tostring(wrapper, encoding="unicode", with_tail=False)
                before, _, after = markup.rpartition("__PYPUBLIB_BODY__")
                markup = before + (self.content or "") + after
                replacement = etree.fromstring(markup.encode("utf-8"),
                                               parser=etree.XMLParser(resolve_entities=False, no_network=True))
                body.text = replacement.text
                for child in list(body):
                    body.remove(child)
                body.extend(replacement)
            return etree.tostring(root.getroottree(), encoding="utf-8", xml_declaration=True).decode("utf-8")

        root = etree.Element(etree.QName(NS["x"], "html"), nsmap={None: NS["x"]})
        root.set(etree.QName("http://www.w3.org/XML/1998/namespace", "lang"), "de")
        head = etree.SubElement(root, etree.QName(NS["x"], "head"))
        etree.SubElement(head, etree.QName(NS["x"], "title")).text = self.title
        for sheet in self.styles:
            etree.SubElement(head, etree.QName(NS["x"], "link"),
                             rel="stylesheet", type="text/css", href=sheet)
        # content is an XHTML fragment, not a scalar text value. Parse it in the
        # XHTML namespace to preserve elements, mixed text, and escaped entities.
        body = etree.fromstring(
            ('<body xmlns="http://www.w3.org/1999/xhtml">' + (self.content or "") + '</body>').encode("utf-8"),
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
        root.append(body)
        return etree.tostring(
            root, encoding="utf-8", xml_declaration=True,
            doctype="<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.1//EN' 'http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd'>",
        ).decode("utf-8")

    @html.setter
    def html(self, page: str) -> None:
        """
        Sets the full chapter HTML including HEAD and BODY.

        Returns:
            str: Complete XHTML document as string.
        """
        try:
            parsed = Chapter.from_xhtml(self.href, page)
        except etree.XMLSyntaxError:
            parsed = Chapter.from_html(self.href, page)
        self._title = parsed.title
        self.styles = parsed.styles
        self.content = parsed.content
        self._original_html = parsed._original_html
        self._original_state = parsed._original_state

    @property
    def images(self) -> List[str]:
        """
        Get all image src attributes from img tags in this chapter.

        Parses the chapter's HTML and extracts all src attributes from <img> elements.

        Returns:
            list[str]: List of image src paths referenced in this chapter.
        """
        doc = etree.fromstring(self.html.encode("utf-8"))
        imgs = doc.findall(".//x:img", namespaces=NS)
        return [img.get("src") for img in imgs if img.get("src")]

    # -----------------------------------Debug and Print Representation -------------------------------------

    def __repr__(self) -> str:
        """
        Return a compact debug string representation of the chapter.

        Returns:
            str: Compact representation including title, href, and styles.
        """
        return f"Chapter(title={self.title}, href={self.href}, styles={self.styles})"

    def __str__(self) -> str:
        """Return a neat, human-readable chapter summary.
        Returns:
            str: Neat representation including title, href, and styles.
        """
        try:
            images = self.images
        except etree.XMLSyntaxError:
            images = []

        styles_preview = ", ".join(self.styles) if self.styles else "-"
        images_preview = ", ".join(images) if images else "-"

        return (
            "Chapter\n"
            f"  title       : {self.title or '-'}\n"
            f"  href        : {self.href or '-'}\n"
            f"  styles      : {len(self.styles)} ({styles_preview})\n"
            f"  images      : {len(images)} ({images_preview})\n"
            f"  content_len : {len(self.content or '')}"
        )
