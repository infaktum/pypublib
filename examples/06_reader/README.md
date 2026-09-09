# EPUB Reader

A small desktop reader built with Tkinter and `pypublib`, demonstrating how to load and display EPUB books.

## Features

- Open local EPUB files using the toolbar, File menu, or `Ctrl+O`.
- Browse chapters in the table of contents or use Previous/Next buttons and the left/right arrow keys.
- View chapter HTML source and its rendered preview side by side in resizable panels.
- Display images and apply linked stylesheets stored in the EPUB.
- Track the current chapter and chapter count in the status bar.

The HTML source pane allows temporary edits, but changes do not update the preview or save to the EPUB.

## Run

Requires Python 3.10 or later with Tkinter available. From the repository root:

```bash
pip install -e . beautifulsoup4 tkinterweb
python examples/06_reader/reader.py
```

Click **Open** and select an `.epub` file to start reading.
