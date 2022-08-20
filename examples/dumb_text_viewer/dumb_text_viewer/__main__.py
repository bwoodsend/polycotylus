import sys
import tkinter
from pathlib import Path

from dumb_text_viewer import TextViewerWidget, favicon


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    root = tkinter.Tk()
    root.title("Dumb Text Viewer")
    root.iconphoto(True, tkinter.PhotoImage(file=favicon))
    TextViewerWidget(root, initial=args[0] if args else None)
    root.mainloop()


if __name__ == "__main__":
    main()
