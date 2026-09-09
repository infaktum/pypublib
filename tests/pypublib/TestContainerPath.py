import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree

from pypublib.epub import extract_epub_content, read_book


class TestContainerPath(unittest.TestCase):
    def container(self, path):
        namespace = 'urn:oasis:names:tc:opendocument:xmlns:container'
        root = etree.Element(etree.QName(namespace, 'container'), nsmap={None: namespace})
        files = etree.SubElement(root, etree.QName(namespace, 'rootfiles'))
        etree.SubElement(files, etree.QName(namespace, 'rootfile'),
                         attrib={'full-path': path, 'media-type': 'application/oebps-package+xml'})
        return etree.tostring(root)

    def create_epub(self, directory, package_path=None, container=None):
        path = str(Path(directory) / 'book.epub')
        with zipfile.ZipFile(path, 'w') as archive:
            if container is not None:
                archive.writestr('META-INF/container.xml', container)
            if package_path is not None:
                archive.writestr(package_path, '''<package xmlns="http://www.idpf.org/2007/opf">
                  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Found</dc:title></metadata>
                  <manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
                  <item id="style" href="main.css" media-type="text/css"/></manifest>
                  <spine><itemref idref="chapter"/></spine></package>''')
                directory_in_zip = package_path.rpartition('/')[0]
                prefix = directory_in_zip + '/' if directory_in_zip else ''
                archive.writestr(prefix + 'chapter.xhtml',
                                 '<html xmlns="http://www.w3.org/1999/xhtml">'
                                 '<head><title>One</title></head><body><p>Text</p></body></html>')
                archive.writestr(prefix + 'main.css', 'p { color: red; }')
        return path

    def test_container_path_takes_precedence_and_resolves_resources(self):
        for package_path in ('EPUB/Packages/book.opf', 'package.opf', 'EPUB/books&notes.opf'):
            with self.subTest(path=package_path), tempfile.TemporaryDirectory() as directory:
                path = self.create_epub(directory, package_path, self.container(package_path))
                with zipfile.ZipFile(path, 'a') as archive:
                    archive.writestr('content.opf', 'This fallback must not be parsed')
                contents = extract_epub_content(path)
                self.assertEqual(contents['metadata']['title'], 'Found')
                self.assertIn('chapter.xhtml', contents['chapters'])
                self.assertEqual(contents['styles']['main.css'], 'p { color: red; }')

    def test_fallback_when_container_is_missing_invalid_or_target_missing(self):
        for container in (None, b'<broken', self.container('missing.opf'), self.container('')):
            for package_path in ('content.opf', 'OEBPS/content.opf'):
                with self.subTest(container=container, path=package_path), tempfile.TemporaryDirectory() as directory:
                    path = self.create_epub(directory, package_path, container)
                    self.assertEqual(extract_epub_content(path)['metadata']['title'], 'Found')

    def test_missing_package_logs_and_raises_descriptive_error(self):
        for container in (None, self.container('missing.opf')):
            with self.subTest(container=container), tempfile.TemporaryDirectory() as directory:
                path = self.create_epub(directory, container=container)
                with zipfile.ZipFile(path, 'a') as archive:
                    archive.writestr('not-content.opf', '<package/>')
                with self.assertLogs('pypublib.epub', level='ERROR') as logs:
                    with self.assertRaisesRegex(ValueError, 'No OPF package found:.*container.xml.*content.opf'):
                        extract_epub_content(path)
                self.assertIn('No OPF package found', logs.output[0])
                with self.assertLogs('pypublib.epub', level='ERROR'):
                    self.assertIsNone(read_book(path))
