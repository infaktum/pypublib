import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pypublib.markdown import  Html
from pypublib.book import Book, Chapter
from pypublib.epub import validate_book

def main():

    book = Book()
    book.title = "The Book of Errors"

    chapter1 = Chapter("Chapter1.xhtml", "Chapter 1")
    chapter2 = Chapter("Chapter2.xhtml", "Chapter with missing stylesheet")
    chapter3 = Chapter("Chapter3.xhtml", "Chapter with missing image")

    book.add_chapters(chapter1, chapter2, chapter3)


    chapter2.add_style("missing.css")
    chapter3.content += Html.img("missing.png")

    problems = validate_book(book)
    if problems is None or len(problems) == 0:
        print("The book has been validated successfully, no problems found.")
    else:
        print("Following problems found:")
        for problem in problems:
            print(problem)



if __name__ ==   "__main__":
    main()
