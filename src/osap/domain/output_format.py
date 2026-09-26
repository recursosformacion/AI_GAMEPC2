from enum import Enum


class OutputFormat(Enum):
    MUSICXML = "musicxml"
    MEI = "mei"
    MIDI = "midi"
    PDF = "pdf"
    JSON = "json"
    SCORE = "score"
    # Formatos de partitura/audio que CPDL ofrece además de PDF/MXL. Se aceptan de forma
    # explícita (etiquetados como tales) en vez de disfrazarlos de MusicXML/PDF.
    AUDIO = "audio"
    MUS = "mus"
    SIB = "sib"
    MSCZ = "mscz"
    CAPX = "capx"
