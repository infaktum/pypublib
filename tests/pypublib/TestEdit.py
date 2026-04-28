import os
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from pypublib import epub, edit
from pypublib.book import Book
from pypublib.chapter import Chapter

MINIMAL_OPF = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\">
  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">
    <dc:title>Filesystem Test</dc:title>
    <dc:creator>Tester</dc:creator>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id=\"chapter1\" href=\"chapter1.xhtml\" media-type=\"application/xhtml+xml\"/>
  </manifest>
  <spine>
    <itemref idref=\"chapter1\"/>
  </spine>
</package>
"""

MINIMAL_XHTML = """<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"en\">
  <head><title>Chapter 1</title></head>
  <body><p>Hello EPUB</p></body>
</html>
"""


class TestEdit(unittest.TestCase):

    def test_edit_chapter(self):
        chapter = MagicMock()
        chapter.content = "Hello world"
        edit.edit_chapter(chapter, ["Hello=Hi"])
        self.assertEqual(chapter.content, "Hi world")

    def test_edit_chapter_ignores_invalid_replacement_items(self):
        chapter = MagicMock()
        chapter.content = "Hello world"

        edit.edit_chapter(chapter, ["invalid", "Hello=Hi"])

        self.assertEqual(chapter.content, "Hi world")

    def test_edit_chapters(self):
        chapter1 = MagicMock()
        chapter2 = MagicMock()
        chapter1.content = "A"
        chapter2.content = "B"
        edit.edit_chapters([chapter1, chapter2], ["A=X", "B=Y"])
        self.assertEqual(chapter1.content, "X")
        self.assertEqual(chapter2.content, "Y")

    def test_edit_all_chapters(self):
        book = MagicMock()
        chapter = MagicMock()
        chapter.content = "foo"
        book.chapters = {"c": chapter}
        edit.edit_all_chapters(book, ["foo=bar"])
        self.assertEqual(chapter.content, "bar")

    def test_edit_chapter_tags(self):
        chapter = MagicMock()
        chapter.html = "<p>foo</p>"
        result = edit.edit_chapter_tags(chapter, ["p=foo=bar"])
        self.assertIn("bar", result.html)

    def test_edit_chapter_tag_replaces_attribute_and_text(self):
        chapter = Chapter.from_content(
            "c.xhtml",
            "T",
            "<a href='old-link'>old text</a>",
            [],
        )

        edit.edit_chapter_tag(chapter, "a", "href", "old", "new")
        self.assertIn("href=\"new-link\"", chapter.html)

        edit.edit_chapter_tag(chapter, "a", "text", "old", "new")
        self.assertIn(">new text<", chapter.html)

    def test_edit_chapter_tag_ignores_missing_attribute(self):
        chapter = Chapter.from_content("c.xhtml", "T", "<a>text only</a>", [])

        edit.edit_chapter_tag(chapter, "a", "href", "old", "new")

        self.assertIn("<a>text only</a>", chapter.html)

    def test_collect_used_selectors_reads_html_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "chapter.xhtml")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write('<p class="alpha beta" id="main">Text</p>')

            selectors = edit.collect_used_selectors(tmpdir)

        self.assertIn(".alpha", selectors)
        self.assertIn(".beta", selectors)
        self.assertIn("#main", selectors)

    def test_process_css_file_removes_unused_selectors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            css_path = os.path.join(tmpdir, "style.css")
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(".keep{color:red;}\n.drop{color:blue;}\n")

            removed = edit.process_css_file(css_path, {".keep"})

            with open(css_path, "r", encoding="utf-8") as f:
                content = f.read()

        self.assertIn(".drop", removed)
        self.assertIn(".keep", content)
        self.assertNotIn(".drop", content)

    def test_remove_unused_styles_keeps_and_removes_styles(self):
        book = Book({"title": "A", "creator": "B"})
        book.styles = {"keep.css": "body{}", "drop.css": "p{}"}

        def fake_clean(temp_dir):
            os.remove(os.path.join(temp_dir, "drop.css"))
            with open(os.path.join(temp_dir, "keep.css"), "w", encoding="utf-8") as f:
                f.write("body{color:black;}")

        with patch("pypublib.edit.clean_unused_styles", side_effect=fake_clean):
            result = edit.remove_unused_styles(book)

        self.assertIs(result, book)
        self.assertIn("keep.css", result.styles)
        self.assertEqual(result.styles["keep.css"], "body{color:black;}")
        self.assertNotIn("drop.css", result.styles)

    def test_remove_unnecessary_files_removes_unreferenced_assets(self):
        book = Book({"title": "A", "creator": "B", "language": "en"})
        chapter = Chapter.from_content(
            "chapter1.xhtml",
            "One",
            "<p>x</p><img src='../images/used.png'/>",
            ["styles/used.css"],
        )
        book.add_chapter(chapter)
        book.styles = {"styles/used.css": "body{}", "unused.css": "p{}"}
        book.images = {"images/used.png": b"img", "unused.png": b"img"}

        result = edit.remove_unnecessary_files(book)

        self.assertIs(result, book)
        self.assertEqual(set(result.styles.keys()), {"styles/used.css"})
        self.assertEqual(set(result.images.keys()), {"images/used.png"})

    def test_remove_unnecessary_files_keeps_cover_image(self):
        book = Book({"title": "A", "creator": "B", "language": "en"})
        book.cover = "cover.jpg"
        book.images = {"cover.jpg": b"cover", "unused.png": b"img"}
        book.styles = {"unused.css": "p{}"}

        result = edit.remove_unnecessary_files(book)

        self.assertIs(result, book)
        self.assertEqual(set(result.images.keys()), {"cover.jpg"})
        self.assertEqual(result.styles, {})

    def test_remove_unnecessary_files_matches_styles_by_basename(self):
        book = Book({"title": "A", "creator": "B", "language": "en"})
        chapter = Chapter.from_content("chapter1.xhtml", "One", "<p>x</p>", ["text/main.css"])
        book.add_chapter(chapter)
        book.styles = {"main.css": "body{}", "other.css": "p{}"}

        result = edit.remove_unnecessary_files(book)

        self.assertIs(result, book)
        self.assertEqual(set(result.styles.keys()), {"main.css"})

    def test_pretty_print_xml_returns_input(self):
        xml = "<root><a>1</a></root>"
        self.assertEqual(epub.pretty_print_xml(xml), xml)

    def test_save_book_sanitizes_question_mark_in_href(self):
        book = Book({"title": "Roundtrip", "creator": "Tester", "language": "en"})
        chapter = Chapter.from_content("chapter?1.xhtml", "Chapter 1", "<p>Body</p>")
        book.add_chapter(chapter)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.epub")
            epub.save_book(book, file_path)

            with zipfile.ZipFile(file_path, "r") as archive:
                names = archive.namelist()

        self.assertIn("OEBPS/chapter1.xhtml", names)
        self.assertNotIn("OEBPS/chapter?1.xhtml", names)

    @patch("pypublib.edit.collect_used_selectors", return_value={".used"})
    @patch("pypublib.edit.process_css_file", return_value=[".unused"])
    def test_clean_unused_styles(self, mock_process, mock_collect):
        with patch("pypublib.epub.os.walk", return_value=[("root", [], ["style.css"])]):
            edit.clean_unused_styles("content_dir")
            mock_process.assert_called()


if __name__ == "__main__":
    unittest.main()
