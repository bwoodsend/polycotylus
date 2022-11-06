import textwrap
import re


def _unravel(text):
    return re.sub("(^ .*\n)|\n(?! )", lambda m: m[1] or " ",
                  textwrap.dedent(text.lstrip("\n")), flags=re.M)


class PolycotylusUsageError(Exception):
    pass


class InvalidLocale(PolycotylusUsageError):

    def __init__(self, locale, location):
        self.locale = locale
        self.location = location

    def __str__(self):
        return _unravel(f"""
            Locale '{self.locale}', specified at {self.location}, is not a valid
            locale identifier. Run:
                python -c "import locale; print(*locale.locale_alias)"
            to see a list of valid locales.
        """)


class InvalidMimetypePattern(PolycotylusUsageError):

    def __init__(self, mimetype, location):
        self.mimetype = mimetype
        self.location = location

    def __str__(self):
        return _unravel(f"""
            Mimetype '{self.mimetype}', specified at {self.location}, does not
            match any known mimetypes. Run:
                python -c "import mimetypes; print(*mimetypes.types_map.values())"
            to see a list of valid mimetypes.
        """)


class PolycotylusYAMLParseError(PolycotylusUsageError):
    pass
