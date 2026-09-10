# EPUB Reader

A small desktop reader built with Tkinter and `pypublib`, demonstrating how to load and display EPUB books.

## Features

- Open local EPUB files using the toolbar, File menu, or `Ctrl+O`.
- Browse chapters in the chapter list or use Previous/Next and `Alt+Left` / `Alt+Right`.
- View chapter HTML source and its rendered preview side by side in resizable panels.
- Display images and apply linked stylesheets stored in the EPUB.
- Track the current chapter and chapter count in the status bar.
- Apply XHTML edits to the book and refresh the preview using **Apply**.
- Save with **Save** / `Ctrl+S`, or choose another file with **Save As** / `Ctrl+Shift+S`.
- Detect invalid XHTML and prompt about unsaved changes before opening another book or exiting.

## Edit and save

1. Open an EPUB and select a chapter.
2. Edit the complete XHTML document in the source pane, including its namespaces.
3. Click **Apply** to validate and update the chapter and preview. Switching chapters
   also applies valid edits; invalid XHTML keeps the current editor open for correction.
4. Click **Save As** to create an edited copy, or **Save** to overwrite the current file.

An asterisk in the window title indicates unsaved changes. Apply updates the in-memory
`Chapter.html`; only Save writes the EPUB. The preview embeds images and stylesheets
in a separate representation, so its data URLs never replace the original chapter source.

The reader uses `Book`, `Chapter`, `read_book` and `publish_book` from `pypublib`,
plus `book.get_resource()` / `book.resolve_resource()` for chapter-relative resources.
Imported archives are saved through the library's atomic replacement mechanism.
No direct access to `ArchiveState` or `_utils` is needed.

The chapter list follows the order provided by `read_book`: spine documents first,
followed by other editable XHTML documents. It is not the authored, hierarchical TOC.

## Possible next improvements

- Show the authored navigation hierarchy and distinguish chapters from auxiliary documents.
- Resolve CSS `@import`, fonts and background images in the preview, including nested paths.
- Add editor undo/redo, search/replace and a jump to the XML error's line and column.
- Load large EPUBs outside the Tk event loop and report progress without freezing the window.
- Navigate internal chapter links and remember the last reading position.
- Replace console-only resource warnings with an expandable diagnostics panel.

## Run

Requires Python 3.10 or later with Tkinter available. From the repository root:

```bash
pip install -e . beautifulsoup4 tkinterweb
python examples/06_reader/reader.py
```

Click **Open** and select an `.epub` file to start reading.
