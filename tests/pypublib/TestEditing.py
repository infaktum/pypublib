import unittest

from lxml import html as lhtml

from pypublib.book import Book
from pypublib.chapter import Chapter
from pypublib.epub import edit_chapter, edit_all_chapters

TEST_CONTENT = """
    <p>Das ist ein Test. Test ist wichtig.</p>
    <img src="image1.png" alt="Bild 1"/>
    <img src="image2.png" alt="Bild 2"/>
"""


class TestEditChapter(unittest.TestCase):
    def test_edit_chapter(self):
        chapter = Chapter.from_content("test.xhtml", "Test", TEST_CONTENT, [])
        replacements = ["Test=Beispiel", "wichtig=notwendig"]
        edit_chapter(chapter, replacements)
        p = lhtml.fromstring(chapter.content).find(".//p")
        self.assertIsNotNone(p)
        self.assertEqual(p.text, "Das ist ein Beispiel. Beispiel ist notwendig.")


class TestEditBook(unittest.TestCase):
    def test_edit_chapter(self):
        book = Book()
        chapter1 = Chapter.from_content("test1.xhtml", "Test", TEST_CONTENT, [])
        chapter2 = Chapter.from_content("test2.xhtml", "Test", TEST_CONTENT, [])
        book.add_chapters(chapter1, chapter2)
        replacements = ["Test=Beispiel", "wichtig=notwendig"]
        edit_all_chapters(book, replacements)
        for chapter in [chapter1, chapter2]:
            p = lhtml.fromstring(chapter.content).find(".//p")
            self.assertIsNotNone(p)
            self.assertEqual(p.text, "Das ist ein Beispiel. Beispiel ist notwendig.")


if __name__ == '__main__':
    unittest.main()
