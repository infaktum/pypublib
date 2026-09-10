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

import base64
import mimetypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from tkinterweb import HtmlFrame
from lxml import etree, html as lxml_html

from pypublib import Book, Chapter, read_book, publish_book

FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_HTML = ("Georgia", 18)
FONT_CODE = ("Consolas", 10)
FONT_BOOK = "Georgia"


class EpubReaderFrame(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("EPUB Reader")
        self.geometry("1100x720")
        self.minsize(900, 600)

        self.current_file = None
        self.current_chapter_index = 0
        self.book: Book | None = None
        self.dirty = False
        self._editor_source = None
        self.chapter_title = None
        self.chapters = []

        self.html_frame = None
        self.raw_html = None
        self.preview_html = None
        self.status = None

        self._build_menu()
        self.build_layout()
        self._bind_shortcuts()
        self.protocol('WM_DELETE_WINDOW', self.close_reader)

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open EPUB...", command=self.open_epub, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_epub, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=lambda: self.save_epub(save_as=True), accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close_reader)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Previous Chapter", command=self.prev_chapter, accelerator="Alt+Left")
        view_menu.add_command(label="Next Chapter", command=self.next_chapter, accelerator="Alt+Right")
        menubar.add_cascade(label="Navigate", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.toc_list = None
        self.status = None
        self.config(menu=menubar)

    # -------------------------------------- Creation of User Interface --------------------------------------

    def build_layout(self):
        """
        Erstellt die komplette Benutzeroberfläche des EPUB-Readers.

        Aufbau:

            ┌───────────────────────────────────────────────────────┐
            │ Toolbar                                               │
            ├──────────────┬──────────────────┬─────────────────────┤
            │              │                  │                     │
            │ TOC          │ Editor HTML      │ Preview HTML        │
            │              │                  │                     │
            ├──────────────┴──────────────────┴─────────────────────┤
            │ Status bar                                            │
            └───────────────────────────────────────────────────────┘
        """

        # =========================================================
        # Styles
        # =========================================================

        style = ttk.Style()

        # Modernes Windows-Theme verwenden, sofern vorhanden
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        # Allgemeiner Hintergrund
        style.configure("App.TFrame", background="#eeeeec")

        # Panel mit feinem Rahmen
        style.configure("Panel.TFrame", background="#ffffff", borderwidth=1, relief="solid")

        # Überschrift eines Panels
        style.configure("PanelTitle.TLabel", background="#ffffff", foreground="#555555", font=("Segoe UI", 9, "bold"))

        # Haupttitel
        style.configure("ChapterTitle.TLabel", background="#ffffff", foreground="#222222", font=("Segoe UI", 13,
                                                                                                 "bold"))
        # Status
        style.configure("Status.TLabel", background="#ddddda", foreground="#444444", font=("Segoe UI", 9))

        # =========================================================
        # Toolbar
        # =========================================================

        toolbar = ttk.Frame(self, style="App.TFrame", padding=(10, 8))
        toolbar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(toolbar, text="Apply", command=self.apply_edits).pack(side=tk.RIGHT, padx=3)
        ttk.Button(toolbar, text="Save As", command=lambda: self.save_epub(save_as=True)).pack(side=tk.RIGHT, padx=3)
        ttk.Button(toolbar, text="Save", command=self.save_epub).pack(side=tk.RIGHT, padx=3)

        # Titel links
        ttk.Label(toolbar, text="EPUB Reader", font=("Segoe UI Semibold", 12)).pack(side=tk.LEFT, padx=(0, 20))
        # Öffnen
        ttk.Button(toolbar, text="📖 Open", command=self.open_epub).pack(side=tk.LEFT)
        # Navigation
        ttk.Button(toolbar, text="◀ Prev", command=self.prev_chapter).pack(side=tk.LEFT, padx=(12, 3))
        ttk.Button(toolbar, text="Next ▶", command=self.next_chapter).pack(side=tk.LEFT)

        # =========================================================
        # Hauptbereich
        # =========================================================

        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # =========================================================
        # Linkes Panel: Inhaltsverzeichnis
        # =========================================================

        toc_frame = ttk.Frame(main, style="Panel.TFrame", padding=10)
        main.add(toc_frame, weight=1)
        ttk.Label(toc_frame, text="TABLE OF CONTENTS", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))

        # Listbox + Scrollbar
        toc_container = ttk.Frame(toc_frame, style="Panel.TFrame")
        toc_container.pack(fill=tk.BOTH, expand=True)
        toc_scrollbar = ttk.Scrollbar(toc_container, orient=tk.VERTICAL)
        toc_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.toc_list = tk.Listbox(toc_container, font=("Segoe UI", 10), bg="#ffffff", fg="#333333",
                                   selectbackground="#d9e2f3", selectforeground="#111111", relief=tk.FLAT, borderwidth=0,
                                   highlightthickness=0,
                                   activestyle="none",
                                   exportselection=False
                                   )

        self.toc_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        toc_scrollbar.configure(command=self.toc_list.yview)
        self.toc_list.configure(yscrollcommand=toc_scrollbar.set)
        self.toc_list.bind("<<ListboxSelect>>", self.on_toc_select)

        # ------------------------- Raw HTML + gerendertes HTML -------------------------

        panes = ttk.PanedWindow(main, orient=tk.HORIZONTAL)
        self.chapter_title = ttk.Label(panes, text="No book opened", font=FONT_HEADER)
        self.chapter_title.pack(anchor="w", pady=(0, 6))

        main.add(panes, weight=4)

        # =========================================================
        # Mittleres Panel: Raw HTML
        # =========================================================

        raw_frame = ttk.Frame(panes, style="Panel.TFrame", padding=10)
        panes.add(raw_frame, weight=1)
        ttk.Label(raw_frame, text="Editor", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))
        raw_container = ttk.Frame(raw_frame, style="Panel.TFrame")
        raw_container.pack(fill=tk.BOTH, expand=True)
        raw_y_scroll = ttk.Scrollbar(raw_container, orient=tk.VERTICAL)
        raw_y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        raw_x_scroll = ttk.Scrollbar(raw_container, orient=tk.HORIZONTAL)

        raw_x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.raw_html = tk.Text(raw_container, wrap=tk.NONE, font=("Consolas", 10), bg="#fafafa", fg="#303030",
                                insertbackground="#303030", relief=tk.FLAT, borderwidth=0, highlightthickness=0, padx=8, pady=8)

        self.raw_html.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.raw_html.configure(yscrollcommand=raw_y_scroll.set, xscrollcommand=raw_x_scroll.set)
        raw_y_scroll.configure(command=self.raw_html.yview)
        raw_x_scroll.configure(command=self.raw_html.xview)
        self.raw_html.insert("1.0", "Open an EPUB file to start reading.")
        self.raw_html.bind('<<Modified>>', self._on_editor_modified)
        self.raw_html.edit_modified(False)
        self.raw_html.configure(state=tk.DISABLED)

        # =========================================================
        # Rechtes Panel: gerendertes HTML
        # =========================================================

        html_frame = ttk.Frame(panes, style="Panel.TFrame", padding=10)
        panes.add(html_frame, weight=1)
        ttk.Label(html_frame, text="RENDERED HTML", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self.preview_html = HtmlFrame(html_frame, messages_enabled=False)
        self.preview_html.pack(fill=tk.BOTH, expand=True)

        # ------------------------------ Status bar -----------------------------

        self.status = ttk.Label(self, text="Ready", style="Status.TLabel", anchor="w", padding=(10, 5))

        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.open_epub())
        self.bind("<Control-s>", lambda e: self.save_epub())
        self.bind("<Control-Shift-S>", lambda e: self.save_epub(save_as=True))
        self.bind("<Alt-Left>", lambda e: self.prev_chapter())
        self.bind("<Alt-Right>", lambda e: self.next_chapter())

    def _pending_edits(self):
        return self._editor_source is not None and self.raw_html.get('1.0', 'end-1c') != self._editor_source

    def _on_editor_modified(self, _event=None):
        if self.raw_html.edit_modified():
            self.raw_html.edit_modified(False)
            self._update_title()

    def _update_title(self):
        marker = ' *' if self.dirty or self._pending_edits() else ''
        self.title(f'EPUB Reader - {self.current_file or "No book opened"}{marker}')

    def apply_edits(self, refresh=True):
        if not self.book or not self._pending_edits():
            return True
        chapter = self.chapters[self.current_chapter_index]
        page = self.raw_html.get('1.0', 'end-1c')
        try:
            root = etree.fromstring(page.encode('utf-8'),
                                    parser=etree.XMLParser(resolve_entities=False, no_network=True))
            namespace = 'http://www.w3.org/1999/xhtml'
            if root.tag != f'{{{namespace}}}html' or root.find(f'{{{namespace}}}body') is None:
                raise ValueError('Expected a complete XHTML document with html and body elements.')
            Chapter.from_xhtml(chapter.href, page)  # Validate before touching the book.
            chapter.html = page
        except (etree.XMLSyntaxError, ValueError) as exc:
            messagebox.showerror('Invalid XHTML', str(exc), parent=self)
            return False
        self._editor_source = page
        self.dirty = True
        self._refresh_toc()
        self.chapter_title.config(text=chapter.title)
        self._update_title()
        if refresh:
            self.preview_html.load_html(self.prepare_chapter(chapter.html, chapter.href))
        self.status.config(text='Changes applied; save the EPUB to write them to disk.')
        return True

    def save_epub(self, save_as=False):
        if self.book is None:
            return False
        if not self.apply_edits():
            return False
        path = self.current_file
        if save_as or not path:
            path = filedialog.asksaveasfilename(title='Save EPUB', defaultextension='.epub',
                                              filetypes=[('EPUB files', '*.epub')])
        if not path:
            return False
        try:
            publish_book(self.book, path)
        except Exception as exc:
            messagebox.showerror('Save failed', str(exc), parent=self)
            return False
        self.current_file = path
        self.dirty = False
        self._update_title()
        self.status.config(text=f'Saved: {path}')
        return True

    def _confirm_discard(self):
        if not self.dirty and not self._pending_edits():
            return True
        answer = messagebox.askyesnocancel('Unsaved changes', 'Save changes before continuing?', parent=self)
        if answer is None:
            return False
        return self.save_epub() if answer else True

    def close_reader(self):
        if self._confirm_discard():
            self.destroy()

    def open_epub(self):
        path = filedialog.askopenfilename(
            title="Open EPUB",
            filetypes=[("EPUB files", "*.epub"), ("All files", "*.*")]
        )
        if not path:
            return
        if not self._confirm_discard():
            return
        book = read_book(path)
        if book is None:
            messagebox.showerror('Open failed', f'Could not read EPUB: {path}', parent=self)
            return
        if not book.chapters:
            messagebox.showerror('Open failed', 'This EPUB has no editable XHTML chapters.', parent=self)
            return
        self.current_file = path
        self.book = book
        self.chapters = list(book.chapters.values())
        self.dirty = False
        self._editor_source = None

        self.current_chapter_index = 0
        self._refresh_toc()
        self.show_chapter(self.current_chapter_index)

    def _refresh_toc(self):
        self.toc_list.delete(0, tk.END)
        for chapter in self.chapters:
            self.toc_list.insert(tk.END, chapter.title)
        if self.chapters:
            self.toc_list.selection_set(self.current_chapter_index)

    def show_chapter(self, index):
        if not self.chapters or not (0 <= index < len(self.chapters)):
            return
        if not self.apply_edits(refresh=False):
            self.toc_list.selection_clear(0, tk.END)
            self.toc_list.selection_set(self.current_chapter_index)
            return

        chapter = self.chapters[index]
        title, content = chapter.title, chapter.html

        self.raw_html.config(state=tk.NORMAL)
        self.raw_html.delete("1.0", tk.END)
        self.raw_html.insert("1.0", content)
        self._editor_source = content
        self.raw_html.edit_modified(False)
        self.chapter_title.config(text=title)

        self.preview_html.load_html(self.prepare_chapter(content, chapter.href))

        self.current_chapter_index = index
        self.toc_list.selection_clear(0, tk.END)
        self.toc_list.selection_set(index)
        self.toc_list.see(index)

        self.status.config(text=f"{title} ({index + 1}/{len(self.chapters)})")
        self._update_title()

    def prepare_chapter(self, content, chapter_href=None):

        html = self.embed_svg_images(content)
        html = self.embed_images(html, chapter_href)
        html = self.embed_stylesheets(html, chapter_href)

        return html

    @staticmethod
    def embed_svg_images(html):
        """Adapt simple SVG image wrappers for the preview renderer only."""
        document = lxml_html.document_fromstring(html.encode('utf-8'), parser=lxml_html.HTMLParser(encoding='utf-8'))
        for svg in document.iter('svg'):
            children = [child for child in svg if isinstance(child.tag, str)]
            if len(children) != 1 or children[0].tag != 'image':
                continue
            image = children[0]
            href = image.get('href') or image.get('xlink:href')
            if not href:
                continue
            replacement = lxml_html.Element('img', src=href, alt='')
            for attribute in ('width', 'height'):
                value = svg.get(attribute) or image.get(attribute)
                if value:
                    replacement.set(attribute, value)
            replacement.tail = svg.tail
            svg.getparent().replace(svg, replacement)
        return lxml_html.tostring(document, encoding='unicode')

    def embed_images(self, html, chapter_href=None):
        """
        Ersetzt EPUB-interne <img>-Referenzen durch Data-URLs.
        """

        document = lxml_html.document_fromstring(html.encode('utf-8'), parser=lxml_html.HTMLParser(encoding='utf-8'))

        for img in document.iter('img'):
            src = img.get("src")

            if not src or self.book.resolve_resource(src, chapter_href) is None:
                continue
            try:
                data = self.book.get_resource(src, chapter_href)
                data_url = self.image_to_data_url(data, self.book.resolve_resource(src, chapter_href))

                img.set('src', data_url)

            except Exception as e:
                print(
                    f"Bild konnte nicht geladen werden: "
                    f"{src}: {e}"
                )

        return lxml_html.tostring(document, encoding='unicode')

    @staticmethod
    def image_to_data_url(data, filename):
        mime_type, _ = mimetypes.guess_type(filename)

        if mime_type is None:
            mime_type = "application/octet-stream"

        encoded = base64.b64encode(data).decode("ascii")

        return f"data:{mime_type};base64,{encoded}"

    def embed_stylesheets(self, html, chapter_href=None):
        """
        Ersetzt <link rel="stylesheet" ...> durch <style>...</style>.

        html:
            HTML/XHTML als String

        get_file_content:
            Funktion, die einen EPUB-internen Dateipfad entgegennimmt
            und den Inhalt der Datei als String zurückgibt.
        """

        document = lxml_html.document_fromstring(html.encode('utf-8'), parser=lxml_html.HTMLParser(encoding='utf-8'))

        for link in document.iter('link'):
            if 'stylesheet' not in link.get('rel', '').split():
                continue

            href = link.get("href")
            if not href or self.book.resolve_resource(href, chapter_href) is None:
                continue

            try:
                css = self.book.get_resource(href, chapter_href).decode('utf-8')

                style = lxml_html.Element('style')
                style.text = css
                style.tail = link.tail

                link.getparent().replace(link, style)

            except Exception as e:
                print(f"CSS konnte nicht geladen werden: {href}: {e}")

        return lxml_html.tostring(document, encoding='unicode')

    def on_toc_select(self, _event):
        sel = self.toc_list.curselection()
        if sel:
            self.show_chapter(sel[0])

    def prev_chapter(self):
        if self.current_chapter_index > 0:
            self.show_chapter(self.current_chapter_index - 1)

    def next_chapter(self):
        if self.current_chapter_index < len(self.chapters) - 1:
            self.show_chapter(self.current_chapter_index + 1)

    @staticmethod
    def show_about():
        messagebox.showinfo("About", "EPUB Reader\nDesktop frame prototype")


if __name__ == "__main__":
    app = EpubReaderFrame()
    app.mainloop()
