from pathlib import Path
import tkinter.filedialog

favicon = str(Path(__file__).with_name("icon.png").resolve())


class TextViewerWidget:

    def __init__(self, root, initial=None):
        self.open_button = tkinter.Button(root, text="Open",
                                          command=self._open_pressed_cb)
        self.open_button.pack(expand=True)

        self.textbox = tkinter.Text(root)
        self.textbox.pack(expand=True)
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
