import unittest

from pypublib.book import Book
from pypublib.chapter import Chapter
from pypublib.epub import validate_book_resources, validate_metadata


class TestValidateBookResources(unittest.TestCase):
    def setUp(self):
        self.book = Book(metadata={"title": "Test", "creator": "Author"})
        # Chapter with all resources
        chapter1 = Chapter("chapter1.xhtml", "Chapter 1")
        chapter1.content += "<img src='image1.png'/>"
        chapter1.styles = ["style1.css"]
        # Chapter missing resources
        chapter2 = Chapter("chapter2.xhtml", "Chapter 2")
        chapter2.content += "<img src='image2.png'/>"
        chapter2.styles = ["style2.css"]
        self.book.add_chapters(chapter1, chapter2)
        self.book.add_image("image1.png", b"data")
        self.book.add_style("style1.css", "body{}")

    def test_no_missing_resources(self):
        # Check only chapter 1 which has all resources
        self.book.chapters = {"chapter1.xhtml": self.book.chapters["chapter1.xhtml"]}
        result = validate_book_resources(self.book)
        self.assertEqual(result, [])

    def test_missing_image_and_style(self):
        # Check only chapter 2 which is missing resources
        self.book.chapters = {"chapter2.xhtml": self.book.chapters["chapter2.xhtml"]}
        result = validate_book_resources(self.book)
        self.assertEqual(len(result), 1)
        self.assertIn("missing_images", result[0])
        self.assertIn("missing_styles", result[0])
        self.assertIn("image2.png", result[0]["missing_images"])
        self.assertIn("style2.css", result[0]["missing_styles"])

    def test_mixed_chapters(self):
        # Both chapters, only chapter 2 has issues
        self.book.chapters = {
            "kap1.xhtml": self.book.chapters["chapter1.xhtml"],
            "kap2.xhtml": self.book.chapters["chapter2.xhtml"]
        }
        result = validate_book_resources(self.book)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["chapter"], "Chapter 2")

    def test_missing_metadata(self):
        book = Book(metadata={})
        chapter = Chapter("chapter1.xhtml", "Chapter 1")
        book.add_chapters(chapter)
        errors, warnings = validate_metadata(book)
        self.assertTrue(errors)
        self.assertEqual(len(errors), 2)
        self.assertIn("title", errors)
        self.assertIn("creator", errors)


if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()
