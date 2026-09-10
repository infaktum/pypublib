#  MIT License
#  #
#  Copyright (c) 2026 Heiko Sippel
#  #
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#  #
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#  #
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.
#
#
#

"""Track imported EPUB archives and save model changes without regeneration."""

import mimetypes
import os
import posixpath
import re
import tempfile
import zipfile
from copy import copy, deepcopy
from pathlib import Path
from urllib.parse import urlsplit

from lxml import etree

from ._utils import (
    DC, DC_FIELDS, GROUPS, META_KEY_PREFIX, NCX, NS, OPF, XHTML,
    archive_path, metadata_key, parse_xml, relative_url,
    rewrite_css, rewrite_url, xml_bytes,
)


class ArchiveState:
    """Original ZIP records plus independent snapshots of the editable book model."""

    def __init__(self, book, contents):
        """
        Capture an imported book's archive and editable model as a baseline.

        Initializes book.archive_entries and book.package_document. Original
        ZIP records remain separate, so duplicate entry names and per-entry
        metadata can be retained. Mutable metadata and resource values are
        copied to detect later edits independently of the original snapshots.

        Args:
            book (Book): Parsed book whose imported state will be tracked.
            contents (dict): Extraction result containing opf_path,
                archive_records, and an optional archive_comment.

        Raises:
            KeyError: If required extraction data or the OPF entry is missing.
            etree.XMLSyntaxError: If the original OPF cannot be parsed.
        """
        self.path = contents["opf_path"]
        self.records = contents["archive_records"]
        self.comment = contents.get("archive_comment", b"")
        book.archive_entries = {info.filename: data for info, data in self.records}
        self.original_entries = book.archive_entries.copy()
        book.package_document = parse_xml(book.archive_entries[self.path])
        self.original_package = xml_bytes(book.package_document)
        self.metadata = deepcopy(book.metadata)
        self.guide = deepcopy(book.guide)
        self.spine = list(book.spine)
        self.cover = book.cover
        self.groups = {name: dict(getattr(book, name)) for name in GROUPS}
        self.values = {name: {href: value.html if name == "chapters" else deepcopy(value)
                              for href, value in values.items()} for name, values in self.groups.items()}
        self.navigation = {}
        self.manifest_ids = {}
        for item in book.package_document.findall("o:manifest/o:item", NS):
            href = item.get("href")
            self.manifest_ids[href] = item.get('id')
            if "nav" in item.get("properties", "").split():
                self.navigation[href] = "nav"
            elif item.get("media-type") == "application/x-dtbncx+xml":
                self.navigation[href] = "ncx"

    def _resources(self, book):
        """
        Collect the current typed resources with their effective manifest hrefs.

        Recognizes an explicit href change on an original Chapter object even
        when its dictionary key still contains the imported name. Newly added
        or replaced objects use their dictionary keys as the output hrefs.

        Args:
            book (Book): Book containing chapter, stylesheet, image, and font maps.

        Returns:
            dict: Effective href mapped to (group name, dictionary key, value).

        Raises:
            ValueError: If resource paths collide, escape the archive root, or
                would overwrite an unrelated original archive entry.
        """
        resources = {}
        owners = {}
        for group in GROUPS:
            for key, value in getattr(book, group).items():
                # Existing dictionary keys remain stable when an explicit href changes.
                href = value.href if group == "chapters" and value is self.groups[group].get(key) else key
                path = archive_path(self.path, href)
                if path is None or path in {'', '.', '..'} or path.startswith('../') or href.endswith('/'):
                    raise ValueError('Invalid resource archive path: ' + href)
                if path in owners:
                    raise ValueError(f'Resource path collision: {owners[path]!r} and {href!r} resolve to {path!r}')
                original_path = archive_path(self.path, key) if key in self.groups[group] else None
                if path in book.archive_entries and path != original_path:
                    raise ValueError(f'Resource path collision: {href!r} would overwrite archive entry {path!r}')
                owners[path] = href
                resources[href] = (group, key, value)
        return resources

    def _metadata(self, book, root) -> None:
        """
        Apply convenience-metadata edits to a working copy of the OPF root.

        Unchanged fields and unknown XML nodes remain untouched. Scalar edits
        update the last matching element, retaining preceding repeated values
        and attributes. Deleted fields remove their matching elements; subject
        edits add or remove individual values while retaining unchanged nodes.

        Args:
            book (Book): Book whose metadata is compared with the baseline.
            root (etree._Element): Working OPF root to modify in place.

        Returns:
            None.
        """
        if book.metadata == self.metadata:
            return
        parent = root.find("o:metadata", NS)
        if parent is None:
            parent = etree.SubElement(root, etree.QName(OPF, "metadata"), nsmap={"dc": DC})
        for key in self.metadata.keys() | book.metadata.keys():
            if book.metadata.get(key) == self.metadata.get(key):
                continue
            matches = [el for el in parent if metadata_key(el) == key]
            value = book.metadata.get(key)
            if key == "subject":
                values = {value} if isinstance(value, str) else set(value or [])
                for el in matches:
                    if (el.text or "").strip() not in values:
                        parent.remove(el)
                existing = {(el.text or "").strip() for el in matches}
                for subject in sorted(values - existing):
                    etree.SubElement(parent, etree.QName(DC, "subject")).text = subject
            elif value is None or value == "":
                for el in matches:
                    parent.remove(el)
            else:
                # The convenience dictionary exposes the last repeated value. Update
                # that element only; other authors/titles and refinements survive.
                if matches:
                    el = matches[-1]
                elif key in DC_FIELDS:
                    el = etree.SubElement(parent, etree.QName(DC, key))
                elif key.startswith(META_KEY_PREFIX):
                    el = etree.SubElement(parent, etree.QName(OPF, "meta"),
                                          name=key[len(META_KEY_PREFIX):], content="")
                elif key.startswith('{'):
                    el = etree.SubElement(parent, etree.QName(key))
                else:
                    name = "calibre:" + key if key in {"series", "series_index"} else key
                    el = etree.SubElement(parent, etree.QName(OPF, "meta"), name=name, content="")
                if "content" in el.attrib:
                    el.set("content", str(value))
                else:
                    el.text = str(value)

    def package(self, book):
        """
        Build the complete OPF while preserving unedited XML information.

        Copies book.package_document and applies metadata, resource, spine,
        cover, and guide edits. Original manifest IDs and item attributes are
        retained wherever possible. New resources receive unique IDs; deleted
        resources lose their manifest and spine references. This method does not
        modify the live XML tree and the import baseline.

        Args:
            book (Book): Imported book containing current model and XML edits.

        Returns:
            bytes: Original OPF entry bytes when unchanged, otherwise the
            updated document serialized as UTF-8 XML.

        Raises:
            KeyError: If the original OPF entry has been removed from the raw map.
            ValueError: If edited values cannot be represented in XML, XML and
                model edits conflict, or the resulting package has invalid IDs,
                colliding resource paths, or missing local targets.
        """
        tree = deepcopy(book.package_document)
        root = tree.getroot()
        self._metadata(book, root)
        resources = self._resources(book)
        original = {href for group in self.groups.values() for href in group}
        removed = original - resources.keys()
        manifest = root.find("o:manifest", NS)
        if manifest is None:
            manifest = etree.SubElement(root, etree.QName(OPF, "manifest"))
        spine = root.find("o:spine", NS)
        if spine is None:
            spine = etree.SubElement(root, etree.QName(OPF, "spine"))
        renamed_sources = {key for href, (group, key, _) in resources.items()
                           if group == 'chapters' and href != key}
        removed_ids = {self.manifest_ids[href] for href in removed - renamed_sources
                       if href in self.manifest_ids}
        for item in list(manifest.findall("o:item", NS)):
            href = item.get("href")
            if href in removed:
                renamed = next((new for new, (group, key, _) in resources.items()
                                if group == "chapters" and key == href), None)
                if renamed:
                    item.set("href", renamed)
                else:
                    removed_ids.add(item.get("id"))
                    manifest.remove(item)
        for item in list(spine.findall("o:itemref", NS)):
            if item.get("idref") in removed_ids:
                spine.remove(item)
        if list(book.spine) != self.spine:
            xml_spine = [el.get('idref') for el in book.package_document.findall('o:spine/o:itemref', NS)]
            if xml_spine != self.spine and xml_spine != list(book.spine):
                raise ValueError('Conflicting spine edits in package_document and book.spine')
            old = {el.get("idref"): el for el in spine.findall("o:itemref", NS)}
            for el in list(old.values()):
                spine.remove(el)
            for identifier in book.spine:
                if identifier not in removed_ids:
                    item = old.get(identifier)
                    if item is not None:
                        spine.append(item)
                    else:
                        etree.SubElement(spine, etree.QName(OPF, 'itemref'), idref=identifier)
        ids = {el.get("id") for el in manifest}
        existing = {archive_path(self.path, el.get("href")) for el in manifest.findall('o:item', NS)}
        for href, (group, key, value) in resources.items():
            if archive_path(self.path, href) in existing:
                continue
            if key in self.groups[group]:
                current_value = value.html if group == 'chapters' else value
                if href != key or current_value != self.values[group][key]:
                    raise ValueError(f'Conflicting manifest and resource edits for {key!r}')
                # An unchanged model must not undo an explicit XML deletion or rename.
                continue
            i = 1
            while "pypublib-" + str(i) in ids:
                i += 1
            identifier = "pypublib-" + str(i)
            ids.add(identifier)
            media_type = {"chapters": "application/xhtml+xml", "styles": "text/css"}.get(group)
            media_type = media_type or mimetypes.guess_type(href)[0] or "application/octet-stream"
            etree.SubElement(manifest, etree.QName(OPF, "item"),
                             attrib={"id": identifier, "href": href, "media-type": media_type})
            if group == "chapters":
                etree.SubElement(spine, etree.QName(OPF, "itemref"), idref=identifier)
        if book.cover != self.cover:
            for item in manifest.findall("o:item", NS):
                properties = item.get("properties", "").split()
                properties = [prop for prop in properties if prop != "cover-image"]
                if item.get("href") == book.cover:
                    properties.append("cover-image")
                if properties:
                    item.set("properties", " ".join(properties))
                else:
                    item.attrib.pop("properties", None)
        if book.guide != self.guide:
            guide = root.find("o:guide", NS)
            if guide is None:
                guide = etree.SubElement(root, etree.QName(OPF, "guide"))
            old = guide.findall("o:reference", NS)
            for item in old:
                guide.remove(item)
            for values in book.guide:
                match = next((item for item in old if item.get("href") == values.get("href")), None)
                if match is None:
                    item = etree.SubElement(guide, etree.QName(OPF, 'reference'))
                else:
                    item = deepcopy(match)
                    guide.append(item)
                item.attrib.update(values)
        # Structural edits must also update the legacy guide without rebuilding it.
        for reference in root.findall("o:guide/o:reference", NS):
            url = reference.get("href", "")
            old = next((href for href in removed
                        if archive_path(self.path, href) == archive_path(self.path, url)), None)
            if old is not None:
                renamed = next((new for new, (group, key, _) in resources.items()
                                if group == "chapters" and key == old), None)
                if renamed:
                    reference.set("href", relative_url(self.path, archive_path(self.path, renamed), url))
                else:
                    reference.getparent().remove(reference)
        result = xml_bytes(tree)
        if result == self.original_package:
            return book.archive_entries[self.path]
        self._validate_package(tree, book, resources)
        return result

    def _validate_package(self, tree, book, resources):
        """
        Reject inconsistent edited package documents before creating an output ZIP.

        Checks unique manifest IDs and normalized local paths, existing local
        resource targets, and spine references. Unchanged imported OPF bytes
        bypass this validation, so merely copying a legacy book remains possible.

        Args:
            tree (etree._ElementTree): Updated OPF document to validate.
            book (Book): Book providing raw archive entries.
            resources (dict): Validated effective typed-resource mapping.

        Returns:
            None.

        Raises:
            ValueError: If IDs, resource targets, or spine references are invalid.
        """
        available = set(book.archive_entries)
        for group in self.groups.values():
            for href in group:
                if href not in resources:
                    available.discard(archive_path(self.path, href))
        available.update(archive_path(self.path, href) for href in resources)
        ids = set()
        paths = set()
        for item in tree.findall('o:manifest/o:item', NS):
            identifier, href = item.get('id'), item.get('href')
            if not identifier or identifier in ids:
                raise ValueError(f'Missing or duplicate manifest ID: {identifier!r}')
            ids.add(identifier)
            if not href:
                raise ValueError(f'Missing manifest href for {identifier!r}')
            path = archive_path(self.path, href)
            if path is None:
                continue
            if path in paths:
                raise ValueError(f'Manifest resource path collision: {path!r}')
            if path in {'', '.', '..'} or path.startswith('../'):
                raise ValueError(f'Invalid manifest archive path: {path!r}')
            paths.add(path)
            if path not in available:
                raise ValueError(f'Manifest target does not exist: {href!r}')
        for item in tree.findall('o:spine/o:itemref', NS):
            if item.get('idref') not in ids:
                raise ValueError(f'Spine references unknown manifest ID: {item.get("idref")!r}')

    def navigation_bytes(self, book, href):
        """
        Apply structural chapter edits to an existing navigation document.

        Retains authored labels, nested tables of contents, landmarks, page lists,
        and extension data. Renamed chapter targets keep their URL fragments.
        Removed targets lose their links; nested NCX entries are promoted rather
        than discarded. New chapters are appended to the existing top-level TOC.
        Title-only changes do not replace authored navigation labels.

        Args:
            book (Book): Imported book with current chapter and raw-entry edits.
            href (str): OPF-relative href of a known XHTML or NCX navigation file.

        Returns:
            bytes: Original or explicitly edited entry bytes when no structural
            adjustment is needed, otherwise the updated navigation XML.

        Raises:
            KeyError: If the navigation entry is missing or its type is unknown.
            etree.XMLSyntaxError: If a document needing adjustment is invalid XML.
        """
        path = archive_path(self.path, href)
        data = book.archive_entries[path]
        resources = self._resources(book)
        removed = self.groups["chapters"].keys() - resources.keys()
        added = [(key, value) for key, (group, original_key, value) in resources.items()
                 if group == "chapters" and original_key not in self.groups["chapters"]]
        if not removed and not added:
            return data
        tree = parse_xml(data)
        changed = False
        for el in tree.xpath('//*[@href or @src]'):
            attribute = "href" if "href" in el.attrib else "src"
            url = el.get(attribute)
            target = archive_path(path, url)
            old = next((key for key in removed if archive_path(self.path, key) == target), None)
            if old is None:
                continue
            renamed = next((new for new, (group, key, _) in resources.items()
                            if group == "chapters" and key == old), None)
            if renamed:
                el.set(attribute, relative_url(path, archive_path(self.path, renamed), url))
            else:
                parent = el.getparent()
                if etree.QName(parent).localname == "navPoint":
                    # Retain nested entries by promoting them to the containing map.
                    outer = parent.getparent()
                    index = outer.index(parent)
                    for child in parent.findall("n:navPoint", NS):
                        outer.insert(index, child)
                        index += 1
                    outer.remove(parent)
                else:
                    parent.remove(el)
            changed = True
        if added:
            kind = self.navigation[href]
            if kind == "nav":
                containers = tree.xpath('//x:nav[contains(concat(" ", normalize-space(@epub:type), " "), " toc ")]/x:ol',
                                        namespaces=NS)
            else:
                containers = tree.findall("n:navMap", NS)
            if containers:
                parent = containers[0]
                ids = set(tree.xpath('//@id'))
                orders = [int(value) for value in tree.xpath('//@playOrder') if value.isdigit()]
                order = max(orders, default=0)
                for chapter_href, chapter in added:
                    target = relative_url(path, archive_path(self.path, chapter_href))
                    if kind == "nav":
                        item = etree.SubElement(parent, etree.QName(XHTML, "li"))
                        etree.SubElement(item, etree.QName(XHTML, "a"), href=target).text = chapter.title
                    else:
                        order += 1
                        i = 1
                        while "pypublib-nav-" + str(i) in ids:
                            i += 1
                        identifier = "pypublib-nav-" + str(i)
                        ids.add(identifier)
                        item = etree.SubElement(parent, etree.QName(NCX, "navPoint"),
                                                id=identifier, playOrder=str(order))
                        label = etree.SubElement(item, etree.QName(NCX, "navLabel"))
                        etree.SubElement(label, etree.QName(NCX, "text")).text = chapter.title
                        etree.SubElement(item, etree.QName(NCX, "content"), src=target)
                    changed = True
        return xml_bytes(tree) if changed else data

    def _rewrite_references(self, entries, resources):
        """
        Update document links and resource URLs affected by chapter renames.

        Scans XML-based documents and CSS, including opaque archive entries.
        Links targeting renamed chapters are retargeted; URLs inside moved
        documents are rebased to keep referring to their original resources.
        Query strings, fragments, XML bases, and HTML base elements are retained.
        Unchanged documents retain their exact input bytes.

        Args:
            entries (dict[str, bytes]): Prepared output entries, modified in place.
            resources (dict): Effective typed-resource mapping for the current book.

        Returns:
            None.

        Raises:
            ValueError: If a document requiring reference inspection cannot be
                parsed or decoded. The destination has not been written yet.
        """
        renames = {archive_path(self.path, key): archive_path(self.path, href)
                   for href, (group, key, _) in resources.items()
                   if group == 'chapters' and key in self.groups[group] and href != key}
        if not renames:
            return
        sources = {target: source for source, target in renames.items()}
        uri_attributes = {'href', 'src', 'poster', 'data', 'action', 'cite', 'longdesc'}

        def reference_base(document_base, url):
            """
            Resolve a local base URI while preserving directory semantics.

            Args:
                document_base (str): Inherited archive document or directory path.
                url (str): Value of an XML base or HTML base reference.

            Returns:
                str | None: Resolved base, retaining a directory's trailing slash,
                or None for an external base URI.
            """
            resolved_base = archive_path(document_base, url)
            return resolved_base + '/' if resolved_base is not None and urlsplit(url).path.endswith('/') else resolved_base

        def visit(element, old_base, new_base):
            """
            Rewrite one XML subtree using its inherited document/base URLs.

            Args:
                element (etree._Element): Subtree root to update in place.
                old_base (str): Original inherited base URI inside the archive.
                new_base (str): Output inherited base URI inside the archive.

            Returns:
                bool: True if any local URL or inline CSS in the subtree has changed.
                Subtrees with an external XML base are left untouched.
            """
            changed = False
            if not isinstance(element.tag, str):
                return changed
            base = element.get('{http://www.w3.org/XML/1998/namespace}base')
            if base is not None:
                updated = rewrite_url(base, old_base, new_base, renames)
                old_base = reference_base(old_base, base)
                new_base = reference_base(new_base, updated)
                if old_base is None or new_base is None:
                    return False  # An external xml:base makes this subtree external.
                if updated != base:
                    element.set('{http://www.w3.org/XML/1998/namespace}base', updated)
                    changed = True
            for attribute, value in list(element.attrib.items()):
                name = etree.QName(attribute).localname
                if name in uri_attributes:
                    updated = rewrite_url(value, old_base, new_base, renames)
                elif name == 'style':
                    updated = rewrite_css(value, old_base, new_base, renames)
                else:
                    continue
                if updated != value:
                    element.set(attribute, updated)
                    changed = True
            if etree.QName(element).localname == 'style' and element.text:
                updated = rewrite_css(element.text, old_base, new_base, renames)
                if updated != element.text:
                    element.text = updated
                    changed = True
            for child in element:
                changed = visit(child, old_base, new_base) or changed
            return changed

        for path, data in list(entries.items()):
            old_path = sources.get(path, path)
            suffix = posixpath.splitext(path)[1].lower()
            try:
                if suffix == '.css':
                    charset = re.match(br'@charset\s+"([^"\r\n]+)";', data)
                    encoding = charset[1].decode('ascii') if charset else 'utf-8'
                    css = data.decode(encoding)
                    document_updated = rewrite_css(css, old_path, path, renames)
                    if document_updated != css:
                        entries[path] = document_updated.encode(encoding)
                elif suffix in {'.xml', '.xhtml', '.html', '.htm', '.svg', '.smil', '.ncx', '.opf'}:
                    tree = parse_xml(data)
                    root = tree.getroot()
                    document_old_base, document_new_base = old_path, path
                    base_element = root.find('.//x:head/x:base[@href]', NS)
                    document_changed = False
                    if base_element is not None:
                        html_base_url = base_element.get('href')
                        document_updated = rewrite_url(html_base_url, old_path, path, renames)
                        document_old_base = reference_base(old_path, html_base_url)
                        document_new_base = reference_base(path, document_updated)
                        if document_old_base is None or document_new_base is None:
                            continue
                        if document_updated != html_base_url:
                            base_element.set('href', document_updated)
                            document_changed = True
                    # The HTML base element itself is relative to the document,
                    # not relative to the effective base it establishes.
                    base_href = base_element.get('href') if base_element is not None else None
                    if base_element is not None:
                        del base_element.attrib['href']
                    document_changed = visit(root, document_old_base, document_new_base) or document_changed
                    if base_element is not None:
                        base_element.set('href', base_href)
                    if document_changed:
                        entries[path] = xml_bytes(tree)
            except (etree.XMLSyntaxError, UnicodeError, LookupError) as exc:
                raise ValueError(f'Cannot safely update resource references in {path!r}: {exc}') from exc

    def entries(self, book):
        """
        Merge raw archive edits and typed model edits into the output entry map.

        Starts with book.archive_entries, removes deleted typed resources, and
        overlays modified resources, navigation, and OPF data. Explicit typed
        edits take precedence over raw edits to the same file. Unknown entries
        and unchanged resource bytes are retained. No files are written here.

        Args:
            book (Book): Imported book to prepare for saving.

        Returns:
            dict[str, bytes]: Archive paths mapped to their output file contents.

        Raises:
            ValueError: If a typed resource uses an external URL as its output path.
            etree.XMLSyntaxError: If the edited XML cannot be parsed.
            KeyError: If the required OPF or navigation data is missing.
        """
        entries = book.archive_entries.copy()
        resources = self._resources(book)
        for group, originals in self.groups.items():
            for href in originals:
                if href not in resources:
                    entries.pop(archive_path(self.path, href), None)
        for href, (group, key, value) in resources.items():
            value = value.html if group == "chapters" else value
            path = archive_path(self.path, href)
            if path is None:
                raise ValueError("Cannot save a remote resource: " + href)
            if path not in entries or value != self.values[group].get(key):
                entries[path] = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        for href in self.navigation:
            path = archive_path(self.path, href)
            if path not in entries:
                continue
            # Explicit chapter edits win if a navigation document is also in the spine.
            if href not in resources or resources[href][2].html == self.values["chapters"].get(href):
                entries[path] = self.navigation_bytes(book, href)
        entries[self.path] = self.package(book)
        self._rewrite_references(entries, resources)
        return entries

    def save(self, book, file_path):
        """
        Save an imported book without regenerating its publication structure.

        Retains original record order, compression methods, timestamps, comments,
        extra fields, and unchanged duplicate records. Added entries use DEFLATE.
        Writes to a temporary file beside the destination and replaces the target
        only after the archive closes successfully. Temporary files are cleaned
        up on failure, allowing the input path to be used as the output path.

        Args:
            book (Book): Imported book containing the changes to save.
            file_path (str | Path): Destination EPUB path; its parent must exist.

        Returns:
            None.

        Raises:
            OSError: If creating, writing, or replacing the output fails.
            ValueError: If model data cannot be serialized or uses a remote path.
            etree.XMLSyntaxError: If the edited XML cannot be parsed.

        Note:
            Unchanged entry contents remain byte-identical, but the ZIP container
            is rewritten and is not guaranteed to match the original ZIP bytes.
        """
        entries = self.entries(book)
        target = Path(file_path).resolve()
        # Write beside the destination so replacement is atomic, also for Save.
        descriptor, temporary = tempfile.mkstemp(prefix=".pypublib-", suffix=".epub", dir=target.parent)
        os.close(descriptor)
        try:
            with zipfile.ZipFile(temporary, "w") as archive:
                archive.comment = self.comment
                written = set()
                for info, original in self.records:
                    name = info.filename
                    if name not in entries:
                        continue
                    data = entries[name]
                    if data == self.original_entries[name]:
                        data = original  # Preserve even duplicate original ZIP records.
                    archive.writestr(copy(info), data)
                    written.add(name)
                for name, data in entries.items():
                    if name not in written:
                        archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
