
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pypublib.epub import publish_book, read_book


def main():
    book = read_book("AliceInWonderland.epub")
    print(f'Read {book}')
    publish_book(book, "ParsedBook.epub")

#-------------------------------------------

if __name__ == "__main__":
    main()
