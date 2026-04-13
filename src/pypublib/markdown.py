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

# ------------------------------------- Html -------------------------------------

class Html:
    """Generates HTML content"""

    @staticmethod
    def p(text, class_name=None):
        """Generates an HTML paragraph."""
        class_attr = f' class="{class_name}"' if class_name else ''
        return f'<p{class_attr}>{text}</p>'

    @staticmethod
    def strong(text):
        """Replaces text with <strong>."""
        return f'<strong>{text}</strong>'

    @staticmethod
    def em(text):
        """Replaces text <em>."""
        return f'<em>{text}</em>'

    @staticmethod
    def header(text, level=1):
        """Generates an HTML header."""
        return f'<h{level}>{text}</h{level}>'

    @staticmethod
    def h1 (text):
        return Html.header(text, level=1)
    @staticmethod
    def h2 (text):
        return Html.header(text, level=2)
    @staticmethod
    def h3 (text):
        return Html.header(text, level=3)
    @staticmethod
    def h4 (text):
        return Html.header(text, level=4)
    @staticmethod
    def h5 (text):
        return Html.header(text, level=5)
    @staticmethod
    def h6 (text):
        return Html.header(text, level=6)

    @staticmethod
    def link(href, text, class_name=None):
        """Generates an HTML link."""
        class_attr = f' class="{class_name}"' if class_name else ''
        return f'<a href="{href}"{class_attr}>{text}</a>'

    @staticmethod
    def img(src, alt_text='Image'):
        """Generates an HTML image."""
        return f'<img src="{src}" alt="{alt_text}"/>'

    @staticmethod
    def ul(items):
        """Generates an unordered HTML list."""
        list_items = '\n  '.join(f'<li>{item}</li>' for item in items)
        return f'<ul>\n  {list_items}\n</ul>'

    @staticmethod
    def ol(items):
        """Generates an ordered HTML list."""
        list_items = '\n  '.join(f'<li>{item}</li>' for item in items)
        return f'<ol>\n  {list_items}\n</ol>'

    @staticmethod
    def blockquote(text):
        """Generates an HTML blockquote."""
        return f'<blockquote>{text}</blockquote>'

    @staticmethod
    def code(code, language=''):
        """Generates an HTML code block."""
        return f'<pre><code class="{language}">{code}\n</code></pre>'

    @staticmethod
    def hr():
        """Generates a horizontal rule."""
        return '<hr/>'

    @staticmethod
    def br():
        """Generates a line break."""
        return '<br/>'
    @staticmethod
    def nbsp(count=1):
        """Generates non-breaking spaces."""
        return '&nbsp;' * count
    @staticmethod
    def pagebreak(id: int = 1) -> str:
        """Generates a page break."""
        #return f'<div xmlns:epub="http://www.idpf.org/2007/ops" epub:type="pagebreak" title="{id}" id="{id}"/>'
        return '<div style="page-break-after: always;"></div>'

# ------------------------------------- MarkdownConverter -------------------------------------

class MarkdownConverter:
    """Converts simple Markdown text to HTML."""

    @staticmethod
    def strong_or_em(text):
        """Replaces *text* with <strong> and _text_ with <em>."""
        text = re.sub(r'\*(.+?)\*', r'<strong>\1</strong>', text)
        text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
        return text

    @staticmethod
    def paragraphs(*texts):
        """Generates multiple HTML paragraphs."""
        return '\n'.join(Html.p(text) for text in texts)

    @staticmethod
    def convert(text):
        """Converts Markdown text to HTML."""
        html = [line for line in MarkdownConverter.parse(text)]
        html = '\n'.join(html)
        return MarkdownConverter.strong_or_em(html)

    @staticmethod
    def parse( text):
        """Parses Markdown text and generates HTML structures."""
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
                    items.append(lines[i].strip()[2:])
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
                    items.append(lines[i].strip()[2:])
                    i += 1
                yield Html.ol(items)
                continue

            # Codeblock-Erkennung: ''' ... '''
            if line == "```":
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []
                code_lines = []
                i += 1
                while i < len(lines) and lines[i].strip() != "```":
                    code_lines.append(lines[i])
                    i += 1
                yield Html.code('\n'.join(code_lines))
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
                yield Html.header(header_match.group(2), level=level)

            elif line.startswith('> '):
                if buffer:
                    yield Html.p(' '.join(buffer))
                    buffer = []
                yield Html.blockquote(line[2:])

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
                buffer.append(line)
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

