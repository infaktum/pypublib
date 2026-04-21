import unittest
from unittest.mock import patch

from lxml import etree

from pypublib.chapter import Chapter


class TestChapter(unittest.TestCase):

    def test_init_sets_attributes(self):
        ch = Chapter.from_content("test.xhtml", "Titel", "<html><body>Inhalt</body></html>", ["style.css"])
        self.assertEqual(ch.href, "test.xhtml")
        self.assertEqual(ch.title, "Titel")
        self.assertIn("Inhalt", ch.html)
        self.assertEqual(ch.styles, ["style.css"])

    def test_from_html_extracts_title_and_stylesheets(self):
        html = """
        <html xmlns="http://www.w3.org/1999/xhtml">
          <head>
            <title>Kapitel 1</title>
            <link rel="stylesheet" type="text/css" href="main.css"/>
          </head>
          <body>Text</body>
        </html>
        """
        ch = Chapter.from_xhtml("kap1.xhtml", html)
        self.assertEqual(ch.title, "Kapitel 1")
        self.assertEqual(ch.styles, ["main.css"])

    def test_from_content_removes_body_tags(self):
        html = "<body>Testinhalt</body>"
        ch = Chapter.from_content("test.xhtml", "Titel", html)
        self.assertNotIn("<body><body>", ch.html)
        self.assertNotIn("</body></body>", ch.html)
        self.assertIn("Testinhalt", ch.html)

    def test_title_setter_and_getter(self):
        ch = Chapter.from_content("test.xhtml", "Alter Titel", "<html>Inhalt</html>", [])
        self.assertEqual(ch.title, "Alter Titel")
        self.assertEqual(ch.href, "test.xhtml")
        ch.title = "Neuer Titel"
        self.assertEqual(ch.title, "Neuer Titel")
        self.assertEqual(ch.href, "Neuer Titel.xhtml")

    def test_from_xhtml_invalid_raises_xml_syntax_error(self):
        with self.assertRaises(etree.XMLSyntaxError):
            Chapter.from_xhtml("broken.xhtml", "<html><body><p>broken")

    def test_from_html_parses_title_styles_and_body(self):
        html = """<?xml version='1.0'?>
        <html><head><title>T</title><link rel='stylesheet' href='a.css'/></head>
        <body><p>X</p></body></html>"""
        chapter = Chapter.from_html("c.xhtml", html)
        self.assertEqual(chapter.title, "T")
        self.assertEqual(chapter.styles, ["a.css"])
        self.assertIn("<p>X</p>", chapter.content)

    def test_from_cover_and_images_and_repr(self):
        chapter = Chapter.from_cover("cover.jpg")
        self.assertEqual(chapter.href, "Cover.xhtml")
        self.assertIn("cover.jpg", chapter.images)
        self.assertIn("Chapter(", repr(chapter))

    def test_str_includes_key_chapter_information(self):
        chapter = Chapter.from_content(
            "kap1.xhtml",
            "Kapitel 1",
            "<p>Text</p><img src='img1.png'/>",
            ["base.css", "theme.css"],
        )

        output = str(chapter)

        self.assertIn("Chapter", output)
        self.assertIn("title       : Kapitel 1", output)
        self.assertIn("href        : kap1.xhtml", output)
        self.assertIn("styles      : 2 (base.css, theme.css)", output)
        self.assertIn("images      : 1 (img1.png)", output)
        self.assertIn("content_len :", output)

    def test_str_handles_missing_styles_and_images(self):
        chapter = Chapter.from_content("empty.xhtml", "", "")

        output = str(chapter)

        self.assertIn("title       : -", output)
        self.assertIn("styles      : 0 (-)", output)
        self.assertIn("images      : 0 (-)", output)

    def test_add_style_avoids_duplicates(self):
        chapter = Chapter.from_content("c.xhtml", "T", "<p>x</p>")
        chapter.add_style("main.css")
        chapter.add_style("main.css")
        self.assertEqual(chapter.styles, ["main.css"])

    def test_from_xhtml_wraps_parser_error_as_value_error(self):
        with patch("pypublib.book.etree.fromstring", side_effect=etree.ParserError("bad")):
            with self.assertRaises(ValueError):
                Chapter.from_xhtml("broken.xhtml", "<html/>")


if __name__ == '__main__':
    unittest.main()
