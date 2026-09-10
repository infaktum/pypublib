"""Reader controller tests with in-memory widgets and real EPUB I/O."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch

from pypublib import Book, Chapter, publish_book, read_book


class Editor:
    def __init__(self):
        self.text = ''

    def get(self, *_args):
        return self.text

    def delete(self, *_args):
        self.text = ''

    def insert(self, _index, text):
        self.text = text

    def config(self, **_kwargs):
        pass

    def edit_modified(self, *_args):
        return False


class TestReader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ('tkinter', 'tkinterweb'):
            if importlib.util.find_spec(name) is None:
                raise unittest.SkipTest(f'Optional reader dependency missing: {name}')
        source = Path(__file__).resolve().parents[2] / 'examples/06_reader/reader.py'
        spec = importlib.util.spec_from_file_location('reader_example', source)
        cls.reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.reader)

    def setUp(self):
        self.app = SimpleNamespace(book=None, chapters=[], current_file=None,
                                   current_chapter_index=0, dirty=False, _editor_source=None,
                                   raw_html=Editor(), preview_html=MagicMock(), toc_list=MagicMock(),
                                   chapter_title=MagicMock(), status=MagicMock(), title=MagicMock())
        for name in ('open_epub', 'show_chapter', 'apply_edits', 'save_epub', '_confirm_discard',
                     '_pending_edits', '_update_title', '_refresh_toc', 'prepare_chapter',
                     'embed_images', 'embed_stylesheets'):
            setattr(self.app, name, MethodType(getattr(self.reader.EpubReaderFrame, name), self.app))
        self.app.embed_svg_images = self.reader.EpubReaderFrame.embed_svg_images
        self.app.image_to_data_url = self.reader.EpubReaderFrame.image_to_data_url
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.source = Path(directory.name) / 'source.epub'
        self.output = Path(directory.name) / 'edited.epub'
        book = Book({'title': 'Reader test', 'creator': 'Tester', 'language': 'en'})
        book.add_chapter(Chapter.from_content('Text/one.xhtml', 'One',
                                            '<p>Original</p><img src="../Images/test.png"/>'))
        book.add_chapter(Chapter.from_content('Text/two.xhtml', 'Two', '<p>Second</p>'))
        book.add_image('Images/test.png', b'image-data')
        publish_book(book, self.source)
        with patch.object(self.reader.filedialog, 'askopenfilename', return_value=str(self.source)):
            self.app.open_epub()
        self.index = next(i for i, chapter in enumerate(self.app.chapters) if chapter.href == 'Text/one.xhtml')
        self.app.show_chapter(self.index)

    def edit(self, text):
        self.app.raw_html.delete('1.0', 'end')
        self.app.raw_html.insert('1.0', text)

    def test_edit_save_as_preserves_source_and_original_resource_references(self):
        original = self.source.read_bytes()
        page = self.app.raw_html.get('1.0', 'end-1c').replace('Original', 'Edited &amp; safe')
        self.edit(page)
        with patch.object(self.reader.filedialog, 'asksaveasfilename', return_value=str(self.output)):
            self.assertTrue(self.app.save_epub(save_as=True))
        saved = read_book(str(self.output))
        chapter = saved.get_chapter('Text/one.xhtml')
        self.assertIn('Edited &amp; safe', chapter.content)
        self.assertEqual(chapter.images, ['../Images/test.png'])
        self.assertNotIn('data:image', chapter.html)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertFalse(self.app.dirty)

    def test_invalid_xhtml_blocks_navigation_and_save_without_losing_draft(self):
        self.edit('<broken>')
        with patch.object(self.reader.messagebox, 'showerror') as error:
            self.app.show_chapter(self.index + 1)
            self.assertEqual(self.app.current_chapter_index, self.index)
            self.assertFalse(self.app.save_epub())
            self.assertTrue(error.called)
        self.assertEqual(self.app.raw_html.get('1.0', 'end-1c'), '<broken>')
        self.assertIn('Original', self.app.chapters[self.index].content)

    def test_failed_open_keeps_current_book(self):
        current = self.app.book
        with patch.object(self.reader.filedialog, 'askopenfilename', return_value='missing.epub'), \
                patch.object(self.reader.messagebox, 'showerror') as error:
            self.app.open_epub()
        self.assertIs(self.app.book, current)
        error.assert_called_once()

    def test_cancelled_or_failed_save_keeps_changes(self):
        self.edit(self.app.raw_html.get('1.0', 'end-1c').replace('Original', 'Changed'))
        with patch.object(self.reader.filedialog, 'asksaveasfilename', return_value=''):
            self.assertFalse(self.app.save_epub(save_as=True))
        self.assertTrue(self.app.dirty)
        with patch.object(self.reader, 'publish_book', side_effect=OSError('Write failed')), \
                patch.object(self.reader.messagebox, 'showerror'):
            self.assertFalse(self.app.save_epub())
        self.assertTrue(self.app.dirty)
        with patch.object(self.reader.messagebox, 'askyesnocancel', return_value=None):
            self.assertFalse(self.app._confirm_discard())

    def test_navigation_applies_valid_draft_and_keeps_it_unsaved(self):
        self.edit(self.app.raw_html.get('1.0', 'end-1c').replace('Original', 'Changed'))
        self.app.show_chapter(self.index + 1)
        self.assertIn('Changed', self.app.book.get_chapter('Text/one.xhtml').content)
        self.assertTrue(self.app.dirty)
        self.assertEqual(self.app.current_chapter_index, self.index + 1)
        self.assertIn('Original', read_book(str(self.source)).get_chapter('Text/one.xhtml').content)
