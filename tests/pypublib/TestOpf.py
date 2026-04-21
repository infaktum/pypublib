import unittest
import tempfile
import os

from pypublib.book import Opf


class TestOpfMethods(unittest.TestCase):
    def setUp(self):
        self.opf_xml = """
         
        <package xmlns="http://www.idpf.org/2007/opf" version="3.0">
            <metadata xmlns:opf="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">
            <dc:title>Buchtitel</dc:title>
            <dc:creator>Autor</dc:creator>
            <dc:subject>Roman</dc:subject>
            <dc:subject>Test</dc:subject>
          </metadata>
          <manifest>
            <item id="chap1" href="kapitel.xhtml" media-type="application/xhtml+xml"/>
            <item id="cover" href="cover.png" media-type="image/png" properties="cover-image"/>
          </manifest>
          <spine>
            <itemref idref="chap1"/>
          </spine>
          <guide>
            <reference type="cover" title="Cover" href="cover.xhtml"/>
          </guide>
        </package>
        """
        self.opf = Opf(self.opf_xml)

    def test_cover(self):
        self.assertEqual(self.opf.cover, "cover.png")

    def test_guide(self):
        guide = self.opf.guide
        self.assertEqual(guide[0]["type"], "cover")
        self.assertEqual(guide[0]["title"], "Cover")
        self.assertEqual(guide[0]["href"], "cover.xhtml")

    def test_manifest(self):
        manifest = self.opf.manifest
        self.assertEqual(manifest[0]["id"], "chap1")
        self.assertEqual(manifest[1]["id"], "cover")

    def test_metadata(self):
        meta = self.opf.metadata
        self.assertEqual(meta["title"], "Buchtitel")
        self.assertEqual(meta["creator"], "Autor")
        self.assertIn("Roman", meta["subject"])
        self.assertIn("Test", meta["subject"])

    def test_spine(self):
        spine = self.opf.spine
        self.assertIn("chap1", spine)

    def test_from_file_without_cover(self):
        opf_xml = """<package xmlns='http://www.idpf.org/2007/opf' version='3.0'>
          <metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>
            <dc:title>T</dc:title>
          </metadata>
          <manifest>
            <item id='c1' href='c1.xhtml' media-type='application/xhtml+xml'/>
          </manifest>
          <spine><itemref idref='c1'/></spine>
        </package>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "content.opf")
            with open(path, "w", encoding="utf-8") as f:
                f.write(opf_xml)
            opf = Opf.from_file(path)

        self.assertIsNone(opf.cover)
        self.assertEqual(opf.guide, [])
        self.assertEqual(opf.spine, ["c1"])

    def test_repr_contains_debug_summary(self):
        representation = repr(self.opf)

        self.assertIn("Opf(", representation)
        self.assertIn("title='Buchtitel'", representation)
        self.assertIn("creator='Autor'", representation)
        self.assertIn("cover='cover.png'", representation)
        self.assertIn("manifest=2", representation)
        self.assertIn("spine=1", representation)
        self.assertIn("guide=1", representation)

if __name__ == "__main__":
    unittest.main()