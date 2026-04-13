import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pypublib.markdown import MarkdownConverter, Html
from pypublib.book import Book, Chapter
from pypublib.epub import publish_book, validate_book

def main():


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

    book = Book({'title':'The Markdown Book','creator':'Marcus Markdown'})

    chapter1 = Chapter(href='Markdown.xhtml', title='Markdown Chapter')
    chapter1.add_style("styles.css")

    chapter1.content = MarkdownConverter.convert(sample_text)
    book.add_chapter(chapter1)

    chapter2 = Chapter("AnotherChapter.xhtml", "Another Chapter")
    chapter2.add_style("styles.css")
    chapter2.content += Html.h1("This chapter is created with Html functions")

    chapter2.content += Html.p("This is a paragraph created with Html.p()")
    chapter2.content += Html.p("This paragraph has some " + Html.em("emphasized text") + " and some " + Html.strong("strong text") + ".")
    chapter2.content += Html.img(src="md.png")
    chapter2.content += Html.p("This paragraph should be red.", "red")
    chapter2.content += Html.h2("Unnumbered list")
    chapter2.content += Html.ul([f'Bullet item {i}' for i in range(1, 6)])
    chapter2.content += Html.h2("Numbered list")
    chapter2.content += Html.ol([f'List item {i}' for i in range(1, 3)])
    chapter2.content += Html.h2("A quote")
    chapter2.content += Html.blockquote("To be, or not to be, that is the question.")
    book.add_chapter(chapter2)

    book.add_style_from_file("styles.css")
    book.add_image_from_file("md.png")

    print(f'Created {book}')
    publish_book(book, "MarkdownBook.epub")


if __name__ ==   "__main__":
    main()
