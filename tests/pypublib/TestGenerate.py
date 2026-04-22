import unittest
from unittest.mock import patch

from pypublib import epub, Chapter


class TestGenerate(unittest.TestCase):
    @patch("pypublib.epub.os.path.isfile", return_value=True)
    @patch("pypublib.epub.zipfile.is_zipfile", return_value=True)
    @patch("pypublib.epub.extract_epub_content")
    @patch("pypublib.epub.create_book")
    def test_read_book_success(self, mock_create_book, mock_extract, mock_is_zip, mock_is_file):
        mock_extract.return_value = {"metadata": {}, "chapters": {}, "styles": {}, "images": {}, "fonts": {},
                                     "spine": [], "guide": [], "cover": None}
        mock_create_book.return_value = "BookObject"
        result = epub.read_book("dummy.epub")
        self.assertEqual(result, "BookObject")

    def test_create_book(self):
        contents = {
            "metadata": {"title": "Test"},
            "chapters": {"titlepage.html": "<h1>Title</h1>", "chapter1.html": "<h1>Chapter 1</h1>"},
            "styles": {},
            "images": {},
            "fonts": {},
            "spine": [],
            "guide": [],
            "cover": None
        }
        with patch("pypublib.epub.Chapter.from_html",
                   return_value=Chapter.from_content("chapter1.html", "Chapter 1", "<h1>Chapter 1</h1>")):
            book = epub.create_book(contents)
            self.assertEqual(book.metadata["title"], "Test")
            self.assertIn("chapter1.html", book.chapters)
