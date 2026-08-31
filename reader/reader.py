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

import base64
import mimetypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from bs4 import BeautifulSoup
from tkinterweb import HtmlFrame

from pypublib.epub import read_book, Book

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
        self.book: Book = None
        self.chapter_title = None
        self.chapters = []

        self.html_frame = None
        self.raw_html = None
        self.preview_html = None
        self._build_menu()
        self.build_layout()
        self._bind_shortcuts()

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open EPUB...", command=self.open_epub, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Previous Chapter", command=self.prev_chapter, accelerator="Left")
        view_menu.add_command(label="Next Chapter", command=self.next_chapter, accelerator="Right")
        menubar.add_cascade(label="Navigate", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.status = None
        self.config(menu=menubar)

    # -------------------------------------- Creation of User Interface --------------------------------------

    def build_layout(self):
        """
        Erstellt die komplette Benutzeroberfläche des EPUB-Readers.

        Aufbau:

            ┌───────────────────────────────────────────────────────┐
            │ Toolbar                                                │
            ├──────────────┬──────────────────┬─────────────────────┤
            │ Inhalts-     │ Editor HTML      │ Preview HTML        │
            │ verzeichnis  │                  │                     │
            ├──────────────┴──────────────────┴─────────────────────┤
            │ Statusleiste                                           │
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
        style.configure(
            "ChapterTitle.TLabel",
            background="#ffffff",
            foreground="#222222",
            font=("Segoe UI", 13, "bold")
        )

        # Status
        style.configure(
            "Status.TLabel",
            background="#ddddda",
            foreground="#444444",
            font=("Segoe UI", 9)
        )

        # =========================================================
        # Toolbar
        # =========================================================

        toolbar = ttk.Frame(
            self,
            style="App.TFrame",
            padding=(10, 8)
        )

        toolbar.pack(
            side=tk.TOP,
            fill=tk.X
        )

        # Titel links
        ttk.Label(
            toolbar,
            text="EPUB Reader",
            font=("Segoe UI Semibold", 12)
        ).pack(
            side=tk.LEFT,
            padx=(0, 20)
        )

        # Öffnen
        ttk.Button(
            toolbar,
            text="📖 Open",
            command=self.open_epub
        ).pack(
            side=tk.LEFT
        )

        # Navigation
        ttk.Button(
            toolbar,
            text="◀ Prev",
            command=self.prev_chapter
        ).pack(
            side=tk.LEFT,
            padx=(12, 3)
        )

        ttk.Button(
            toolbar,
            text="Next ▶",
            command=self.next_chapter
        ).pack(
            side=tk.LEFT
        )

        # =========================================================
        # Hauptbereich
        # =========================================================

        main = ttk.PanedWindow(
            self,
            orient=tk.HORIZONTAL
        )

        main.pack(
            fill=tk.BOTH,
            expand=True,
            padx=8,
            pady=(0, 8)
        )

        # =========================================================
        # Linkes Panel: Inhaltsverzeichnis
        # =========================================================

        toc_frame = ttk.Frame(
            main,
            style="Panel.TFrame",
            padding=10
        )

        main.add(
            toc_frame,
            weight=1
        )

        ttk.Label(
            toc_frame,
            text="TABLE OF CONTENTS",
            style="PanelTitle.TLabel"
        ).pack(
            anchor="w",
            pady=(0, 8)
        )

        # Listbox + Scrollbar
        toc_container = ttk.Frame(
            toc_frame,
            style="Panel.TFrame"
        )

        toc_container.pack(
            fill=tk.BOTH,
            expand=True
        )

        toc_scrollbar = ttk.Scrollbar(
            toc_container,
            orient=tk.VERTICAL
        )

        toc_scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        self.toc_list = tk.Listbox(
            toc_container,
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#333333",
            selectbackground="#d9e2f3",
            selectforeground="#111111",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            exportselection=False
        )

        self.toc_list.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True
        )

        toc_scrollbar.configure(
            command=self.toc_list.yview
        )

        self.toc_list.configure(
            yscrollcommand=toc_scrollbar.set
        )

        self.toc_list.bind(
            "<<ListboxSelect>>",
            self.on_toc_select
        )

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

        ttk.Label(
            raw_frame,
            text="Editor",
            style="PanelTitle.TLabel"
        ).pack(
            anchor="w",
            pady=(0, 8)
        )

        raw_container = ttk.Frame(
            raw_frame,
            style="Panel.TFrame"
        )

        raw_container.pack(
            fill=tk.BOTH,
            expand=True
        )

        raw_y_scroll = ttk.Scrollbar(
            raw_container,
            orient=tk.VERTICAL
        )

        raw_y_scroll.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        raw_x_scroll = ttk.Scrollbar(
            raw_container,
            orient=tk.HORIZONTAL
        )

        raw_x_scroll.pack(
            side=tk.BOTTOM,
            fill=tk.X
        )

        self.raw_html = tk.Text(
            raw_container,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg="#fafafa",
            fg="#303030",
            insertbackground="#303030",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=8
        )

        self.raw_html.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True
        )

        self.raw_html.configure(
            yscrollcommand=raw_y_scroll.set,
            xscrollcommand=raw_x_scroll.set
        )

        raw_y_scroll.configure(
            command=self.raw_html.yview
        )

        raw_x_scroll.configure(
            command=self.raw_html.xview
        )

        self.raw_html.insert(
            "1.0",
            "Open an EPUB file to start reading."
        )

        self.raw_html.configure(
            state=tk.DISABLED
        )

        # =========================================================
        # Rechtes Panel: gerendertes HTML
        # =========================================================

        html_frame = ttk.Frame(
            panes,
            style="Panel.TFrame",
            padding=10
        )

        panes.add(
            html_frame,
            weight=1
        )

        ttk.Label(
            html_frame,
            text="RENDERED HTML",
            style="PanelTitle.TLabel"
        ).pack(
            anchor="w",
            pady=(0, 8)
        )
        self.preview_html = HtmlFrame(html_frame, messages_enabled=False)
        self.preview_html.pack(fill=tk.BOTH, expand=True)

        # ------------------------------ Status bar -----------------------------

        self.status = ttk.Label(
            self,
            text="Ready",
            style="Status.TLabel",
            anchor="w",
            padding=(10, 5)
        )

        self.status.pack(
            side=tk.BOTTOM,
            fill=tk.X
        )

    def _build_layout(self):
        # Toolbar frame

        toolbar = ttk.Frame(self, padding=(8, 6), relief=tk.SOLID)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="Open", command=self.open_epub).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="◀ Prev", command=self.prev_chapter).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Next ▶", command=self.next_chapter).pack(side=tk.LEFT, padx=(6, 0))

        # Main split area
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        # Left: table of contents
        toc_frame = ttk.Frame(main, padding=8)
        ttk.Label(toc_frame, text="Table of Contents").pack(anchor="w", pady=(0, 6))

        self.toc_list = tk.Listbox(toc_frame, exportselection=False)
        self.toc_list.pack(fill=tk.BOTH, expand=True)
        self.toc_list.bind("<<ListboxSelect>>", self.on_toc_select)

        main.add(toc_frame, weight=1)

        # ----------------------------------- Right: Editor and preview pane -----------------------------------
        panes = ttk.PanedWindow(main, orient=tk.HORIZONTAL)

        self.chapter_title = ttk.Label(panes, text="No book opened", font=FONT_HEADER)
        self.chapter_title.pack(anchor="w", pady=(0, 6))

        main.add(panes, weight=4)

        # ----------------------------------- Editor pane -----------------------------------

        raw_frame = ttk.Frame(panes, padding=8)

        panes.add(raw_frame, weight=1)

        ttk.Label(raw_frame, text="Editor").pack(anchor="w", pady=(0, 6))
        self.raw_html = tk.Text(raw_frame, wrap=tk.NONE, font=FONT_CODE)
        self.raw_html.pack(fill=tk.BOTH, expand=True)
        self.raw_html.insert("1.0", "Open an EPUB file to start reading and editing.")

        self.raw_html.config(state=tk.DISABLED)

        # -------------------------- Preview ------------------------------

        self.html_frame = ttk.Frame(panes, padding=8)
        panes.add(self.html_frame, weight=1)
        ttk.Label(self.html_frame, text="Preview HTML").pack(anchor="w", pady=(0, 6))
        self.html_frame = HtmlFrame(self.html_frame, messages_enabled=False)
        self.html_frame.pack(fill=tk.BOTH, expand=True)

        self.raw_html.config(state=tk.DISABLED)

        # Status bar
        self.status = ttk.Label(self, text="Ready", anchor="w", relief=tk.SUNKEN, padding=(8, 4))
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.open_epub())
        self.bind("<Left>", lambda e: self.prev_chapter())
        self.bind("<Right>", lambda e: self.next_chapter())

    def open_epub(self):
        path = filedialog.askopenfilename(
            title="Open EPUB",
            filetypes=[("EPUB files", "*.epub"), ("All files", "*.*")]
        )
        if not path:
            return

        self.current_file = path
        self.status.config(text=f"Opened: {path}")

        self.book = read_book(path)

        self.chapters = [
            (chapter.title, chapter.html)
            for chapter in list(self.book.chapters.values())
        ]

        self.current_chapter_index = 0
        self._refresh_toc()
        self.show_chapter(self.current_chapter_index)

    def _refresh_toc(self):
        self.toc_list.delete(0, tk.END)
        for title, _ in self.chapters:
            self.toc_list.insert(tk.END, title)
        if self.chapters:
            self.toc_list.selection_set(self.current_chapter_index)

    def show_chapter(self, index):
        if not self.chapters or not (0 <= index < len(self.chapters)):
            return

        title, content = self.chapters[index]

        self.raw_html.config(state=tk.NORMAL)
        self.raw_html.delete("1.0", tk.END)
        self.raw_html.insert("1.0", content)
        # self.raw_html.config(state=tk.DISABLED)

        self.preview_html.load_html(self.prepare_chapter(content))

        self.current_chapter_index = index
        self.toc_list.selection_clear(0, tk.END)
        self.toc_list.selection_set(index)
        self.toc_list.see(index)

        self.status.config(text=f"{title} ({index + 1}/{len(self.chapters)})")

    def prepare_chapter(self, content):

        html = self.embed_images(content)
        html = self.embed_svg_images(html)
        html = self.embed_stylesheets(html)

        return html

    def embed_svg_images(self, html):
        """
        Ersetzt SVG-Konstrukte der Form

            <svg>
                <image xlink:href="cover.jpeg">
            </svg>

        durch ein normales <img>-Element.

        chapter_path:
            Pfad des aktuellen XHTML-Dokuments innerhalb des EPUBs.

        get_file_content:
            Funktion, die eine Datei aus dem EPUB liest und
            deren Inhalt als bytes zurückgibt.
        """

        soup = BeautifulSoup(html, "html.parser")

        # Alle SVG-Elemente durchsuchen
        for svg in soup.find_all("svg"):
            image = svg.find("image")

            if image is None:
                continue

            # SVG kann href oder xlink:href verwenden
            href = image.get("href")

            if href is None:
                href = image.get("xlink:href")

            if not href:
                continue

            # Fragment entfernen, falls vorhanden
            href = href.split("#")[0]

            """

            try:


                # Data-URL erzeugen
                data_url = self.image_to_data_url(   data)
                

                # Breite/Höhe des SVG bzw. image übernehmen
                width = image.get("width")
                height = image.get("height")

                # Neues img-Element
                new_img = soup.new_tag("img")

                new_img["src"] = data_url

                if width:
                    new_img["width"] = width

                if height:
                    new_img["height"] = height

                # SVG-Attribute übernehmen
                svg_width = svg.get("width")
                svg_height = svg.get("height")

                if svg_width:
                    new_img["width"] = svg_width

                if svg_height:
                    new_img["height"] = svg_height

                # SVG durch img ersetzen
                svg.replace_with(new_img)

            except Exception as e:

                print(
                    f"SVG-Bild konnte nicht geladen werden: "
                    f"{image_path}: {e}"
                )
            """
        return str(soup)

    def embed_images(self, html):
        """
        Ersetzt EPUB-interne <img>-Referenzen durch Data-URLs.
        """

        soup = BeautifulSoup(html, "html.parser")

        for img in soup.find_all("img"):
            src = img.get("src")

            if not src:
                continue
            try:
                data = self.book.images[src]
                data_url = self.image_to_data_url(data, src)

                img["src"] = data_url

            except Exception as e:
                print(
                    f"Bild konnte nicht geladen werden: "
                    f"{src}: {e}"
                )

        return str(soup)

    @staticmethod
    def image_to_data_url(data, filename):
        mime_type, _ = mimetypes.guess_type(filename)

        if mime_type is None:
            mime_type = "application/octet-stream"

        encoded = base64.b64encode(data).decode("ascii")

        return f"data:{mime_type};base64,{encoded}"

    def embed_stylesheets(self, html):
        """
        Ersetzt <link rel="stylesheet" ...> durch <style>...</style>.

        html:
            HTML/XHTML als String

        get_file_content:
            Funktion, die einen EPUB-internen Dateipfad entgegennimmt
            und den Inhalt der Datei als String zurückgibt.
        """

        soup = BeautifulSoup(html, "html.parser")

        for link in soup.find_all("link", rel="stylesheet"):

            href = link.get("href")
            if not href:
                continue

            try:
                css = self.book.styles[href]

                style = soup.new_tag("style")
                style.string = css

                link.replace_with(style)

            except Exception as e:
                print(f"CSS konnte nicht geladen werden: {href}: {e}")

        return str(soup)

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
