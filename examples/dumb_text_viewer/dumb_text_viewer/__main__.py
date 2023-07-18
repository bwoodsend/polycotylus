import tkinter
from argparse import ArgumentParser

from dumb_text_viewer import TextViewerWidget, favicon


def main(args=None):
    parser = ArgumentParser()
    parser.add_argument("file", nargs="?")
    parser.add_argument("--pink-mode", action="store_true")
    options = parser.parse_args(args)

    root = tkinter.Tk(className="Dumb Text Viewer")
    root.title("Dumb Text Viewer")
    root.iconphoto(True, tkinter.PhotoImage(file=favicon))
    TextViewerWidget(root, initial=options.file, pink_mode=options.pink_mode)
    root.mainloop()


if __name__ == "__main__":
    main()
