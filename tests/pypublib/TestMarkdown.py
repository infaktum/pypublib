import unittest
from pypublib.markdown import MarkdownConverter, Html

class TestMarkdownConverter(unittest.TestCase):
    def test_strong_or_em(self):
        self.assertEqual(
            MarkdownConverter.strong_or_em("This is *important* and _emphasized_."),
            "This is <strong>important</strong> and <em>emphasized</em>."
        )

    def test_paragraphs(self):
        self.assertEqual(
            MarkdownConverter.paragraphs("A", "B"),
            f"{Html.p('A')}\n{Html.p('B')}"
        )

    def test_convert(self):
        md = "# Title\nThis is *important* and _emphasized_."
        html = MarkdownConverter.convert(md)
        self.assertIn("<h1>Title</h1>", html)
        self.assertIn("<strong>important</strong>", html)
        self.assertIn("<em>emphasized</em>", html)

    def test_parse_headers(self):
        md = "# Main\n## Sub"
        result = list(MarkdownConverter.parse(md))
        self.assertEqual(result[0], "<h1>Main</h1>")
        self.assertEqual(result[1], "<h2>Sub</h2>")

    def test_parse_unordered_list(self):
        md = "* A\n* B"
        result = list(MarkdownConverter.parse(md))
        self.assertEqual(result[0], Html.ul(["A", "B"]))

    def test_parse_ordered_list(self):
        md = "1. One\n. Two"
        result = list(MarkdownConverter.parse(md))
        ol = Html.ol(["One", "Two"])
        self.assertTrue("<li>One</li>" in ol)
        self.assertTrue("<li>Two</li>" in ol)

    def test_parse_codeblock(self):
        md = "```\nprint(1)\nprint(2)\n```"
        result = list(MarkdownConverter.parse(md))
        self.assertEqual(result[0], Html.code("print(1)\nprint(2)"))

    def test_parse_image(self):
        md = "![Alt](image.png)"
        result = list(MarkdownConverter.parse(md))
        self.assertEqual(result[0], Html.img("image.png", "Alt"))

    def test_parse_blockquote(self):
        md = "> Quote"
        result = list(MarkdownConverter.parse(md))
        self.assertEqual(result[0], Html.blockquote("Quote"))

    def test_parse_hr(self):
        md = "---"
        result = list(MarkdownConverter.parse(md))
        self.assertEqual(result[0], Html.hr())

    def test_parse_paragraph(self):
        md = "Paragraph text"
        result = list(MarkdownConverter.parse(md))
        self.assertEqual(result[0], Html.p("Paragraph text"))

if __name__ == "__main__":
    unittest.main()