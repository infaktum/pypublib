import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree

from pypublib.book import Book
from pypublib.chapter import Chapter
from pypublib.epub import read_book, save_book


class TestXmlEscaping(unittest.TestCase):
    def setUp(self):
        self.text = 'A & B <C> "quoted" \'apostrophe\' – $manifest_items'
        self.href = 'chapter&"quoted".xhtml'
        self.chapter = Chapter.from_content(
            self.href, self.text,
            'Before <p>A &amp; B <em>nested</em> tail<br/></p> after',
            ['style&"quoted".css'],
        )
        self.book = Book({'title': self.text, 'creator': self.text, 'language': 'en'})
        self.book.add_chapter(self.chapter)

    def parse(self, xml):
        return etree.fromstring(xml.encode('utf-8'))

    def test_opf_preserves_metadata_attributes_and_references(self):
        self.book.subject = self.text
        self.book.series = (self.text, 2)
        self.book.add_metadata(self.text, self.text)
        self.book.guide = [{'type': 'text', 'title': self.text, 'href': self.href}]
        root = self.parse(self.book.opf)
        ns = {'o': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}
        self.assertEqual(root.findtext('o:metadata/dc:title', namespaces=ns), self.text)
        self.assertEqual(root.findtext('o:metadata/dc:creator', namespaces=ns), self.text)
        self.assertEqual(root.findtext('o:metadata/dc:subject', namespaces=ns), self.text)
        metadata = {item.get('name'): item.get('content') for item in root.findall('o:metadata/o:meta', ns)}
        self.assertEqual(metadata[self.text], self.text)
        self.assertEqual(metadata['calibre:series'], self.text)
        self.assertEqual(metadata['calibre:series_index'], '2')
        item = root.find('o:manifest/o:item', ns)
        self.assertEqual(item.get('href'), self.href)
        self.assertEqual(root.findall('o:spine/o:itemref', ns)[1].get('idref'), item.get('id'))
        reference = root.find('o:guide/o:reference', ns)
        self.assertEqual(reference.get('title'), self.text)
        self.assertEqual(reference.get('href'), self.href)

    def test_navigation_preserves_titles_and_links(self):
        root = self.parse(self.book.nav)
        ns = {'x': 'http://www.w3.org/1999/xhtml'}
        link = root.find('.//x:nav[@id="toc"]/x:ol/x:li/x:a', ns)
        self.assertEqual(link.text, self.text)
        self.assertEqual(link.get('href'), self.href)
        self.book.uid = self.text
        root = self.parse(self.book.ncx)
        ns = {'n': 'http://www.daisy.org/z3986/2005/ncx/'}
        self.assertEqual(root.find('n:head/n:meta', ns).get('content'), self.text)
        self.assertEqual(root.findtext('.//n:navLabel/n:text', namespaces=ns), self.text)
        self.assertEqual(root.find('.//n:content', ns).get('src'), self.href)

    def test_chapter_preserves_markup_and_escapes_head_values(self):
        root = self.parse(self.chapter.html)
        ns = {'x': 'http://www.w3.org/1999/xhtml'}
        self.assertEqual(root.findtext('x:head/x:title', namespaces=ns), self.text)
        self.assertEqual(root.find('x:head/x:link', ns).get('href'), self.chapter.styles[0])
        body = root.find('x:body', ns)
        self.assertEqual(''.join(body.itertext()), 'Before A & B nested tail after')
        self.assertIsNotNone(body.find('x:p/x:em', ns))
        self.assertIsNotNone(body.find('x:p/x:br', ns))
        parsed = Chapter.from_xhtml(self.href, self.chapter.html)
        self.assertEqual(parsed.title, self.text)
        self.assertEqual(parsed.styles, self.chapter.styles)
        self.parse(parsed.html)

    def test_cover_escapes_image_path(self):
        name = 'cover&"quoted".jpg'
        chapter = Chapter.from_cover(name)
        self.assertEqual(chapter.images, [name])

    def test_html_input_serializes_void_elements_as_xml(self):
        chapter = Chapter.from_html('one.xhtml', '<html><head><title>A &amp; B</title></head>'
                                    '<body><p>A<br>B<img src="pic.png"></p></body></html>')
        self.parse(chapter.html)
        self.assertEqual(chapter.images, ['pic.png'])

    def test_saved_epub_xml_parses_and_metadata_roundtrips(self):
        # Use filesystem-safe names for this integration test (including Windows).
        book = Book({'title': self.text, 'creator': self.text, 'language': 'en'})
        book.add_chapter(Chapter.from_content('one.xhtml', self.text, '<p>A &amp; B</p>'))
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'book.epub')
            save_book(book, path)
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.endswith(('.xml', '.opf', '.xhtml', '.ncx')):
                        with self.subTest(name=name):
                            etree.fromstring(archive.read(name))
            loaded = read_book(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, self.text)
        self.assertEqual(loaded.chapters['one.xhtml'].title, self.text)
