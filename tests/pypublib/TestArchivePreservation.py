import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from pypublib.book import Book
from pypublib.chapter import Chapter
from pypublib.epub import extract_epub_content, read_book, save_book


OPF_PATH = 'EPUB/package.opf'
OPF = b'''<?xml version="1.0" encoding="UTF-8"?>
<!-- package comment -->
<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:custom="urn:custom" version="3.0" unique-identifier="uid" prefix="test: urn:test" custom:flag="keep">
 <metadata>
  <dc:identifier id="uid">original-id</dc:identifier><dc:title id="title">Original</dc:title>
  <dc:creator id="a1">First Author</dc:creator><dc:creator id="a2">Second Author</dc:creator>
  <meta refines="#a1" property="role" scheme="marc:relators">aut</meta>
  <meta refines="#a2" property="role" scheme="marc:relators">edt</meta>
  <meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
  <meta name="custom-key" content="custom value"/><custom:data code="7"><custom:child/></custom:data>
  <dc:language>en</dc:language><dc:subject id="subject">One</dc:subject>
 </metadata>
 <manifest>
  <item id="c1" href="Text/one.xhtml" media-type="application/xhtml+xml" properties="svg scripted" media-overlay="audio1"/>
  <item id="c2" href="Text/appendix.xhtml" media-type="application/xhtml+xml" custom:flag="appendix"/>
  <item id="nav" href="Navigation/toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  <item id="ncx" href="Navigation/toc.ncx" media-type="application/x-dtbncx+xml"/>
  <item id="style" href="Styles/main.css" media-type="text/css"/>
  <item id="audio1" href="audio.smil" media-type="application/smil+xml"/>
  <item id="script" href="script.js" media-type="text/javascript"/>
  <item id="cover" href="Images/cover.png" media-type="image/png" properties="cover-image remote-resources"/>
 </manifest>
 <spine toc="ncx" page-progression-direction="rtl"><itemref idref="c1" linear="yes" properties="page-spread-left"/></spine>
 <guide><reference type="text" title="Start" href="Text/one.xhtml#start" custom:flag="guide"/></guide>
 <custom:extension value="preserve"/>
</package>'''
CHAPTER = b'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<?keep processing-instruction?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
 xmlns:custom="urn:chapter" xml:lang="en" lang="en">
 <head><title>One</title><meta name="custom" content="preserve"/>
 <style>p { color: red; }</style><link rel="stylesheet" href="../Styles/main.css" media="screen"/>
 <script src="../script.js"/></head>
 <body class="book" epub:type="bodymatter" custom:flag="keep">Leading &amp; text
 <p id="start">Original <em>nested</em> tail</p><!-- body comment -->
 <custom:node custom:attribute="yes"/>Trailing text</body></html>'''
NAV = b'''<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
 <head><title>Authored navigation</title></head><body>
 <nav epub:type="toc"><ol><li><a href="../Text/one.xhtml#start">Custom label</a>
  <ol><li><a href="../Text/appendix.xhtml#note">Nested entry</a></li></ol></li></ol></nav>
 <nav epub:type="page-list"><ol><li><a href="../Text/one.xhtml#page1">1</a></li></ol></nav>
 <nav epub:type="landmarks"><ol><li><a epub:type="bodymatter" href="../Text/one.xhtml">Start</a></li></ol></nav>
 </body></html>'''
NCX = b'''<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
 <head><meta name="custom" content="keep"/></head><docTitle><text>Original</text></docTitle>
 <navMap><navPoint id="point1" playOrder="1"><navLabel><text>One</text></navLabel>
 <content src="../Text/one.xhtml#start"/><navPoint id="point2" playOrder="2">
 <navLabel><text>Appendix</text></navLabel><content src="../Text/appendix.xhtml"/></navPoint></navPoint></navMap>
 </ncx>'''


class TestArchivePreservation(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / 'original.epub'
        self.output = Path(self.directory.name) / 'output.epub'
        self.entries = {
            'mimetype': b'application/epub+zip',
            'META-INF/container.xml': b'<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                                      b'<rootfile full-path="EPUB/package.opf"/></rootfiles></container>',
            OPF_PATH: OPF,
            'EPUB/Text/one.xhtml': CHAPTER,
            'EPUB/Text/appendix.xhtml': CHAPTER.replace(b'<title>One</title>', b'<title>Appendix</title>'),
            'EPUB/Navigation/toc.xhtml': NAV,
            'EPUB/Navigation/toc.ncx': NCX,
            'EPUB/Styles/main.css': b'@font-face { font-family: custom; src: url(../font.dat); }',
            'EPUB/Images/cover.png': b'png-bytes',
            'EPUB/audio.smil': b'<smil><body/></smil>',
            'EPUB/script.js': b'function example() {}',
            'EPUB/font.dat': b'opaque font bytes',
            'META-INF/custom.xml': b'<unknown preserve="yes"/>',
            'unused/': b'',
            'unused/unknown.bin': bytes(range(256)),
        }
        with zipfile.ZipFile(self.source, 'w') as archive:
            archive.comment = b'Archive comment'
            for name, data in self.entries.items():
                info = zipfile.ZipInfo(name, (2025, 6, 7, 8, 9, 10))
                info.compress_type = zipfile.ZIP_STORED if name == 'mimetype' else zipfile.ZIP_DEFLATED
                info.comment = b'Entry comment'
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        self.book = read_book(str(self.source))
        self.assertIsNotNone(self.book)

    def saved_entries(self, book=None, path=None):
        path = path or self.output
        save_book(book or self.book, path)
        with zipfile.ZipFile(path) as archive:
            return {info.filename: archive.read(info) for info in archive.infolist()}

    def test_unmodified_roundtrip_preserves_all_entry_bytes_and_zip_metadata(self):
        self.assertEqual(self.book.archive_entries, self.entries)
        self.assertEqual(self.book.opf.encode(), OPF)
        self.assertEqual(self.book.nav.encode(), NAV)
        self.assertEqual(self.book.toc.encode(), NCX)
        self.assertEqual(self.saved_entries(), self.entries)
        with zipfile.ZipFile(self.source) as source, zipfile.ZipFile(self.output) as output:
            self.assertEqual(source.namelist(), output.namelist())
            self.assertEqual(source.comment, output.comment)
            for before, after in zip(source.infolist(), output.infolist()):
                for field in ('date_time', 'compress_type', 'external_attr', 'comment', 'extra'):
                    self.assertEqual(getattr(before, field), getattr(after, field))
        self.assertIn('Text/appendix.xhtml', self.book.chapters)
        self.assertEqual(self.book.spine, ['c1'])
        self.assertEqual(self.book.manifest[0]['media-overlay'], 'audio1')

    def test_body_edit_changes_only_chapter_and_retains_complete_xhtml(self):
        chapter = self.book.chapters['Text/one.xhtml']
        chapter.content = chapter.content.replace('Original', 'Changed &amp; safe')
        entries = self.saved_entries()
        for name, data in self.entries.items():
            if name != 'EPUB/Text/one.xhtml':
                self.assertEqual(entries[name], data, name)
        root = etree.fromstring(entries['EPUB/Text/one.xhtml'])
        ns = {'x': 'http://www.w3.org/1999/xhtml'}
        self.assertEqual(root.get('{http://www.w3.org/XML/1998/namespace}lang'), 'en')
        self.assertEqual(root.find('x:body', ns).get('class'), 'book')
        self.assertIsNotNone(root.find('x:head/x:style', ns))
        self.assertEqual(root.find('x:head/x:link', ns).get('media'), 'screen')
        self.assertIsNotNone(root.find('.//{urn:chapter}node'))
        self.assertIn(b'<?keep processing-instruction?>', entries['EPUB/Text/one.xhtml'])
        self.assertIn(b'<!-- body comment -->', entries['EPUB/Text/one.xhtml'])
        self.assertIn('Changed & safe', ''.join(root.itertext()))
        self.assertEqual(entries, self.saved_entries())

    def test_metadata_edit_preserves_repeated_values_refinements_and_extensions(self):
        self.book.title = 'Changed & safe'
        self.book.creator = 'Updated second author'
        entries = self.saved_entries()
        ns = {'o': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}
        root = etree.fromstring(entries[OPF_PATH])
        self.assertEqual(root.findtext('o:metadata/dc:title', namespaces=ns), 'Changed & safe')
        self.assertEqual(root.find('o:metadata/dc:title', ns).get('id'), 'title')
        authors = root.findall('o:metadata/dc:creator', ns)
        self.assertEqual([el.text for el in authors], ['First Author', 'Updated second author'])
        self.assertEqual([el.get('id') for el in authors], ['a1', 'a2'])
        original = etree.fromstring(OPF)
        for path in ('o:manifest', 'o:spine', 'o:guide', '{urn:custom}extension'):
            self.assertEqual(etree.tostring(root.find(path, ns)), etree.tostring(original.find(path, ns)))
        self.assertEqual(len(root.findall('o:metadata/o:meta[@refines]', ns)), 2)
        self.assertEqual(entries['EPUB/Navigation/toc.xhtml'], NAV)
        self.assertEqual(entries['EPUB/Navigation/toc.ncx'], NCX)

    def test_full_document_and_opaque_entry_edits(self):
        self.book.package_document.getroot().set('{urn:custom}flag', 'updated')
        self.book.archive_entries['unused/unknown.bin'] = b'updated bytes'
        self.book.archive_entries['new.bin'] = b'new bytes'
        self.book.archive_entries['EPUB/Navigation/toc.xhtml'] = NAV.replace(b'Custom label', b'Edited label')
        entries = self.saved_entries()
        self.assertEqual(etree.fromstring(entries[OPF_PATH]).get('{urn:custom}flag'), 'updated')
        self.assertEqual(entries['unused/unknown.bin'], b'updated bytes')
        self.assertEqual(entries['new.bin'], b'new bytes')
        self.assertIn(b'Edited label', entries['EPUB/Navigation/toc.xhtml'])

    def test_loaded_title_change_does_not_rename_chapter(self):
        chapter = self.book.chapters['Text/one.xhtml']
        chapter.title = 'A new title'
        self.assertEqual(chapter.href, 'Text/one.xhtml')
        entries = self.saved_entries()
        self.assertEqual(entries[OPF_PATH], OPF)
        self.assertEqual(entries['EPUB/Navigation/toc.xhtml'], NAV)

    def test_add_remove_resources_updates_manifest_and_preserves_other_entries(self):
        self.book.remove_chapter('Text/one.xhtml')
        self.book.add_chapter(Chapter.from_content('Text/new.xhtml', 'New', '<p>New</p>'))
        self.book.styles['Styles/new.css'] = 'p { color: green; }'
        entries = self.saved_entries()
        self.assertNotIn('EPUB/Text/one.xhtml', entries)
        self.assertIn('EPUB/Text/new.xhtml', entries)
        root = etree.fromstring(entries[OPF_PATH])
        ns = {'o': 'http://www.idpf.org/2007/opf'}
        items = root.findall('o:manifest/o:item', ns)
        self.assertNotIn('Text/one.xhtml', [el.get('href') for el in items])
        self.assertIn('Text/new.xhtml', [el.get('href') for el in items])
        self.assertEqual(entries['EPUB/script.js'], self.entries['EPUB/script.js'])
        self.assertIn(b'Nested entry', entries['EPUB/Navigation/toc.xhtml'])
        self.assertIn(b'point2', entries['EPUB/Navigation/toc.ncx'])
        self.assertNotIn(b'../Text/one.xhtml', entries['EPUB/Navigation/toc.xhtml'])
        self.assertIn(b'../Text/new.xhtml', entries['EPUB/Navigation/toc.xhtml'])
        self.assertIn(b'../Text/new.xhtml', entries['EPUB/Navigation/toc.ncx'])
        self.assertEqual(root.findall('o:guide/o:reference', ns), [])

    def test_explicit_rename_keeps_ids_and_navigation_fragments(self):
        self.book.chapters['Text/one.xhtml'].href = 'Text/renamed.xhtml'
        entries = self.saved_entries()
        self.assertNotIn('EPUB/Text/one.xhtml', entries)
        self.assertEqual(entries['EPUB/Text/renamed.xhtml'], CHAPTER)
        root = etree.fromstring(entries[OPF_PATH])
        ns = {'o': 'http://www.idpf.org/2007/opf'}
        item = root.find('o:manifest/o:item[@id="c1"]', ns)
        self.assertEqual(item.get('href'), 'Text/renamed.xhtml')
        self.assertEqual(item.get('media-overlay'), 'audio1')
        self.assertIn(b'../Text/renamed.xhtml#start', entries['EPUB/Navigation/toc.xhtml'])
        self.assertIn(b'../Text/renamed.xhtml#start', entries['EPUB/Navigation/toc.ncx'])
        self.assertEqual(root.find('o:guide/o:reference', ns).get('href'), 'Text/renamed.xhtml#start')

    def test_resource_edit_changes_only_resource(self):
        self.book.styles['Styles/main.css'] = 'p { color: blue; }'
        entries = self.saved_entries()
        expected = dict(self.entries)
        expected['EPUB/Styles/main.css'] = b'p { color: blue; }'
        self.assertEqual(entries, expected)

    def test_rename_updates_links_from_other_chapters_and_smil(self):
        chapter = self.book.chapters['Text/appendix.xhtml']
        chapter.content += '<a href="one.xhtml?v=2#start">Cross reference</a>'
        self.book.archive_entries['EPUB/audio.smil'] = b'<smil><body><text src="Text/one.xhtml#start"/></body></smil>'
        self.book.chapters['Text/one.xhtml'].href = 'Text/renamed.xhtml'
        entries = self.saved_entries()
        self.assertIn(b'href="renamed.xhtml?v=2#start"', entries['EPUB/Text/appendix.xhtml'])
        self.assertIn(b'src="Text/renamed.xhtml#start"', entries['EPUB/audio.smil'])
        self.assertEqual(entries, self.saved_entries())

    def test_move_rebases_images_styles_scripts_inline_css_and_self_links(self):
        chapter = self.book.chapters['Text/one.xhtml']
        chapter.content += '<img src="../Images/cover.png"/><a href="#start">Self</a>'
        chapter.content += '<p style="background: url(../Images/cover.png)">Style</p>'
        chapter.href = 'Text/Deep/renamed.xhtml'
        entries = self.saved_entries()
        root = etree.fromstring(entries['EPUB/Text/Deep/renamed.xhtml'])
        ns = {'x': 'http://www.w3.org/1999/xhtml'}
        self.assertEqual(root.find('x:head/x:link', ns).get('href'), '../../Styles/main.css')
        self.assertEqual(root.find('x:head/x:script', ns).get('src'), '../../script.js')
        self.assertEqual(root.find('.//x:img', ns).get('src'), '../../Images/cover.png')
        self.assertEqual(root.find('.//x:a', ns).get('href'), '#start')
        self.assertIn('../../Images/cover.png', root.find('.//x:p[@style]', ns).get('style'))
        self.assertEqual(entries['EPUB/Styles/main.css'], self.entries['EPUB/Styles/main.css'])

    def test_encoded_rename_and_addition_keep_queries_and_fragments(self):
        from pypublib._utils import archive_path
        self.book.chapters['Text/one.xhtml'].href = 'Text/new%23name%3F%25.xhtml'
        self.book.add_chapter(Chapter.from_content('Text/added%23name.xhtml', 'Added', '<p>new</p>'))
        entries = self.saved_entries()
        ns = {'x': 'http://www.w3.org/1999/xhtml', 'n': 'http://www.daisy.org/z3986/2005/ncx/'}
        for path, query, attr in (
                ('EPUB/Navigation/toc.xhtml', './/x:a', 'href'),
                ('EPUB/Navigation/toc.ncx', './/n:content', 'src')):
            root = etree.fromstring(entries[path])
            for element in root.findall(query, ns):
                self.assertIn(archive_path(path, element.get(attr)), entries)
            self.assertIn(b'new%23name%3F%25.xhtml#start', entries[path])
            self.assertIn(b'added%23name.xhtml', entries[path])

    def test_css_and_svg_links_are_updated_without_rewriting_unrelated_strings(self):
        self.book.styles['Styles/main.css'] = ('/* url(../Text/one.xhtml) */\n'
                                             'p { content: "url(../Text/one.xhtml)"; '
                                             'filter: url("../Text/one.xhtml#filter"); }')
        self.book.archive_entries['EPUB/extra.svg'] = (
            b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
            b'<use xlink:href="Text/one.xhtml#shape"/></svg>')
        self.book.chapters['Text/one.xhtml'].href = 'Text/renamed.xhtml'
        entries = self.saved_entries()
        self.assertIn(b'url("../Text/renamed.xhtml#filter")', entries['EPUB/Styles/main.css'])
        self.assertIn(b'/* url(../Text/one.xhtml) */', entries['EPUB/Styles/main.css'])
        self.assertIn(b'content: "url(../Text/one.xhtml)"', entries['EPUB/Styles/main.css'])
        self.assertIn(b'Text/renamed.xhtml#shape', entries['EPUB/extra.svg'])

    def test_xml_base_preserves_reference_targets_when_chapter_moves(self):
        chapter = self.book.chapters['Text/one.xhtml']
        chapter.html = chapter.html.replace('<body ', '<body xml:base="../Images/" ')
        chapter.content += '<img src="cover.png"/>'
        chapter.href = 'Text/Deep/renamed.xhtml'
        root = etree.fromstring(self.saved_entries()['EPUB/Text/Deep/renamed.xhtml'])
        body = root.find('{http://www.w3.org/1999/xhtml}body')
        self.assertEqual(body.get('{http://www.w3.org/XML/1998/namespace}base'), '../../Images/')
        self.assertEqual(body.find('{http://www.w3.org/1999/xhtml}img').get('src'), 'cover.png')

    def test_html_base_and_external_urls_survive_move(self):
        chapter = self.book.chapters['Text/one.xhtml']
        chapter.html = chapter.html.replace('<head>', '<head><base href="../Images/"/>')
        chapter.content += '<img src="cover.png"/><a href="https://example.com/one.xhtml">External</a>'
        chapter.href = 'Text/Deep/renamed.xhtml'
        root = etree.fromstring(self.saved_entries()['EPUB/Text/Deep/renamed.xhtml'])
        ns = {'x': 'http://www.w3.org/1999/xhtml'}
        self.assertEqual(root.find('x:head/x:base', ns).get('href'), '../../Images/')
        self.assertEqual(root.find('.//x:img', ns).get('src'), 'cover.png')
        self.assertEqual(root.find('.//x:a', ns).get('href'), 'https://example.com/one.xhtml')

    def test_full_xhtml_assignment_keeps_head_and_body_attributes(self):
        chapter = self.book.chapters['Text/one.xhtml']
        chapter.html = chapter.html.replace('Original <em>', 'Edited <em>')
        entries = self.saved_entries()
        self.assertEqual(entries['EPUB/Text/one.xhtml'], CHAPTER.replace(b'Original <em>', b'Edited <em>'))
        self.assertEqual(entries[OPF_PATH], OPF)

    def test_duplicate_archive_records_are_retained(self):
        with zipfile.ZipFile(self.source, 'a') as archive:
            with self.assertWarns(UserWarning):
                archive.writestr('unused/unknown.bin', b'second duplicate')
        book = read_book(str(self.source))
        with self.assertWarns(UserWarning):
            self.saved_entries(book)
        with zipfile.ZipFile(self.output) as archive:
            values = [archive.read(info) for info in archive.infolist() if info.filename == 'unused/unknown.bin']
        self.assertEqual(values, [bytes(range(256)), b'second duplicate'])

    def test_unparseable_chapter_and_non_utf8_css_stay_in_archive(self):
        entries = dict(self.entries)
        entries['EPUB/Text/appendix.xhtml'] = b'<broken'
        entries['EPUB/Styles/main.css'] = b'/* caf\xe9 */'
        with zipfile.ZipFile(self.source, 'w') as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        book = read_book(str(self.source))
        self.assertIsNotNone(book)
        self.assertNotIn('Text/appendix.xhtml', book.chapters)
        self.assertEqual(self.saved_entries(book), entries)

    def test_from_contents_keeps_archive_state(self):
        book = Book()
        book.from_contents(extract_epub_content(str(self.source)))
        self.assertEqual(self.saved_entries(book), self.entries)

    def assert_save_rejected(self, message):
        self.output.write_bytes(b'previous output')
        with self.assertRaisesRegex(ValueError, message):
            save_book(self.book, self.output)
        self.assertEqual(self.output.read_bytes(), b'previous output')

    def test_canonical_resource_collisions_are_rejected(self):
        for href in ('Text/../Text/one.xhtml', 'Text/%6Fne.xhtml', 'Text/one.xhtml?version=2'):
            with self.subTest(href=href):
                self.book.add_chapter(Chapter.from_content(href, 'Collision', '<p>replacement</p>'))
                self.assert_save_rejected('Resource path collision')
                self.book.remove_chapter(href)

    def test_cross_group_and_opaque_entry_collisions_are_rejected(self):
        self.book.images['Text/one.xhtml'] = b'not a chapter'
        self.assert_save_rejected('Resource path collision')
        del self.book.images['Text/one.xhtml']
        self.book.add_chapter(Chapter.from_content('script.js', 'Collision', '<p>replacement</p>'))
        self.assert_save_rejected('would overwrite archive entry')

    def test_paths_outside_archive_are_rejected(self):
        self.book.add_chapter(Chapter.from_content('../../outside.xhtml', 'Outside', '<p>text</p>'))
        self.assert_save_rejected('Invalid resource archive path')

    def test_direct_manifest_deletion_does_not_recreate_resource(self):
        ns = {'o': 'http://www.idpf.org/2007/opf'}
        tree = self.book.package_document
        item = tree.find('o:manifest/o:item[@id="c1"]', ns)
        item.getparent().remove(item)
        self.assert_save_rejected('Spine references unknown manifest ID')
        reference = tree.find('o:spine/o:itemref[@idref="c1"]', ns)
        reference.getparent().remove(reference)
        entries = self.saved_entries()
        root = etree.fromstring(entries[OPF_PATH])
        self.assertIsNone(root.find('o:manifest/o:item[@href="Text/one.xhtml"]', ns))
        self.assertEqual(root.findall('o:spine/o:itemref', ns), [])
        self.assertEqual(entries['EPUB/Text/one.xhtml'], CHAPTER)

    def test_conflicting_manifest_and_chapter_edits_are_rejected(self):
        item = self.book.package_document.find('o:manifest/o:item[@id="c1"]',
                                               {'o': 'http://www.idpf.org/2007/opf'})
        item.getparent().remove(item)
        self.book.chapters['Text/one.xhtml'].content += '<p>changed</p>'
        self.assert_save_rejected('Conflicting manifest and resource edits')

    def test_manifest_id_edits_require_matching_spine_update(self):
        ns = {'o': 'http://www.idpf.org/2007/opf'}
        tree = self.book.package_document
        tree.find('o:manifest/o:item[@id="c1"]', ns).set('id', 'renamed-id')
        self.assert_save_rejected('Spine references unknown manifest ID')
        tree.find('o:spine/o:itemref', ns).set('idref', 'renamed-id')
        root = etree.fromstring(self.saved_entries()[OPF_PATH])
        self.assertEqual(root.find('o:spine/o:itemref', ns).get('idref'), 'renamed-id')

    def test_duplicate_manifest_ids_and_missing_targets_are_rejected(self):
        ns = {'o': 'http://www.idpf.org/2007/opf'}
        item = self.book.package_document.find('o:manifest/o:item[@id="c2"]', ns)
        item.set('id', 'c1')
        self.assert_save_rejected('duplicate manifest ID')
        item.set('id', 'c2')
        item.set('href', 'Text/../Text/one.xhtml')
        self.assert_save_rejected('Manifest resource path collision')
        item.set('href', 'Text/missing.xhtml')
        self.assert_save_rejected('Manifest target does not exist')

    def test_conflicting_spine_views_are_rejected(self):
        self.book.package_document.find('o:spine/o:itemref',
                                         {'o': 'http://www.idpf.org/2007/opf'}).set('idref', 'c2')
        self.book.spine = []
        self.assert_save_rejected('Conflicting spine edits')

    def test_metadata_namespaces_stay_separate_during_import_and_edit(self):
        from pypublib._utils import META_KEY_PREFIX
        from pypublib.book import Opf

        ns = {'o': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}
        parent = self.book.package_document.find('o:metadata', ns)
        etree.SubElement(parent, '{urn:custom}title').text = 'Extension title'
        etree.SubElement(parent, 'title', nsmap={None: ''}).text = 'Unqualified title'
        etree.SubElement(parent, '{urn:custom}subject').text = 'Extension subject'
        etree.SubElement(parent, '{http://www.idpf.org/2007/opf}meta', name='title', content='Meta title')
        view = Opf(etree.tostring(self.book.package_document)).metadata
        self.assertEqual(view['title'], 'Original')
        self.assertEqual(view['{urn:custom}title'], 'Extension title')
        self.assertEqual(view['{}title'], 'Unqualified title')
        self.assertEqual(view[META_KEY_PREFIX + 'title'], 'Meta title')
        self.book.title = 'Changed & safe'
        self.book.metadata['subject'] = {'New subject'}
        root = etree.fromstring(self.saved_entries()[OPF_PATH])
        self.assertEqual(root.findtext('o:metadata/dc:title', namespaces=ns), 'Changed & safe')
        self.assertEqual(root.findtext('o:metadata/{urn:custom}title', namespaces=ns), 'Extension title')
        self.assertEqual(root.findtext('o:metadata/{urn:custom}subject', namespaces=ns), 'Extension subject')
        self.assertEqual(root.find('o:metadata/o:meta[@name="title"]', ns).get('content'), 'Meta title')
        self.book.metadata['{urn:custom}title'] = 'Edited extension title'
        self.book.metadata[META_KEY_PREFIX + 'title'] = 'Edited meta title'
        root = etree.fromstring(self.saved_entries()[OPF_PATH])
        self.assertEqual(root.findtext('o:metadata/dc:title', namespaces=ns), 'Changed & safe')
        self.assertEqual(root.findtext('o:metadata/{urn:custom}title', namespaces=ns), 'Edited extension title')
        self.assertEqual(root.find('o:metadata/o:meta[@name="title"]', ns).get('content'), 'Edited meta title')

    def test_model_deletion_and_xml_deletion_remove_original_spine_id(self):
        item = self.book.package_document.find('o:manifest/o:item[@id="c1"]',
                                               {'o': 'http://www.idpf.org/2007/opf'})
        item.getparent().remove(item)
        self.book.remove_chapter('Text/one.xhtml')
        root = etree.fromstring(self.saved_entries()[OPF_PATH])
        self.assertEqual(root.findall('{*}spine/{*}itemref'), [])

    def test_same_path_save_and_failed_replacement_preserve_source(self):
        original = self.source.read_bytes()
        with patch('pypublib.archive_state.os.replace', side_effect=OSError('test failure')):
            with self.assertRaises(OSError):
                self.saved_entries(path=self.source)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(list(Path(self.directory.name).glob('.pypublib-*')), [])
        self.assertEqual(self.saved_entries(path=self.source), self.entries)
