import os
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from pypublib import epub
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


class TestEpub(unittest.TestCase):
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
            "chapters": {"chapter1.html": "<h1>Chapter 1</h1>"},
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

    @patch("pypublib.epub.zipfile.ZipFile")
    def test_extract_epub_content(self, mock_zip):
        mock_zip.return_value.__enter__.return_value.namelist.return_value = ["OEBPS/content.opf",
                                                                              "OEBPS/chapter1.xhtml", "OEBPS/style.css"]
        mock_zip.return_value.__enter__.return_value.read.side_effect = lambda name: b"<xml/>" if name.endswith(
            "content.opf") else b"chapter" if name.endswith(".xhtml") else b"css"
        result = epub.extract_epub_content("dummy.epub")
        self.assertIn("chapters", result)
        self.assertIn("styles", result)
        self.assertIn("metadata", result)

    @patch("pypublib.epub.save_book")
    def test_publish_book(self, mock_save):
        book = MagicMock()
        epub.publish_book(book, "output.epub")
        mock_save.assert_called_once_with(book, "output.epub")

    def test_read_book_missing_file_returns_none(self):
        result = epub.read_book("definitely_missing_file.epub")
        self.assertIsNone(result)

    def test_read_book_invalid_path_returns_none(self):
        self.assertIsNone(epub.read_book("   "))
        self.assertIsNone(epub.read_book(None))

    @patch("pypublib.epub.os.path.isfile", return_value=True)
    @patch("pypublib.epub.zipfile.is_zipfile", return_value=True)
    @patch("pypublib.epub.extract_epub_content", side_effect=zipfile.BadZipFile("bad"))
    def test_read_book_handles_bad_zip_exception(self, _extract, _is_zip, _is_file):
        self.assertIsNone(epub.read_book("broken.epub"))

    @patch("pypublib.epub.os.path.isfile", return_value=True)
    @patch("pypublib.epub.zipfile.is_zipfile", return_value=True)
    @patch("pypublib.epub.extract_epub_content", side_effect=UnicodeDecodeError("utf-8", b"x", 0, 1, "bad"))
    def test_read_book_handles_decode_exception(self, _extract, _is_zip, _is_file):
        self.assertIsNone(epub.read_book("broken.epub"))

    @patch("pypublib.epub.os.path.isfile", return_value=True)
    @patch("pypublib.epub.zipfile.is_zipfile", return_value=True)
    @patch("pypublib.epub.extract_epub_content", side_effect=KeyError("missing"))
    def test_read_book_handles_key_error(self, _extract, _is_zip, _is_file):
        self.assertIsNone(epub.read_book("broken.epub"))

    @patch("pypublib.epub.os.path.isfile", return_value=True)
    @patch("pypublib.epub.zipfile.is_zipfile", return_value=True)
    @patch("pypublib.epub.extract_epub_content", side_effect=PermissionError("denied"))
    def test_read_book_handles_permission_error(self, _extract, _is_zip, _is_file):
        self.assertIsNone(epub.read_book("broken.epub"))

    @patch("pypublib.epub.os.path.isfile", return_value=True)
    @patch("pypublib.epub.zipfile.is_zipfile", return_value=True)
    @patch("pypublib.epub.extract_epub_content", side_effect=RuntimeError("unexpected"))
    def test_read_book_handles_generic_exception(self, _extract, _is_zip, _is_file):
        self.assertIsNone(epub.read_book("broken.epub"))

    def test_read_book_non_zip_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "not_an_epub.epub")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("plain text")
            result = epub.read_book(file_path)
        self.assertIsNone(result)

    def test_extract_epub_content_reads_real_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "sample.epub")
            with zipfile.ZipFile(file_path, "w") as archive:
                archive.writestr("OEBPS/content.opf", MINIMAL_OPF)
                archive.writestr("OEBPS/chapter1.xhtml", MINIMAL_XHTML)
                archive.writestr("OEBPS/style.css", "body { color: black; }")
                archive.writestr("OEBPS/picture.png", b"png-data")
                archive.writestr("OEBPS/font.ttf", b"font-data")

            contents = epub.extract_epub_content(file_path)

        self.assertIn("chapter1.xhtml", contents["chapters"])
        self.assertIn("style.css", contents["styles"])
        self.assertIn("picture.png", contents["images"])
        self.assertIn("font.ttf", contents["fonts"])
        self.assertEqual(contents["metadata"].get("title"), "Filesystem Test")
        self.assertIn("chapter1", contents["spine"])

    def test_extract_epub_content_without_opf_uses_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "sample.epub")
            with zipfile.ZipFile(file_path, "w") as archive:
                archive.writestr("OEBPS/chapter1.html", "<html><body>Hi</body></html>")
                archive.writestr("OEBPS/image.svg", b"svg-data")
                archive.writestr("OEBPS/font.woff2", b"font-data")

            contents = epub.extract_epub_content(file_path)

        self.assertEqual(contents["metadata"], {})
        self.assertEqual(contents["spine"], [])
        self.assertEqual(contents["guide"], [])
        self.assertIsNone(contents["cover"])
        self.assertIn("chapter1.html", contents["chapters"])
        self.assertIn("image.svg", contents["images"])
        self.assertIn("font.woff2", contents["fonts"])

    def test_save_book_writes_valid_epub_archive(self):
        book = Book({"title": "Roundtrip", "creator": "Tester", "language": "en"})
        chapter = Chapter.from_content("chapter1.xhtml", "Chapter 1", "<p>Body</p>")
        chapter.add_style("style.css")
        book.add_chapter(chapter)
        book.add_style("style.css", "body { color: black; }")
        book.add_image("picture.png", b"png-data")
        book.add_font("font.ttf", b"font-data")

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "output.epub")
            epub.save_book(book, file_path)

            with zipfile.ZipFile(file_path, "r") as archive:
                names = archive.namelist()
                infos = archive.infolist()

        self.assertEqual(infos[0].filename, "mimetype")
        self.assertEqual(infos[0].compress_type, zipfile.ZIP_STORED)
        self.assertIn("META-INF/container.xml", names)
        self.assertIn("OEBPS/content.opf", names)
        self.assertIn("OEBPS/nav.xhtml", names)
        self.assertIn("OEBPS/toc.ncx", names)
        self.assertIn("OEBPS/chapter1.xhtml", names)

    def test_publish_and_read_roundtrip(self):
        book = Book({"title": "Roundtrip", "creator": "Tester", "language": "en"})
        chapter = Chapter.from_content("chapter1.xhtml", "Chapter 1", "<p>Hello</p>")
        book.add_chapter(chapter)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "roundtrip.epub")
            epub.publish_book(book, file_path)
            loaded = epub.read_book(file_path)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.metadata.get("title"), "Roundtrip")
        self.assertIn("chapter1.xhtml", loaded.chapters)

    def test_create_book_sets_cover(self):
        contents = {
            "metadata": {"title": "Test"},
            "chapters": {"chapter1.xhtml": MINIMAL_XHTML},
            "styles": {},
            "images": {},
            "fonts": {},
            "spine": [],
            "guide": [],
            "cover": "cover.jpg",
        }
        book = epub.create_book(contents)
        self.assertEqual(book.cover, "cover.jpg")

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

    def test_validate_book_detects_duplicate_href(self):
        book = Book({"title": "A", "creator": "B"})
        chapter1 = Chapter.from_content("chapter1.xhtml", "One", "<p>1</p>")
        chapter2 = Chapter.from_content("chapter2.xhtml", "Two", "<p>2</p>")
        chapter2.href = "chapter1.xhtml"
        book.chapters = {"c1": chapter1, "c2": chapter2}
        issues = epub.validate_book(book)
        self.assertTrue(any("Duplicate chapter href" in issue for issue in issues))

    def test_validate_book_detects_missing_title_and_href(self):
        book = Book({"title": "A", "creator": "B"})
        chapter = Chapter.from_content("chapter1.xhtml", "Title", "<p>1</p>")
        chapter._title = ""
        chapter.href = ""
        book.chapters = {"c1": chapter}
        issues = epub.validate_book(book)
        self.assertTrue(any("missing a title" in issue for issue in issues))
        self.assertTrue(any("missing an href" in issue for issue in issues))

    def test_validate_book_resources_reports_missing_assets(self):
        book = Book({"title": "A", "creator": "B", "language": "en"})
        chapter = Chapter.from_content("chapter1.xhtml", "One", "<img src='missing.png'/><p>x</p>")
        chapter.add_style("missing.css")
        book.add_chapter(chapter)

        issues = epub.validate_book_resources(book)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["chapter"], "One")
        self.assertIn("missing.png", issues[0]["missing_images"])
        self.assertIn("missing.css", issues[0]["missing_styles"])

    def test_validate_chapters_missing_data_raises(self):
        chapter = SimpleNamespace(title="", html="")
        book = SimpleNamespace(chapters=[chapter])
        with self.assertRaises(ValueError):
            epub.validate_chapters(book)

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

    def test_edit_chapter_tag_replaces_attribute_and_text(self):
        chapter = Chapter.from_content(
            "c.xhtml",
            "T",
            "<a href='old-link'>old text</a>",
            [],
        )

        epub.edit_chapter_tag(chapter, "a", "href", "old", "new")
        self.assertIn("href=\"new-link\"", chapter.html)

        epub.edit_chapter_tag(chapter, "a", "text", "old", "new")
        self.assertIn(">new text<", chapter.html)

    def test_collect_used_selectors_reads_html_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "chapter.xhtml")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write('<p class="alpha beta" id="main">Text</p>')

            selectors = epub.collect_used_selectors(tmpdir)

        self.assertIn(".alpha", selectors)
        self.assertIn(".beta", selectors)
        self.assertIn("#main", selectors)

    def test_process_css_file_removes_unused_selectors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            css_path = os.path.join(tmpdir, "style.css")
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(".keep{color:red;}\n.drop{color:blue;}\n")

            removed = epub.process_css_file(css_path, {".keep"})

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

        with patch("pypublib.epub.clean_unused_styles", side_effect=fake_clean):
            result = epub.remove_unused_styles(book)

        self.assertIs(result, book)
        self.assertIn("keep.css", result.styles)
        self.assertEqual(result.styles["keep.css"], "body{color:black;}")
        self.assertNotIn("drop.css", result.styles)

    def test_remove_unused_styles_cleans_nested_temp_dirs(self):
        book = Book({"title": "A", "creator": "B"})
        book.styles = {"keep.css": "body{}"}
        paths = {}

        def fake_clean(temp_dir):
            nested = os.path.join(temp_dir, "nested")
            os.makedirs(nested, exist_ok=True)
            with open(os.path.join(nested, "temp.txt"), "w", encoding="utf-8") as f:
                f.write("tmp")
            paths["nested"] = nested

        with patch("pypublib.epub.clean_unused_styles", side_effect=fake_clean):
            result = epub.remove_unused_styles(book)

        self.assertIs(result, book)
        self.assertFalse(os.path.exists(paths["nested"]))

    def test_pretty_print_xml_returns_input(self):
        xml = "<root><a>1</a></root>"
        self.assertEqual(epub.pretty_print_xml(xml), xml)

    @patch("pypublib.epub.collect_used_selectors", return_value={".used"})
    @patch("pypublib.epub.process_css_file", return_value=[".unused"])
    def test_clean_unused_styles(self, mock_process, mock_collect):
        with patch("pypublib.epub.os.walk", return_value=[("root", [], ["style.css"])]):
            epub.clean_unused_styles("content_dir")
            mock_process.assert_called()


if __name__ == "__main__":
    unittest.main()
