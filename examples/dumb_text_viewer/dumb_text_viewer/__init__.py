from pathlib import Path
import tkinter.filedialog
from tkinter.scrolledtext import ScrolledText
from tkinter import E, W, S, N

favicon = str(Path(__file__).with_name("icon.png").resolve())


class TextViewerWidget:
    def __init__(self, root, initial=None):
        frame = tkinter.Frame(root)
        frame.grid(row=0, column=0, sticky=W + E)
        self.open_button = tkinter.Button(frame, text='Open',
                                          command=self._open_pressed_cb)
        self.open_button.grid(row=0, column=0, padx=10, pady=10)

        frame = tkinter.Frame(root, padx=5, pady=5)
        frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10,
                   sticky=E + W + N + S)

        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.textbox = ScrolledText(frame, width=100, height=30)
        self.textbox.grid(row=0, column=0, sticky=E + W + N + S)

        if initial:
            self.open(initial)

    def _open_pressed_cb(self):
        path = tkinter.filedialog.askopenfilename()
        if path:
            self.open(path)

    def open(self, path):
        with open(path, encoding="utf-8") as f:
            contents = f.read()
        self.textbox.delete(1.0, "end")
        self.textbox.insert("end", contents)
