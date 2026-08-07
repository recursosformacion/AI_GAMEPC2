"""Léxico musical: clasifica los términos de un título para entender la obra.

Comportamiento por categoría del léxico (un fichero YAML en ``lexicon/``):

  - ``forms``, ``catalogue``, ``opus``, ``work_number`` → CAMBIAN la obra (identidad)
  - ``movements`` → NO cambian la obra; crean un subnivel
  - ``voices``, ``instruments``, ``instrumentation``, ``edition``, ``arrangement``,
    ``genres``, ``languages``, ``phrases`` → describen la representación

Proceso de clasificación (modo DEBUG):
  1. Se reconocen primero las FRASES multi-palabra (Lux Aeterna, Dies Irae, ...).
  2. Por cada token suelto se aplica una selección:
       len<=2 | dígito | stopword | compositor | prefijo catálogo | léxico  → IGNORAR
  3. Los términos no musicales (proveedor, editorial, nombres, numeración...) se
     vuelcan a ``lexicon/sinAsignarTexto.yaml`` (referencia, no para el léxico).
  4. Los términos musicales genuinamente desconocidos se vuelcan a
     ``lexicon/sinAsignar.yaml`` (para enriquecer el léxico), sin duplicados.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from pathlib import Path

# Comportamientos por categoría.
IDENTITY_CATEGORIES = {"forms", "catalogue", "opus", "opus_prefixes", "work_number"}
SUBLEVEL_CATEGORIES = {"movements", "movemets"}
DESCRIPTIVE_CATEGORIES = {
    "voices",
    "instruments",
    "instrumentation",
    "performing_forces",
    "notes",
    "edition",
    "arrangement",
    "genres",
    "languages",
    "liturgical",
    "phrases",
}

# Palabras vacías: nunca son términos musicales.
_STOPWORDS = {
    "and",
    "for",
    "in",
    "the",
    "of",
    "a",
    "an",
    "by",
    "with",
    "from",
    "to",
    "on",
    "op",
    "opus",
    "no",
    "nr",
    "nº",
    "k",
    "kv",
    "bwv",
    "d",
    "hob",
    "rv",
    "woo",
    "arr",
    "arrangement",
    "arrangements",
    "version",
    "versions",
    "movement",
    "movt",
    "wip",
    "draft",
    "reproduction",
    "complete",
    "accurate",
    "facsimile",
    "scan",
    "scanned",
    "manuscript",
    "holograph",
    "transcript",
    "transcription",
    "copy",
    "photocopy",
    "autograph",
    "original",
    "modern",
    "urtext",
    "digital",
    "digitally",
    "public",
    "domain",
    "reprint",
    "reprinted",
    "revised",
    "revision",
    "improved",
    "corrected",
    "clean",
    "edition",
    "new",
    "source",
    "image",
    "images",
    "major",
    "minor",
    "maj",
    "min",
    "flat",
    "sharp",
    "dur",
    "moll",
    "assai",
    "più",
    "satb",
    "ssa",
    "ttbb",
    "sab",
    "soprano",
    "alto",
    "tenor",
    "bass",
    "solo",
    "chorus",
    "choir",
    "orch",
    "orchestra",
    "strings",
    "string",
    "pt",
    "mvmt",
    "imslp",
    "opus_number",
    "more",
    "than",
    "will",
    "introduction",
    "reprise",
    "il",
    "la",
    "le",
    "lo",
    "gli",
    "un",
    "una",
    "e",
    "di",
    "del",
    "della",
    "per",
    "non",
    "che",
    "der",
    "die",
    "das",
    "dem",
    "den",
    "ein",
    "eine",
    "einen",
    "aus",
    "von",
    "zu",
    "wie",
    "und",
    "des",
    "du",
    "de",
    "les",
    "et",
    "sur",
    "sans",
    "avec",
    "y",
    "que",
    "con",
    "para",
    "el",
    "los",
    "se",
    "mi",
    "si",
}

# Nombres propios y apellidos: nunca desconocidos.
_PROPER_NAMES = {
    "mozart",
    "wolfgang",
    "amadeus",
    "wa",
    "w",
    "bach",
    "johann",
    "sebastian",
    "js",
    "beethoven",
    "ludwig",
    "van",
    "schubert",
    "franz",
    "palestrina",
    "giovanni",
    "pierluigi",
    "da",
    "victoria",
    "tomas",
    "tomás",
    "luis",
    "gounod",
    "charles",
    "verdi",
    "giuseppe",
    "brahms",
    "johannes",
    "vivaldi",
    "antonio",
    "bruckner",
    "anton",
    "haendel",
    "handel",
    "georg",
    "frideric",
    "byrd",
    "william",
    "tallis",
    "thomas",
    "monteverdi",
    "claudio",
    "rutter",
    "john",
    "leopold",
    "nannerl",
    "joseph",
    "haydn",
    "felix",
    "mendelssohn",
    "frederic",
    "chopin",
    "robert",
    "schumann",
    "clara",
    "nicolaus",
    "simrock",
    "süßmayr",
    "xaver",
    "pachelbel",
    "purcell",
    "dowland",
    "gesualdo",
    "lasso",
    "desprez",
    "josquin",
    "fauré",
    "faure",
    "ravel",
    "debussy",
    "satie",
    "bizet",
    "saint-saëns",
    "tchaikovsky",
    "rachmaninoff",
    "prokofiev",
    "shostakovich",
    "strauss",
    "mahler",
    "wagner",
    "allegri",
    "morales",
    "guerrero",
    "cabezón",
    "tomkins",
    "gibbons",
}

# Palabras de proveedor: nunca a la lista.
_PROVIDER_WORDS = {
    "imslp",
    "openscore",
    "open-score",
    "open_score",
    "local",
    "youtube",
    "musescore",
    "muse",
    "score",
    "github",
    "zenodo",
    "cpdl",
    "petrucci",
    "wiki",
    "api",
    "org",
    "com",
    "net",
    "pdf",
    "xml",
    "mid",
    "midi",
    "musicxml",
}

# Prefijos de catálogo (se ignoran como tokens): K/KV/BWV/Op/D/Hob/RV/WoO/S...
_CATALOGUE_PREFIXES = {
    "k",
    "kv",
    "köchel",
    "koechel",
    "bwv",
    "hob",
    "hoboken",
    "op",
    "opus",
    "d",
    "rv",
    "woo",
    "s",
    "schw",
    "t",
    "h",
    "wq",
    "mq",
    "hodie",
}

# Numeración: números romanos y ordinales (movimiento/sección/orden).
_NUMBERING_RE = re.compile(r"(?:[ivxlcdm]{1,6}|[0-9]+(?:st|nd|rd|th)|nd|rd|st|th)$", re.IGNORECASE)


def _norm(word: str) -> str:
    return " ".join(word.strip().lower().split())


def _title_words(title: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÿ']+", title)


def _title_has_lowercase(title: str) -> bool:
    return any(w.islower() for w in _title_words(title))


@dataclass
class LexiconResult:
    """Resultado de clasificar un título con el léxico."""

    identity: list[str] = field(default_factory=list)
    movement: list[str] = field(default_factory=list)
    descriptive: list[str] = field(default_factory=list)
    work_number: str | None = None
    unknowns: list[str] = field(default_factory=list)


class Lexicon:
    """Carga el léxico y clasifica títulos; en DEBUG vuelca ignorados y desconocidos."""

    def __init__(self, path: Path, debug: bool = True) -> None:
        self.path = path
        self.debug = debug
        self.terms: dict[str, str] = {}  # término normalizado -> categoría
        self._new_unknowns = 0
        self._new_text = 0
        self._load()

    def _load(self) -> None:
        for yaml_file in self.path.glob("*.yaml"):
            stem = yaml_file.stem.lower()
            if stem.startswith("sinasignar"):
                continue
            try:
                document = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue  # tolerar ficheros malformados durante el enriquecimiento
            if not isinstance(document, dict):
                continue
            category = _norm(yaml_file.stem)
            for terms in document.values():
                if not isinstance(terms, list):
                    continue
                for term in terms:
                    if not isinstance(term, str):
                        continue
                    if category in ("catalogue_prefixes", "opus_prefixes"):
                        _CATALOGUE_PREFIXES.add(_norm(term))
                    else:
                        term = _norm(term)
                        if term:  # filtrar entradas vacías
                            self.terms[term] = category

    def classify(self, title: str) -> LexiconResult:
        result = LexiconResult()
        text = " " + _norm(title) + " "
        matched: set[str] = set()

        # 1. Frases / términos (multi-palabra o de una letra) primero (unidad),
        #    con LÍMITES de palabra para que "c" no coincida dentro de "corpus".
        for term, category in sorted(self.terms.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"\b{re.escape(term)}\b", text) and term not in matched:
                matched.add(term)
                self._assign(result, category, term)

        # work_number: "No. 40" / "No40" / "Number 40".
        m = re.search(r"\b(?:no\.?|number|nº)\s*(\d+)", _norm(title), re.IGNORECASE)
        if m:
            result.work_number = m.group(1)

        # 2. Selección por token (solo los que no forman parte de una frase).
        for word in set(re.findall(r"[a-zà-ÿ']+", text)):
            if word in matched:
                continue
            if any(word in term for term in matched):
                continue
            # Término léxico de una sola palabra (notas c/d/g, voces, formas):
            # se clasifica como música, no como desconocido.
            if word in self.terms:
                self._assign(result, self.terms[word], word)
                continue
            # Plural de un término del léxico ("pianos" -> "piano"): clasificar.
            if word.endswith("s") and word[:-1] in self.terms:
                self._assign(result, self.terms[word[:-1]], word[:-1])
                continue
            status = self._select(word, title)
            if status == "ignore":
                if self.debug:
                    self._register_text(word)
                continue
            if word not in result.unknowns:
                result.unknowns.append(word)
                if self.debug:
                    self._register_unknown(word)
        return result

    def _select(self, word: str, title: str) -> str:
        """Pipeline de selección: 'ignore' o 'unknown'."""
        base = word[:-2] if word.endswith("'s") else word
        if len(base) <= 2 or base.isdigit():
            return "ignore"
        if word in _STOPWORDS or word in _PROPER_NAMES or word in _PROVIDER_WORDS:
            return "ignore"
        if base in _STOPWORDS or base in _PROPER_NAMES or base in _PROVIDER_WORDS:
            return "ignore"
        if word in _CATALOGUE_PREFIXES or base in _CATALOGUE_PREFIXES:
            return "ignore"
        if _NUMBERING_RE.match(word):
            return "ignore"
        # Nombres propios: mayúscula inicial en título con minúsculas.
        if _title_has_lowercase(title) and any(
            token.lower() == word and token[:1].isupper() for token in _title_words(title)
        ):
            return "ignore"
        return "unknown"

    def _assign(self, result: LexiconResult, category: str, term: str) -> None:
        if category in IDENTITY_CATEGORIES:
            result.identity.append(term)
        elif category in SUBLEVEL_CATEGORIES:
            result.movement.append(term)
        else:
            result.descriptive.append(term)

    def _register_unknown(self, term: str) -> None:
        """Término musical desconocido -> sinAsignar.yaml (para el léxico)."""
        if self._append_unique(self.path / "sinAsignar.yaml", term):
            self._new_unknowns += 1

    def _register_text(self, term: str) -> None:
        """Término NO musical (ignorado) -> sinAsignarTexto.yaml (referencia)."""
        if self._append_unique(self.path / "sinAsignarTexto.yaml", term):
            self._new_text += 1

    @staticmethod
    def _append_unique(target: Path, term: str) -> bool:
        terms: list[str] = []
        if target.exists():
            document = yaml.safe_load(target.read_text(encoding="utf-8"))
            if isinstance(document, list):
                terms = [str(t) for t in document]
        if term in terms:
            return False
        terms.append(term)
        terms.sort()
        target.write_text(yaml.safe_dump(terms, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return True

    @property
    def new_unknowns(self) -> int:
        return self._new_unknowns

    @property
    def new_text(self) -> int:
        return self._new_text
