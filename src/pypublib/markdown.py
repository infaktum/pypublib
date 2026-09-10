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
from html import escape

# ------------------------------------- Html -------------------------------------

class Html:
    """
    Generator for common HTML elements.

    Provides static methods for creating HTML elements from Python strings.
    Useful for building HTML content programmatically.
    """

    @staticmethod
    def p(text, class_name=None):
        """
        Generate an HTML paragraph element.

        Args:
            text (str): The paragraph text content.
            class_name (str, optional): CSS class name to apply. Defaults to None.

        Returns:
            str: HTML paragraph string.

        Example:
            >>> Html.p("Hello world")
            '<p>Hello world</p>'
            >>> Html.p("Styled", class_name="intro")
            '<p class="intro">Styled</p>'
        """
        class_attr = f' class="{escape(class_name, quote=True)}"' if class_name else ''
        return f'<p{class_attr}>{text}</p>'

    @staticmethod
    def strong(text):
        """
        Generate HTML strong (bold) element.

        Args:
            text (str): The text to make bold.

        Returns:
            str: HTML strong element string.
        """
        return f'<strong>{text}</strong>'

    @staticmethod
    def em(text):
        """
        Generate HTML emphasis (italic) element.

        Args:
            text (str): The text to emphasize.

        Returns:
            str: HTML emphasis element string.
        """
        return f'<em>{text}</em>'

    @staticmethod
    def header(text, level=1):
        """
        Generate an HTML header element.

        Args:
            text (str): The header text content.
            level (int, optional): Header level (1-6). Defaults to 1.

        Returns:
            str: HTML header element string (e.g., '<h1>...</h1>').

        Example:
            >>> Html.header("Title", level=1)
            '<h1>Title</h1>'
        """
        return f'<h{level}>{text}</h{level}>'

    @staticmethod
    def h1(text):
        """Generate an H1 heading. See :meth:`header`."""
        return Html.header(text, level=1)

    @staticmethod
    def h2(text):
        """Generate an H2 heading. See :meth:`header`."""
        return Html.header(text, level=2)

    @staticmethod
    def h3(text):
        """Generate an H3 heading. See :meth:`header`."""
        return Html.header(text, level=3)

    @staticmethod
    def h4(text):
        """Generate an H4 heading. See :meth:`header`."""
        return Html.header(text, level=4)

    @staticmethod
    def h5(text):
        """Generate an H5 heading. See :meth:`header`."""
        return Html.header(text, level=5)

    @staticmethod
    def h6(text):
        """Generate an H6 heading. See :meth:`header`."""
        return Html.header(text, level=6)

    @staticmethod
    def link(href, text, class_name=None):
        """
        Generate an HTML anchor (link) element.

        Args:
            href (str): The link URL.
            text (str): The link text displayed to the user.
            class_name (str, optional): CSS class name to apply. Defaults to None.

        Returns:
            str: HTML anchor element string.
        """
        class_attr = f' class="{escape(class_name, quote=True)}"' if class_name else ''
        return f'<a href="{escape(href, quote=True)}"{class_attr}>{text}</a>'

    @staticmethod
    def img(src, alt_text='Image'):
        """
        Generate an HTML image element.

        Args:
            src (str): The image source URL or path.
            alt_text (str, optional): Alternative text for the image. Defaults to 'Image'.

        Returns:
            str: HTML image element string.
        """
        return f'<img src="{escape(src, quote=True)}" alt="{escape(alt_text, quote=True)}"/>'

    @staticmethod
    def ul(items):
        """
        Generate an unordered (bulleted) HTML list.

        Args:
            items (list[str]): List of items to include as list items.

        Returns:
            str: HTML unordered list string with <li> elements.
        """
        list_items = '\n  '.join(f'<li>{item}</li>' for item in items)
        return f'<ul>\n  {list_items}\n</ul>'

    @staticmethod
    def ol(items):
        """
        Generate an ordered (numbered) HTML list.

        Args:
            items (list[str]): List of items to include as list items.

        Returns:
            str: HTML ordered list string with <li> elements.
        """
        list_items = '\n  '.join(f'<li>{item}</li>' for item in items)
        return f'<ol>\n  {list_items}\n</ol>'

    @staticmethod
    def blockquote(text):
        """
        Generate an HTML blockquote element.

        Args:
            text (str): The quoted text.

        Returns:
            str: HTML blockquote element string.
        """
        return f'<blockquote>{text}</blockquote>'

    @staticmethod
    def code(code, language=''):
        """
        Generate an HTML code block element.

        Args:
            code (str): The code content.
            language (str, optional): Programming language for syntax highlighting class.
                Defaults to empty string.

        Returns:
            str: HTML pre/code element string.
        """
        return f'<pre><code class="{escape(language, quote=True)}">{escape(code, quote=False)}\n</code></pre>'

    @staticmethod
    def hr():
        """
        Generate a horizontal rule (line break) element.

        Returns:
            str: HTML horizontal rule string.
        """
        return '<hr/>'

    @staticmethod
    def br():
        """
        Generate a line break element.

        Returns:
            str: HTML line break string.
        """
        return '<br/>'

    @staticmethod
    def nbsp(count=1):
        """
        Generate non-breaking spaces.

        Args:
            count (int, optional): Number of non-breaking spaces to generate. Defaults to 1.

        Returns:
            str: HTML non-breaking space entities string.
        """
        return '&#160;' * count

    @staticmethod
    def pagebreak(id_: int = 1) -> str:
        """
        Generate a page break element.

        Creates a CSS-based page break that works in EPUB readers.

        Args:
            id_ (int, optional): Identifier for the page break (for reference). Defaults to 1.

        Returns:
            str: HTML div element with page-break styling.
        """
        return '<div style="page-break-after: always;"></div>'

# ------------------------------------- MarkdownConverter -------------------------------------

class MarkdownConverter:
    """
    Convert simple Markdown syntax to HTML.

    Provides methods to convert basic Markdown markup to HTML elements.
    Supports headers, lists, code blocks, images, blockquotes, and text formatting.
    """

    @staticmethod
    def strong_or_em(text):
        """
        Replace Markdown bold and emphasis syntax with HTML tags.

        Converts:
            - *text* to <strong>text</strong>
            - _text_ to <em>text</em>

        Args:
            text (str): Text containing Markdown formatting.

        Returns:
            str: Text with HTML formatting applied.

        Example:
            >>> MarkdownConverter.strong_or_em("This is *bold* and _italic_")
            'This is <strong>bold</strong> and <em>italic</em>'
        """
        text = re.sub(r'\*(.+?)\*', r'<strong>\1</strong>', text)
        text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
        return text

    @staticmethod
    def paragraphs(*texts):
        """
        Generate multiple HTML paragraphs from text strings.

        Args:
            *texts (str): Variable length argument list of paragraph texts.

        Returns:
            str: Multiple HTML paragraph elements joined with newlines.

        Example:
            >>> MarkdownConverter.paragraphs("First", "Second", "Third")
            '<p>First</p>\\n<p>Second</p>\\n<p>Third</p>'
        """
        return '\n'.join(Html.p(text) for text in texts)

    @staticmethod
    def convert(text):
        """
        Convert Markdown text to HTML.

        Performs complete Markdown parsing and converts all supported Markdown
        syntax to corresponding HTML elements.

        Args:
            text (str): Markdown-formatted text.

        Returns:
            str: HTML string with all Markdown elements converted.

        Example:
            >>> markdown = "# Title\\nThis is **bold** text"
            >>> MarkdownConverter.convert(markdown)
        """
        html = [line for line in MarkdownConverter.parse(text)]
        html = '\n'.join(html)
        # Apply emphasis only to text, never to code blocks or HTML attributes.
        parts = re.split(r'(<pre\b[^>]*>.*?</pre>|<[^>]+>)', html, flags=re.DOTALL)
        return ''.join(part if part.startswith('<') else MarkdownConverter.strong_or_em(part)
                       for part in parts)

    @staticmethod
    def parse(text):
        """
        Parse Markdown text and generate HTML structures.

        Processes Markdown text line by line and yields HTML elements for:
            - Headers (# to ######)
            - Unordered lists (* items)
            - Ordered lists (. or 1. items)
            - Code blocks (``` ... ```)
            - Images (![alt](url))
            - Blockquotes (> text)
            - Horizontal rules (---)
            - Paragraphs (plain text)

        Args:
            text (str): Markdown-formatted text.

        Yields:
            str: HTML elements as strings.

        Note:
            This is a generator function that yields HTML elements
            for each parsed Markdown block.
        """
        lines = text.split('\n')
        i = 0
        buffer = []
        while i < len(lines):
            line = lines[i].strip()

            # Unordered list
            if line.startswith('* '):
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []
                items = []
                while i < len(lines) and lines[i].strip().startswith('* '):
                    items.append(escape(lines[i].strip()[2:], quote=False))
                    i += 1
                yield Html.ul(items)
                continue

            # Ordered list
            if line.startswith('. ') or line.startswith('1. '):
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []
                items = []
                while i < len(lines) and (lines[i].strip().startswith('. ') or lines[i].strip().startswith('1. ')):
                    items.append(escape(re.sub(r'^(?:1\.|\.)\s+', '', lines[i].strip()), quote=False))
                    i += 1
                yield Html.ol(items)
                continue

            # Codeblock-Erkennung: ''' ... '''
            if line.startswith("```"):
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []
                code_lines = []
                i += 1
                while i < len(lines) and lines[i].strip() != "```":
                    code_lines.append(lines[i])
                    i += 1
                yield Html.code('\n'.join(code_lines), language=line[3:].strip())
                i += 1
                continue

            # Images md style: ![Alt-Text](Bild-URL)
            image_match = re.match(r'!\[(.*?)\]\((.*?)(?: "(.*?)")?\)', line)
            if image_match:
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []
                alt_text = image_match.group(1) or 'Image'
                src = image_match.group(2)
                yield Html.img(src, alt_text)
                i += 1
                continue

            # Header up to 6 levels deep
            header_match = re.match(r'^(#{1,6}|={1,6})\s+(.*)', line)
            if header_match:
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []
                level = len(header_match.group(1))
                yield Html.header(escape(header_match.group(2), quote=False), level=level)

            elif line.startswith('> '):
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []
                yield Html.blockquote(escape(line[2:], quote=False))

            elif line == '---':
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []
                yield Html.hr()

            elif line == '':
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []


            else:
                buffer.append(escape(line, quote=False))
            i += 1
        if buffer:
            yield Html.p(' '.join(buffer))

#----------------------------------------------------------------

if __name__ == "__main__":
    sample_text = """
# Sample Document
This is a sample document to demonstrate the HTML content generation functions.
This is not a new paragraph.

But this is a new paragraph.

## Features
* Easy to use functions
* Supports various HTML elements
* Modular design
* Detects *bold words* or _emphasized longer text_
* and images:

![Markdown](md.png)

### Usage
To use these functions
1. create your markdown text
. import the MarkdownParser
. convert the text using the parser

```
html = parser.convert(text)
```
---
As we say:
> Let the framework do the rest!
"""
    converter = MarkdownConverter()
    print(converter.convert(sample_text))

