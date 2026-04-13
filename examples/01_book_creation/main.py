
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pypublib.epub import publish_book
from string import Template
from pypublib.book import Book, Chapter


def main():
    """
    Create a simple book with metadata, chapters, styles, and a cover, then publish it as an EPUB file.
    1. Create a new Book instance.
    2. Set metadata such as author, title, language, identifier, description, publisher, date, and series.
    3. Create an introduction chapter and add it to the book.
    4. Generate multiple chapters using a template and add them to the book.
    5. Modify the content of a specific chapter and add an epilogue chapter.
    6. Add styles to the book, both from a string and from an external file.
    7. Add a cover image to the book.
    8. Publish the book as an EPUB file.
    9. Print out various stages of the book creation process for verification.
    10. Ensure the script runs the main function when executed directly.
    """

    book = Book()
    print(f'New book created: {book}')

    book.author = "Monty Python"
    book.title = "The Adventures of Monty Python"
    book.language = "en"
    book.identifier = "urn:isbn:9876543210"
    book.description = "A thrilling adventure of a programming language."
    book.publisher = "Pythonic Press"
    book.date = "2024-10-01"
    book.series = "Python Series", 1

    print(f'Metadata: {book.metadata}')

    introduction = Chapter.from_content('Introduction.xhtml', 'Introduction',
        "<h1>Introduction</h1><p>Once upon a time, the brave young programmer Monty Python leaves his hometown.</p>", styles=["styles.css"])

    book.add_chapters(introduction)
    introduction.add_style("intro_style.css")
    template = Template(f"""
        <h1>Chapter $i</h1>
        <p>The $i. adventure of our brave Monty.</p>
    """)
    chapters = [ Chapter.from_content(f"Chapter_{n}.xhtml", f"Chapter {n}", template.substitute(i=n),
                                      styles=["styles.css"]) for n in range(1, 6)]
    book.add_chapters(*chapters)

    chapter5 = book.get_chapter("Chapter_5.xhtml")
    chapter5.content += '<p>Being the last adventure of Monty, because he had gained enough treasures to return home to his mom.</p>'
    print(f'Added text to chapter 5: {chapter5.content}')
    last_chapter = Chapter.from_content("Epilogue.xhtml", "Epilogue",
                "<h1>Epilogue</h1><p>And they all lived happily ever after.</p>",styles=["styles.css"])
    book.add_chapter(last_chapter)

    print(f'Chapter added: {book.chapters.keys()}')


    book.add_style("body_styles.css", "body { font-family: Arial, sans-serif; }")
    book.add_style_from_file("styles.css")

    print(f'Styles added: {list(book.styles.keys())}')

    with open("Cover.jpg", "rb") as cover_file:
        book.add_cover("cover.jpg", cover_file.read())

    print(f'Cover added: {book.cover}')

    print(f'Created book {book}')

    publish_book(book, "The_Adventures_of_Monty_Python.epub")


#-------------------------------

if __name__ == "__main__":
    main()
