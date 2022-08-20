import tkinter.filedialog
from pathlib import Path

from dumb_text_viewer import TextViewerWidget

path = Path(__file__).with_name("some-text.txt")


def test_initial_open():
    root = tkinter.Tk()
    self = TextViewerWidget(root, path)
    root.update()
    assert "Hello!" in self.textbox.get(1.0, "end")

    root.quit()


def test_subsequent_open(monkeypatch):
    root = tkinter.Tk()
    self = TextViewerWidget(root)
    root.update()
    self.textbox.get(1.0, "end").isspace()

    monkeypatch.setattr(tkinter.filedialog, "askopenfilename", lambda *_: None)
    self.open_button.invoke()
    root.update()
    self.textbox.get(1.0, "end").isspace()

    monkeypatch.setattr(tkinter.filedialog, "askopenfilename", lambda *_: path)
    self.open_button.invoke()
    root.update()
    assert "Hello!" in self.textbox.get(1.0, "end")

    root.quit()
