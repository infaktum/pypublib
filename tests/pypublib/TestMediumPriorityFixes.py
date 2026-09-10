import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree

from pypublib import Book, Chapter, Html
from pypublib.book import Opf
from pypublib.epub import read_book, save_book, validate_chapters
from pypublib.markdown import MarkdownConverter


class TestMediumPriorityFixes(unittest.TestCase):
    def book(self):
        return Book({'title': 'Test', 'creator': 'Author', 'language': 'en'})

    def test_custom_chapter_href_is_used_by_export_and_navigation(self):
        book = self.book()
        chapter = Chapter.from_content('old.xhtml', 'One', '<p>Text</p>')
        book.add_chapter(chapter, 'new.xhtml')
        self.assertEqual(chapter.href, 'new.xhtml')
        self.assertEqual(list(book.chapters), ['new.xhtml'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'book.epub'
            save_book(book, path)
            with zipfile.ZipFile(path) as archive:
                self.assertIn('OEBPS/new.xhtml', archive.namelist())
                self.assertNotIn('OEBPS/old.xhtml', archive.namelist())
                for document in ('content.opf', 'nav.xhtml', 'toc.ncx'):
                    xml = etree.fromstring(archive.read('OEBPS/' + document))
                    refs = xml.xpath('//@href | //@src')
                    self.assertIn('new.xhtml', refs)
                    self.assertNotIn('old.xhtml', refs)
            self.assertIn('new.xhtml', read_book(str(path)).chapters)
        book.remove_chapter(chapter)
        self.assertFalse(book.chapters)

    def test_readding_chapter_with_new_href_does_not_duplicate_it(self):
        book = self.book()
        chapter = Chapter.from_content('old.xhtml', 'One', '<p>Text</p>')
        book.add_chapter(chapter)
        book.add_chapter(chapter, 'new.xhtml')
        self.assertEqual(list(book.chapters), ['new.xhtml'])

    def test_imported_chapter_custom_href_preserves_rename_tracking(self):
        book = self.book()
        book.add_chapter(Chapter.from_content('old.xhtml', 'One', '<p>Text</p>'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'book.epub'
            save_book(book, path)
            imported = read_book(str(path))
            chapter = imported.chapters['old.xhtml']
            imported.add_chapter(chapter, 'new.xhtml')
            save_book(imported, path)
            with zipfile.ZipFile(path) as archive:
                self.assertIn('OEBPS/new.xhtml', archive.namelist())
                self.assertNotIn('OEBPS/old.xhtml', archive.namelist())
                nav = etree.fromstring(archive.read('OEBPS/nav.xhtml'))
                self.assertIn('new.xhtml', nav.xpath('//@href'))

    def test_validation_accepts_real_chapters_and_rejects_empty_or_invalid_content(self):
        book = self.book()
        chapter = Chapter.from_content('one.xhtml', 'One', '<p>Text</p>')
        book.add_chapter(chapter)
        validate_chapters(book)
        for title, content in (('', '<p>Text</p>'), ('   ', '<p>Text</p>'), ('One', ''),
                               ('One', ' \n '), ('One', '<p>broken')):
            with self.subTest(title=title, content=content):
                chapter.title = title
                chapter.content = content
                with self.assertRaises(ValueError):
                    validate_chapters(book)

    def test_opf_from_file_honors_xml_encoding_declarations(self):
        book = self.book()
        book.title = 'Gr\u00fc\u00dfe'
        xml = book.opf
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'content.opf'
            for encoding in ('utf-8', 'iso-8859-1', 'utf-16'):
                with self.subTest(encoding=encoding):
                    path.write_bytes(xml.replace("encoding='utf-8'", f"encoding='{encoding}'").encode(encoding))
                    self.assertEqual(Opf.from_file(str(path)).metadata['title'], book.title)

    def test_series_assignment_is_a_scalar_and_can_be_repeated(self):
        book = self.book()
        book.series = ' First '
        self.assertEqual(book.series, 'First')
        book.series = (' Second ', 2)
        book.series = ' Third '
        self.assertEqual(book.series, 'Third')
        self.assertEqual(book.metadata['series_index'], 2)

    def test_replacing_cover_updates_chapter_image_and_roundtrip(self):
        book = self.book()
        book.add_chapter(Chapter.from_content('one.xhtml', 'One', '<p>Text</p>'))
        book.add_cover('first.png', b'first')
        book.add_cover('second.png', b'second')
        self.assertEqual(list(book.chapters), ['Cover.xhtml', 'one.xhtml'])
        self.assertEqual(book.chapters['Cover.xhtml'].images, ['second.png'])
        self.assertEqual(book.cover_image, b'second')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'book.epub'
            save_book(book, path)
            imported = read_book(str(path))
            self.assertEqual(imported.cover, 'second.png')
            self.assertEqual(imported.chapters['Cover.xhtml'].images, ['second.png'])

    def test_html_attributes_code_and_spaces_are_valid_xhtml(self):
        value = 'a&b<test>"quoted"\'single\''
        code = 'if a < b and x & y:\n    print("<em>my_variable_name</em>")'
        fragment = (Html.p(Html.strong('nested'), value) + Html.link(value, 'link', value)
                    + Html.img(value, value) + Html.code(code, value) + Html.nbsp(2))
        chapter = Chapter.from_content('one.xhtml', 'One', fragment)
        root = etree.fromstring(chapter.html.encode())
        ns = {'x': 'http://www.w3.org/1999/xhtml'}
        self.assertEqual(root.find('.//x:p', ns).get('class'), value)
        self.assertIsNotNone(root.find('.//x:p/x:strong', ns))
        self.assertEqual(root.find('.//x:a', ns).get('href'), value)
        self.assertEqual(root.find('.//x:img', ns).get('alt'), value)
        self.assertEqual(root.find('.//x:code', ns).text, code + '\n')
        self.assertEqual(root.find('.//x:code', ns).get('class'), value)
        self.assertTrue(''.join(root.itertext()).endswith('\u00a0\u00a0'))

    def test_markdown_emphasis_does_not_change_code_or_attributes(self):
        code = 'my_variable_name = "*literal*"\nif a < b: pass'
        markdown = ('# A & B\n*bold* and _italic_\n\n```python\n' + code
                    + '\n```\n\n![a_b_c](my_image_name.png)')
        result = MarkdownConverter.convert(markdown)
        root = etree.fromstring(('<root>' + result + '</root>').encode())
        self.assertEqual(root.find('pre/code').text, code + '\n')
        self.assertEqual(root.find('pre/code').get('class'), 'python')
        self.assertEqual(root.find('img').get('src'), 'my_image_name.png')
        self.assertEqual(root.find('img').get('alt'), 'a_b_c')
        self.assertEqual(root.find('h1').text, 'A & B')
        self.assertEqual(root.find('p/strong').text, 'bold')
        self.assertEqual(root.find('p/em').text, 'italic')
