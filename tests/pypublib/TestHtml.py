import unittest
from pypublib.markdown import Html

class TestHtml(unittest.TestCase):
    def test_p(self):
        self.assertEqual(Html.p("Text"), "<p>Text</p>")
        self.assertEqual(Html.p("Text", "info"), '<p class="info">Text</p>')

    def test_strong(self):
        self.assertEqual(Html.strong("Important"), "<strong>Important</strong>")

    def test_em(self):
        self.assertEqual(Html.em("Emphasized"), "<em>Emphasized</em>")

    def test_header(self):
        self.assertEqual(Html.header("Title", 2), "<h2>Title</h2>")

    def test_h1_to_h6(self):
        self.assertEqual(Html.h1("A"), "<h1>A</h1>")
        self.assertEqual(Html.h2("B"), "<h2>B</h2>")
        self.assertEqual(Html.h3("C"), "<h3>C</h3>")
        self.assertEqual(Html.h4("D"), "<h4>D</h4>")
        self.assertEqual(Html.h5("E"), "<h5>E</h5>")
        self.assertEqual(Html.h6("F"), "<h6>F</h6>")

    def test_link(self):
        self.assertEqual(Html.link("url", "Text"), '<a href="url">Text</a>')
        self.assertEqual(Html.link("url", "Text", "btn"), '<a href="url" class="btn">Text</a>')

    def test_img(self):
        self.assertEqual(Html.img("image.png"), '<img src="image.png" alt="Image"/>')
        self.assertEqual(Html.img("image.png", "Logo"), '<img src="image.png" alt="Logo"/>')

    def test_ul(self):
        self.assertEqual(Html.ul(["A", "B"]), "<ul>\n  <li>A</li>\n  <li>B</li>\n</ul>")

    def test_ol(self):
        self.assertEqual(Html.ol(["A", "B"]), "<ol>\n  <li>A</li>\n  <li>B</li>\n</ol>")

    def test_blockquote(self):
        self.assertEqual(Html.blockquote("Quote"), "<blockquote>Quote</blockquote>")

    def test_code(self):
        self.assertEqual(Html.code("print(1)"), '<pre><code class="">print(1)\n</code></pre>')
        self.assertEqual(Html.code("print(1)", "python"), '<pre><code class="python">print(1)\n</code></pre>')

    def test_hr(self):
        self.assertEqual(Html.hr(), "<hr/>")

    def test_br(self):
        self.assertEqual(Html.br(), "<br/>")

    def test_nbsp(self):
        self.assertEqual(Html.nbsp(), "&nbsp;")
        self.assertEqual(Html.nbsp(3), "&nbsp;&nbsp;&nbsp;")

    def test_pagebreak(self):
        self.assertEqual(Html.pagebreak(), '<div style="page-break-after: always;"></div>')
        self.assertEqual(Html.pagebreak(5), '<div style="page-break-after: always;"></div>')

if __name__ == "__main__":
    unittest.main()