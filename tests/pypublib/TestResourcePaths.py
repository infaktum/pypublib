import unittest
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from pypublib._utils import archive_path
from pypublib.book import Book
from pypublib.chapter import Chapter
from pypublib.edit import remove_unnecessary_files
from pypublib.epub import validate_book_resources


class TestResourcePaths(unittest.TestCase):
    def setUp(self):
        self.book = Book({'title': 'Paths', 'creator': 'Tester'})
        self.book.images = {'Images/my cover.png': b'correct', 'Other/my cover.png': b'wrong'}
        self.book.styles = {'Styles/main.css': 'p { color: red; }', 'Other/main.css': 'p { color: blue; }'}
        self.chapter = Chapter.from_content(
            'Text/chapter.xhtml', 'Chapter',
            '<p><img src="../Images/my%20cover.png?size=1&amp;mode=2#view"/></p>',
            ['../Styles/./main.css?v=1#sheet'],
        )
        self.book.add_chapter(self.chapter)

    def test_resolves_urls_without_basename_guessing(self):
        self.assertEqual(self.book.get_resource('../Images/my%20cover.png?q=1#view', self.chapter.href), b'correct')
        self.assertEqual(self.book.get_resource('../Other/my%20cover.png', self.chapter.href), b'wrong')
        self.assertIsNone(self.book.resource_key(self.book.images, 'my%20cover.png', self.chapter.href))
        self.assertIsNone(self.book.resource_key(self.book.images, '../images/my%20cover.png', self.chapter.href))
        self.assertEqual(self.book.resource_key(self.book.styles, './Styles/main.css'), 'Styles/main.css')

    def test_archive_paths_and_fragment_only_references(self):
        cases = {
            '../Images/my%20cover.png?q=1#view': 'EPUB/Images/my cover.png',
            '../Images/a%2520b.png': 'EPUB/Images/a%20b.png',
            '/Images/cover.png': 'Images/cover.png',
            '#section': 'EPUB/Text/one.xhtml',
            '?v=2': 'EPUB/Text/one.xhtml',
            'https://example.com/image.png': None,
            '//example.com/image.png': None,
            'data:image/png;base64,AAAA': None,
        }
        for href, expected in cases.items():
            with self.subTest(href=href):
                self.assertEqual(archive_path('EPUB/Text/one.xhtml', href), expected)

    def test_validation_uses_resolved_paths_and_reports_original_missing_href(self):
        self.assertEqual(validate_book_resources(self.book), [])
        self.chapter.styles.append('../Missing/main.css#fragment')
        issues = validate_book_resources(self.book)
        self.assertEqual(issues[0]['missing_styles'], ['../Missing/main.css#fragment'])
        self.assertEqual(issues[0]['missing_images'], [])

    def test_external_and_data_urls_are_not_missing_local_resources(self):
        self.chapter.content += '<img src="https://example.com/a.png"/><img src="data:image/png;base64,AAAA"/>'
        self.chapter.styles.append('//example.com/styles.css')
        self.assertEqual(validate_book_resources(self.book), [])

    def test_cleanup_keeps_only_correct_directory_matches(self):
        remove_unnecessary_files(self.book)
        self.assertEqual(set(self.book.images), {'Images/my cover.png'})
        self.assertEqual(set(self.book.styles), {'Styles/main.css'})

    def test_original_entries_are_available_when_not_in_typed_maps(self):
        self.book.styles.clear()
        self.book.archive_entries['OEBPS/Styles/main.css'] = b'original stylesheet'
        self.assertEqual(self.book.get_resource('../Styles/main.css', self.chapter.href), b'original stylesheet')
        self.assertEqual(validate_book_resources(self.book), [])

    def test_stylesheet_reference_uses_stylesheet_directory(self):
        self.book.images['Styles/Images/my cover.png'] = b'css-relative'
        self.assertEqual(self.book.get_resource('Images/my%20cover.png', 'Styles/main.css'), b'css-relative')

    def test_reader_embeds_relative_images_and_styles_without_opening_a_window(self):
        for name in ('bs4', 'tkinterweb', 'tkinter'):
            if importlib.util.find_spec(name) is None:
                self.skipTest('Optional reader dependency is unavailable: ' + name)
        from bs4 import BeautifulSoup

        path = Path(__file__).resolve().parents[2] / 'examples' / '06_reader' / 'reader.py'
        spec = importlib.util.spec_from_file_location('reader_path_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        reader = module.EpubReaderFrame
        context = SimpleNamespace(book=self.book, image_to_data_url=reader.image_to_data_url)
        html = self.chapter.html
        images = reader.embed_images(context, html, self.chapter.href)
        preview = reader.embed_stylesheets(context, images, self.chapter.href)
        soup = BeautifulSoup(preview, 'html.parser')
        self.assertEqual(soup.img['src'], 'data:image/png;base64,Y29ycmVjdA==')
        self.assertEqual(soup.style.string, 'p { color: red; }')
        external = '<img src="https://example.com/image.png"/>'
        self.assertEqual(BeautifulSoup(reader.embed_images(context, external, self.chapter.href),
                                       'html.parser').img['src'], 'https://example.com/image.png')
