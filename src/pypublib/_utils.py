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

"""Shared EPUB archive, CSS inspection and safe resource-path utilities."""

import posixpath
import re
from pathlib import Path, PureWindowsPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from lxml import etree

OPF = "http://www.idpf.org/2007/opf"
DC = "http://purl.org/dc/elements/1.1/"
XHTML = "http://www.w3.org/1999/xhtml"
EPUB = "http://www.idpf.org/2007/ops"
NCX = "http://www.daisy.org/z3986/2005/ncx/"
NS = {"o": OPF, "dc": DC, "x": XHTML, "epub": EPUB, "n": NCX}
GROUPS = ("chapters", "styles", "images", "fonts")
DC_FIELDS = {'title', 'creator', 'subject', 'description', 'publisher', 'contributor',
             'date', 'type', 'format', 'identifier', 'source', 'language', 'relation',
             'coverage', 'rights'}
META_KEY_PREFIX = '{' + OPF + '}meta/'


def relative_url(base, target, original=''):
    """
    Encode an archive target as a relative URL while retaining URL suffixes.

    Args:
        base (str): Archive path of the referring document.
        target (str): Decoded archive path of the target resource.
        original (str): Original URL supplying its query string and fragment.

    Returns:
        str: Relative URL with percent-encoded path characters. Slashes remain
        path separators; literal percent signs, question marks, and hashes in
        filenames cannot become URL syntax.
    """
    suffix = urlsplit(original)
    path = posixpath.relpath(target, posixpath.dirname(base))
    if suffix.path.endswith('/'):
        path += '/'
    return urlunsplit(('', '', quote(path, safe='/'), suffix.query, suffix.fragment))


def rewrite_url(href, old_base, new_base, renames):
    """
    Retarget a local URL after a document or its target has moved.

    Args:
        href (str): Original URL from a document or stylesheet.
        old_base (str): Original referring document's archive path.
        new_base (str): Output referring document's archive path.
        renames (dict[str, str]): Original archive paths mapped to output paths.

    Returns:
        str: Adjusted URL, or the original spelling when it already resolves to
        the intended target. External and data URLs are returned unchanged.
    """
    target = archive_path(old_base, href)
    if target is None:
        return href
    target = renames.get(target, target)
    if archive_path(new_base, href) == target:
        return href
    return relative_url(new_base, target, href)


def rewrite_css(css, old_base, new_base, renames):
    """
    Rewrite CSS url() and quoted @import references without reformatting rules.

    Args:
        css (str): Stylesheet or inline style text.
        old_base (str): Original containing document's archive path.
        new_base (str): Output containing document's archive path.
        renames (dict[str, str]): Original-to-output archive path mapping.

    Returns:
        str: CSS with adjusted references. Comments and unrelated string values
        are retained verbatim; CSS escapes in URLs are decoded before resolution.
    """
    tokens = re.compile(
        r'''/\*.*?\*/|(?P<url>url\(\s*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|(?:\\.|[^)"'])*)\s*\))|(?P<import>@import\s+(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'))|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''',
        re.IGNORECASE | re.DOTALL | re.VERBOSE,
    )

    def replace(match):
        """
        Replace one URL token, leaving comments and ordinary strings intact.

        Args:
            match (re.Match): CSS URL, import, comment, or string token.

        Returns:
            str: Original token or an escaped replacement URL token.
        """
        token = match.group()
        if match.group('url'):
            value = token[token.index('(') + 1:-1].strip()
        elif match.group('import'):
            value = token[len('@import'):].strip()
        else:
            return token
        if value[:1] in {'"', "'"}:
            value = value[1:-1]
        value = re.sub(r'\\([0-9a-fA-F]{1,6})\s?|\\(\r\n|[\n\r\f])|\\(.)',
                       lambda m: chr(int(m[1], 16)) if m[1] and 0 < int(m[1], 16) <= 0x10ffff
                       else (m[3] or ''), value)
        updated = rewrite_url(value, old_base, new_base, renames)
        if updated == value:
            return token
        escaped = updated.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\a ')
        return 'url("' + escaped + '")' if match.group('url') else '@import "' + escaped + '"'

    return tokens.sub(replace, css)


def archive_path(base: str, href: str) -> str | None:
    """
    Resolve a publication URL to a normalized ZIP entry path.

    Resolves relative paths against the containing document using POSIX path
    rules, independent of the operating system. Percent escapes are decoded
    once; query strings and fragments are excluded from the resulting path.
    A fragment-only reference points to the containing document itself.

    Args:
        base (str): Archive path of the document containing the reference.
        href (str): Local relative or absolute URL, or an external URL.

    Returns:
        str | None: Normalized archive path without a leading slash, or None
        for external URLs, including HTTP, protocol-relative, and data URLs.

    Example:
        >>> archive_path("EPUB/Text/chapter.xhtml", "../Images/my%20cover.png#view")
        'EPUB/Images/my cover.png'
    """
    url = urlsplit(href)
    if url.scheme or url.netloc:
        return None
    if not url.path:
        return base
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), unquote(url.path))).lstrip('/')


def parse_xml(data: bytes):
    """
    Parse a complete XML document while retaining its document-level data.

    Keeps namespaces, comments, processing instructions, and the document type.
    External entities are not expanded and network retrieval is disabled.

    Args:
        data (bytes): Original XML bytes, including any encoding declaration.

    Returns:
        etree._ElementTree: Parsed document with its complete root tree.

    Raises:
        etree.XMLSyntaxError: If the supplied data is not well-formed XML.
    """
    return etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True)).getroottree()


def xml_bytes(tree) -> bytes:
    """
    Serialize an XML tree to UTF-8 without adding formatting whitespace.

    Args:
        tree (etree._ElementTree): Complete document to serialize.

    Returns:
        bytes: XML with an encoding declaration and retained document-level
        nodes. Text and attribute values are escaped by lxml.
    """
    return etree.tostring(tree, encoding="utf-8", xml_declaration=True)


def metadata_key(element) -> str | None:
    """
    Map an OPF metadata element to its convenience-dictionary key.

    Uses local names only for Dublin Core elements. Extension elements retain
    their expanded XML names, keeping equally named fields in different
    namespaces separate. OPF meta names colliding with Dublin Core fields use
    the prefix ``{OPF namespace}meta/``. Calibre series keys omit calibre: to
    match Book's convenience properties. The XML element is not modified.

    Args:
        element (etree._Element): Metadata child, comment, or processing instruction.

    Returns:
        str | None: Dictionary key, or None for non-element nodes.
    """
    if not isinstance(element.tag, str):
        return None
    qualified = etree.QName(element)
    name = qualified.localname
    if qualified.namespace == DC:
        return name
    if qualified.namespace == OPF and name == "meta":
        name = element.get("name") or element.get("property") or name
        if name.startswith("calibre:"):
            name = name[len("calibre:"):]
        return META_KEY_PREFIX + name if name in DC_FIELDS else name
    return element.tag if qualified.namespace else '{}' + name


# CSS inspection and conservative cleanup

_TOKENS = re.compile(
    r'''/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|url\(\s*(?P<url>(?:\\.|[^'"()\\])*?)\s*\)''',
    re.DOTALL | re.IGNORECASE,
)


def css_references(css):
    """Yield URL values and strings (including imports and image-set sources).

    Ordinary strings may retain an extra resource, which is preferable to
    deleting a dependency we cannot interpret conclusively.
    """
    for match in _TOKENS.finditer(css):
        token = match.group()
        if token.startswith('/*'):
            continue
        value = match.group('url') if match.group('url') is not None else token[1:-1]
        yield re.sub(r'\\([0-9a-fA-F]{1,6})\s?|\\(\r\n|[\n\r\f])|\\(.)',
                     lambda m: chr(int(m[1], 16)) if m[1] and 0 < int(m[1], 16) <= 0x10ffff
                     else (m[3] or ''), value)


def used_selectors(markup):
    root = etree.fromstring(markup.encode('utf-8'),
                            parser=etree.XMLParser(resolve_entities=False, no_network=True))
    result = set()
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        result.add(etree.QName(element).localname)
        result.update('.' + name for name in element.get('class', '').split())
        if element.get('id'):
            result.add('#' + element.get('id'))
    return result


def clean_css(css, used):
    """Remove only provably unused simple rules; preserve complex/at rules.

    Balanced blocks, comments and strings are scanned without reserializing
    CSS. Unknown selectors, nested blocks and incomplete input stay verbatim.
    """
    tokens = re.compile(r'''/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[{};]|(?P<broken>/\*|["'])''', re.DOTALL)
    start = depth = 0
    opening = None
    kept, removed = [], []
    for match in tokens.finditer(css):
        if match.group('broken'):
            return css, []
        token = match.group()
        if token == '{':
            if depth == 0:
                opening = match.start()
            depth += 1
        elif token == '}' and depth:
            depth -= 1
            if depth == 0:
                selector_text = re.sub(r'/\*.*?\*/', '', css[start:opening], flags=re.DOTALL)
                selectors = [part.strip() for part in selector_text.split(',')]
                simple = all(re.fullmatch(r'[.#]?[a-zA-Z_][a-zA-Z0-9_-]*', s) for s in selectors)
                if simple and not any(s in used for s in selectors):
                    # Preserve comments even when their following rule is removed.
                    kept.extend(re.findall(r'/\*.*?\*/', css[start:opening], re.DOTALL))
                    removed.extend(selectors)
                else:
                    kept.append(css[start:match.end()])
                start = match.end()
        elif token == '}':
            return css, []
        elif token == ';' and depth == 0:
            kept.append(css[start:match.end()])
            start = match.end()
    if depth:
        return css, []
    kept.append(css[start:])
    return ''.join(kept), removed


# Filesystem containment for new publications

def resource_path(root, href):
    """Reject absolute, traversing and platform-specific filesystem paths."""
    name = unquote(href)
    windows = PureWindowsPath(name)
    if (not name or name.startswith('/') or windows.drive or '\\' in name
            or ':' in name or '\x00' in name or name.endswith('/')
            or any(part in {'', '.', '..'} or part.endswith((' ', '.')) for part in name.split('/'))
            or windows.is_reserved()):
        raise ValueError(f'Invalid resource path: {href!r}')
    base = Path(root).resolve()
    target = (base / name).resolve()
    if not target.is_relative_to(base) or target == base:
        raise ValueError(f'Resource path escapes output directory: {href!r}')
    return target
