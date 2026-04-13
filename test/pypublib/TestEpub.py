import unittest
from unittest.mock import patch, MagicMock
from pypublib import epub
from pypublib.book import Book, Chapter

class TestEpub(unittest.TestCase):
    @patch("pypublib.epub.os.path.isfile", return_value=True)
    @patch("pypublib.epub.zipfile.is_zipfile", return_value=True)
    @patch("pypublib.epub.extract_epub_content")
    @patch("pypublib.epub.create_book")
    def test_read_book_success(self, mock_create_book, mock_extract, mock_is_zip, mock_is_file):
        mock_extract.return_value = {"metadata": {}, "chapters": {}, "styles": {}, "images": {}, "fonts": {}, "spine": [], "guide": [], "cover": None}
        mock_create_book.return_value = "BookObject"
        result = epub.read_book("dummy.epub")
        self.assertEqual(result, "BookObject")

    def test_create_book(self):
        contents = {
            "metadata": {"title": "Test"},
            "chapters": {"chapter1.html": "<h1>Chapter 1</h1>"},
            "styles": {},
            "images": {},
            "fonts": {},
            "spine": [],
            "guide": [],
            "cover": None
        }
        with patch("pypublib.epub.Chapter.from_html", return_value=Chapter.from_content("chapter1.html", "Chapter 1","<h1>Chapter 1</h1>")):
            book = epub.create_book(contents)
            self.assertEqual(book.metadata["title"], "Test")
            self.assertIn("chapter1.html", book.chapters)

    @patch("pypublib.epub.zipfile.ZipFile")
    def test_extract_epub_content(self, mock_zip):
        mock_zip.return_value.__enter__.return_value.namelist.return_value = ["OEBPS/content.opf", "OEBPS/chapter1.xhtml", "OEBPS/style.css"]
        mock_zip.return_value.__enter__.return_value.read.side_effect = lambda name: b"<xml/>" if name.endswith("content.opf") else b"chapter" if name.endswith(".xhtml") else b"css"
        result = epub.extract_epub_content("dummy.epub")
        self.assertIn("chapters", result)
        self.assertIn("styles", result)
        self.assertIn("metadata", result)

    @patch("pypublib.epub.save_book")
    def test_publish_book(self, mock_save):
        book = MagicMock()
        epub.publish_book(book, "output.epub")
        mock_save.assert_called_once_with(book, "output.epub")



    def test_validate_metadata(self):
        book = MagicMock()
        book.metadata = {"title": "A"}
        missing_mandatory, missing_optional = epub.validate_metadata(book)
        self.assertIn("creator", missing_mandatory)
        self.assertIn("language", missing_optional)

    def test_validate_book(self):
        book = MagicMock()
        book.chapters = {}
        book.metadata = {}
        book.images = {}
        book.styles = {}
        issues = epub.validate_book(book)
        self.assertTrue(any("no chapters" in issue for issue in issues))

    def test_edit_chapter(self):
        chapter = MagicMock()
        chapter.content = "Hello world"
        epub.edit_chapter(chapter, ["Hello=Hi"])
        self.assertEqual(chapter.content, "Hi world")

    def test_edit_chapters(self):
        chapter1 = MagicMock()
        chapter2 = MagicMock()
        chapter1.content = "A"
        chapter2.content = "B"
        epub.edit_chapters([chapter1, chapter2], ["A=X", "B=Y"])
        self.assertEqual(chapter1.content, "X")
        self.assertEqual(chapter2.content, "Y")

    def test_edit_all_chapters(self):
        book = MagicMock()
        chapter = MagicMock()
        chapter.content = "foo"
        book.chapters = {"c": chapter}
        epub.edit_all_chapters(book, ["foo=bar"])
        self.assertEqual(chapter.content, "bar")



    def test_edit_chapter_tags(self):
        chapter = MagicMock()
        chapter.html = "<p>foo</p>"
        result = epub.edit_chapter_tags(chapter, ["p=foo=bar"])
        self.assertIn("bar", result.html)

    @patch("pypublib.epub.collect_used_selectors", return_value={".used"})
    @patch("pypublib.epub.process_css_file", return_value=[".unused"])
    def test_clean_unused_styles(self, mock_process, mock_collect):
        with patch("pypublib.epub.os.walk", return_value=[("root", [], ["style.css"])]):
            epub.clean_unused_styles("content_dir")
            mock_process.assert_called()



if __name__ == "__main__":
    unittest.main()