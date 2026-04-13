import unittest

from pypublib.book import Chapter

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


if __name__ == '__main__':
    unittest.main()



