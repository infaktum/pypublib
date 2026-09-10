import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree

from pypublib import Book, Chapter
from pypublib.edit import remove_unused_styles, remove_unnecessary_files, clean_unused_styles
from pypublib.epub import save_book, read_book


class TestHighPriorityFixes(unittest.TestCase):
    def book(self):
        book = Book({'title': 'Test', 'creator': 'Author', 'language': 'en'})
        book.add_chapter(Chapter.from_content('Text/one.xhtml', 'One',
                                            '<p class="keep" id="main">Text</p>', ['../Styles/main.css']))
        book.styles['Styles/main.css'] = '.keep { color:red; }'
        return book

    def test_export_rejects_paths_without_touching_external_or_output_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            victim = root / 'victim.txt'
            victim.write_bytes(b'original')
            output = root / 'output.epub'
            output.write_bytes(b'existing output')
            for group in ('chapters', 'styles', 'images', 'fonts'):
                for name in (str(victim), '../victim.txt', '../../victim.txt',
                             '%2e%2e/victim.txt', r'..\victim.txt', r'C:\victim.txt',
                             '/victim.txt', r'\\server\share\victim.txt', 'file:stream'):
                    with self.subTest(group=group, name=name):
                        book = self.book()
                        value = Chapter.from_content(name, 'Unsafe', '<p>x</p>') if group == 'chapters' else (
                            'overwrite' if group == 'styles' else b'overwrite')
                        getattr(book, group)[name] = value
                        with self.assertRaises(ValueError):
                            save_book(book, output)
                        self.assertEqual(victim.read_bytes(), b'original')
                        self.assertEqual(output.read_bytes(), b'existing output')

    def test_export_rejects_generated_and_normalized_path_collisions(self):
        for name in ('content.opf', 'nav.xhtml', 'toc.ncx', 'Styles/%6dain.css', 'styles/MAIN.css'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                book = self.book()
                book.images[name] = b'collision'
                with self.assertRaises(ValueError):
                    save_book(book, Path(directory) / 'output.epub')

    def test_css_cleanup_uses_actual_markup_and_preserves_complex_syntax(self):
        book = self.book()
        preserved = ('p {color:blue;} #main {color:green;} '
                     'p.keep:hover {color:red;} [class="keep"] {color:red;} '
                     '@media screen { .keep {color:green;} } '
                     '@font-face {font-family:test;src:url(font.woff);} '
                     '.keep::before {content:"} ; {";}')
        book.styles['Styles/main.css'] += preserved + '.absent {color:black;}'
        result = remove_unused_styles(book)
        self.assertIs(result, book)
        self.assertIn('.keep { color:red; }', book.styles['Styles/main.css'])
        self.assertIn(preserved, book.styles['Styles/main.css'])
        self.assertNotIn('.absent', book.styles['Styles/main.css'])
        self.assertEqual(book.chapters['Text/one.xhtml'].styles, ['../Styles/main.css'])

    def test_css_cleanup_keeps_incomplete_css(self):
        for css in ('.absent {color:red', '.absent {content:"broken}', '/* broken', '.absent {color:red;} }'):
            with self.subTest(css=css):
                book = self.book()
                book.styles['Styles/main.css'] = css
                remove_unused_styles(book)
                self.assertEqual(book.styles['Styles/main.css'], css)

    def test_directory_cleanup_supports_single_quotes_and_element_selectors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'page.html').write_text("<p class='keep' id='main'>text</p>", encoding='utf-8')
            css = '.keep{} #main{} p{} .absent{}'
            (root / 'main.css').write_text(css, encoding='utf-8')
            clean_unused_styles(root)
            self.assertEqual((root / 'main.css').read_text(), '.keep{} #main{} p{}')

    def test_recursive_css_dependencies_inline_styles_and_cycles_survive(self):
        book = self.book()
        book.styles['Styles/main.css'] = '@import "nested/second.css"; p{background:url(../Images/bg.png)}'
        book.styles['Styles/nested/second.css'] = '@import url("../main.css"); p{background:url(../../Images/my%20image.png)}'
        book.styles['unused.css'] = 'p{color:red;}'
        book.images = {name: b'image' for name in ('Images/bg.png', 'Images/my image.png', 'Images/inline.png', 'Images/svg.png', 'unused.png')}
        book.chapters['Text/one.xhtml'].content += (
            '<p style="background:url(../Images/inline.png)">inline</p>'
            '<svg xmlns="http://www.w3.org/2000/svg"><image href="../Images/svg.png"/></svg>')
        remove_unnecessary_files(book)
        self.assertEqual(set(book.styles), {'Styles/main.css', 'Styles/nested/second.css'})
        self.assertEqual(set(book.images), {'Images/bg.png', 'Images/my image.png', 'Images/inline.png', 'Images/svg.png'})

    def test_export_has_unique_ids_resolvable_spine_and_required_metadata(self):
        book = self.book()
        book.add_cover('Images/cover.jpg', b'cover')
        book.add_image('Text/one.png', b'image')
        book.add_font('Text/one.woff', b'font')
        book.metadata['dcterms:modified'] = 'old'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output.epub'
            save_book(book, output)
            with zipfile.ZipFile(output) as archive:
                root = etree.fromstring(archive.read('OEBPS/content.opf'))
                ns = {'o': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}
                identifier = root.get('unique-identifier')
                self.assertTrue(identifier)
                self.assertEqual(root.find('o:metadata/dc:identifier', ns).get('id'), identifier)
                modified = root.findall('o:metadata/o:meta[@property="dcterms:modified"]', ns)
                self.assertEqual(len(modified), 1)
                self.assertRegex(modified[0].text, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
                items = root.findall('o:manifest/o:item', ns)
                ids = [item.get('id') for item in items]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(len(root.xpath('//@id')), len(set(root.xpath('//@id'))))
                hrefs = [item.get('href') for item in items]
                self.assertEqual(hrefs.count('Cover.xhtml'), 1)
                for href in hrefs:
                    self.assertIn('OEBPS/' + href, archive.namelist())
                for item in root.findall('o:spine/o:itemref', ns):
                    self.assertIn(item.get('idref'), ids)
                    self.assertIn(item.get('linear', 'yes'), {'yes', 'no'})
                self.assertEqual(root.find('o:manifest/o:item[@href="Images/cover.jpg"]', ns).get('media-type'), 'image/jpeg')
            loaded = read_book(str(output))
            self.assertIsNotNone(loaded)
            self.assertEqual(set(loaded.chapters), set(book.chapters) | {'nav.xhtml'})
