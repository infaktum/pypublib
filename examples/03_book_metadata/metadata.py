import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pypublib.epub import publish_book, read_book

from pypublib.book import Book, Chapter

book = Book()

book.subject = "Science Fiction"
book.subject ="Adventure"
book.subject = "Fantasy", "Epic"

print(book.metadata)
import html
book.description = html.escape("<p>An epic tale of adventure and fantasy in a science fiction world.</p>")

publish_book(book, "subject.epub")

book = read_book("subject.epub")



print(book.metadata)