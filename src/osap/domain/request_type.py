from enum import Enum


class RequestType(Enum):
    TITLE = "title"
    COMPOSER = "composer"
    PARTIAL_TITLE = "partial_title"
    DOCUMENT = "document"
    IMAGE = "image"
    MUSICXML = "musicxml"
    MEI = "mei"
    MIDI = "midi"
    URL = "url"
    IDENTIFIER = "identifier"
