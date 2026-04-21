import os
import tempfile
import unittest

from pypublib.book import Book
from pypublib.chapter import Chapter

VALID_XHTML = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
  <head>
    <title>Kapitel</title>
    <link rel="stylesheet" type="text/css" href="main.css"/>
  </head>
  <body>
    <p>Hallo</p>
    <img src="cover.jpg"/>
  </body>
</html>
"""


class TestBookAdvanced(unittest.TestCase):
    def test_from_contents_and_chapter_access(self):
        ch = Chapter.from_content("one.xhtml", "One", "<p>1</p>")
        book = Book()
        book.from_contents(
            {
                "metadata": {"title": "Loaded"},
                "chapters": [ch],
                "styles": {"main.css": "body{}"},
                "images": {"a.jpg": b"img"},
                "fonts": {"a.ttf": b"font"},
                "guide": [{"type": "text", "title": "Start", "href": "one.xhtml"}],
            }
        )
        self.assertEqual(book.title, "Loaded")
        self.assertIs(book.get_chapter("one.xhtml"), ch)
        self.assertIsNone(book.get_chapter("missing.xhtml"))

    def test_from_contents_sets_cover(self):
        ch = Chapter.from_content("one.xhtml", "One", "<p>1</p>")
        book = Book()
        book.from_contents({"chapters": [ch], "cover": "cover.jpg"})

        self.assertEqual(book.cover, "cover.jpg")
        self.assertEqual(next(iter(book.chapters.keys())), "Cover.xhtml")

    def test_add_chapter_with_custom_href(self):
        book = Book()
        ch = Chapter.from_content("one.xhtml", "One", "<p>1</p>")
        book.add_chapter(ch, href="custom.xhtml")
        self.assertIn("custom.xhtml", book.chapters)

    def test_add_style_and_image_from_files(self):
        book = Book()
        with tempfile.TemporaryDirectory() as tmpdir:
            css_path = os.path.join(tmpdir, "style.css")
            img_path = os.path.join(tmpdir, "cover.png")
            with open(css_path, "w", encoding="utf-8") as f:
                f.write("body { color: red; }")
            with open(img_path, "wb") as f:
                f.write(b"PNG")

            book.add_style_from_file(css_path)
            book.add_image_from_file(img_path)

        self.assertEqual(book.styles["style.css"], "body { color: red; }")
        self.assertEqual(book.images["cover.png"], b"PNG")

    def test_add_styles_and_add_images_bulk(self):
        book = Book()
        book.add_styles({"a.css": "a{}", "b.css": "b{}"})
        book.add_images({"a.jpg": b"a", "b.jpg": b"b"})
        self.assertIn("a.css", book.styles)
        self.assertIn("b.jpg", book.images)

    def test_cover_handling_and_cover_image(self):
        book = Book({"title": "T", "creator": "A"})
        ch = Chapter.from_content("one.xhtml", "One", "<p>1</p>")
        book.add_chapter(ch)
        book.add_cover("cover.jpg", b"data")

        first_key = next(iter(book.chapters.keys()))
        self.assertEqual(first_key, "Cover.xhtml")
        self.assertEqual(book.cover, "cover.jpg")
        self.assertEqual(book.cover_image, b"data")

    def test_metadata_properties_subject_and_series(self):
        book = Book()
        book.title = " T "
        book.creator = " C "
        book.author = " A "
        book.language = " en "
        book.identifier = " id "
        book.description = " desc "
        book.publisher = " pub "
        book.date = " 2026-01-01 "
        book.subject = " one "
        book.subject = (" two ", " ")
        book.series = (" Series ", 2)
        book.metadata["series"] = []
        book.series = "Part 1"

        self.assertEqual(book.title, "T")
        self.assertEqual(book.creator, "A")
        self.assertEqual(book.author, "A")
        self.assertEqual(book.language, "en")
        self.assertEqual(book.identifier, "id")
        self.assertEqual(book.description, "desc")
        self.assertEqual(book.publisher, "pub")
        self.assertEqual(book.date, "2026-01-01")
        self.assertIn("one", book.subject)
        self.assertIn("two", book.subject)
        self.assertEqual(book.series, ["Part 1"])
        self.assertIn("Part 1", book.metadata["series"])

    def test_set_metadata_nav_ncx_manifest_opf_and_repr(self):
        book = Book()
        chapter = Chapter.from_xhtml("kapitel.xhtml", VALID_XHTML)
        book.add_chapter(chapter)
        book.add_style("main.css", "body{}")
        book.add_image("cover.jpg", b"img")
        book.add_font("main.ttf", b"font")
        book.set_metadata(
            creator="Autor",
            title="Titel",
            language="en",
            identifier="id-1",
            description="desc",
            publisher="pub",
            date="2026",
        )
        book.series = ("Saga", 1)
        book.subject = "fantasy"
        book.guide = [{"type": "text", "title": "Start", "href": "kapitel.xhtml"}]
        book.cover = "cover.jpg"

        nav = book.nav
        ncx = book.ncx
        manifest = book.manifest
        opf = book.opf

        self.assertIn("Table of Contents", nav)
        self.assertIn("kapitel.xhtml", nav)
        self.assertIn("navPoint-1", ncx)
        self.assertTrue(
            any(item.get("properties") == "cover-image" for item in manifest if item["href"] == "cover.jpg"))
        self.assertIn("<dc:title>Titel</dc:title>", opf)
        self.assertIn("<dc:subject>fantasy</dc:subject>", opf)
        self.assertIn('name = "calibre:series"', opf)
        self.assertIn("<guide>", opf)
        self.assertIn("Book(title = Titel", repr(book))


if __name__ == "__main__":
    unittest.main()
