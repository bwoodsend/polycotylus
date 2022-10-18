class PolycotylusUsageError(Exception):
    pass


class InvalidLocale(PolycotylusUsageError):

    def __init__(self, locale, location):
        self.locale = locale
        self.location = location

    def __str__(self):
        return f"Locale '{self.locale}', specified at {self.location}, is " \
            "not a valid locale identifier. Run\n     " \
            'python -c "import locale; print(*locale.locale_alias)"\n' \
            "to see a list of valid locales."


class InvalidMimetypePattern(PolycotylusUsageError):

    def __init__(self, mimetype, location):
        self.mimetype = mimetype
        self.location = location

    def __str__(self):
        return f"Mimetype '{self.mimetype}', specified at {self.location}, " \
            "does not match any known mimetypes. Run\n     " \
            'python -c "import mimetypes; print(*mimetypes.types_map.values())"\n' \
            "to see a list of valid mimetypes."


class PolycotylusYAMLParseError(PolycotylusUsageError):
    pass
