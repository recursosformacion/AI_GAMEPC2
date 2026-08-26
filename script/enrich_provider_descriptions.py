#!/usr/bin/env python
"""Enriquece las descripciones de `providers` en osap-api con datos reales.

Igual que se hizo con los compositores (biografía generada + guardada en BD), este
script completa la descripción multi-idioma de cada proveedor combinando la reseña
base (del YAML) con datos reales del índice local y del proveedor:

  * número de obras/representaciones indexadas,
  * formatos disponibles,
  * estado (conectado / no conectado),
  * URL pública del proveedor.

El resultado se guarda en `providers.description` como JSON `{es, ca, fr, en, de}`.
Es idempotente: re-ejecutarlo reescribe las descripciones con datos actualizados.

Uso (en osap-api, con PYTHONPATH=osap-api):
    python script/enrich_provider_descriptions.py [--db-api osap_api] [--db-user U] [--db-password P]
"""

from __future__ import annotations

import argparse
import json
import sys

import pymysql
from pymysql.cursors import DictCursor

# Reseña base por provider (se mantiene la del YAML; solo se enriquece).
_BASE = {
    "cpdl": {
        "es": "CPDL (Choral Public Domain Library): partituras corales de dominio público para SATB/SSA/TTBB y más.",
        "en": "CPDL (Choral Public Domain Library): public-domain choral scores for SATB/SSA/TTBB and more.",
        "ca": "CPDL (Choral Public Domain Library): partitures corals de domini públic per a SATB/SSA/TTBB i més.",
        "fr": "CPDL (Choral Public Domain Library) : partitions chorales du domaine public pour SATB/SSA/TTBB et plus.",
        "de": "CPDL (Choral Public Domain Library): gemeinfreie Chorpartituren für SATB/SSA/TTBB und mehr.",
    },
    "freescores": {
        "es": "FreeScores.com: partituras clásicas de dominio público en PDF y MusicXML.",
        "en": "FreeScores.com: public-domain classical scores in PDF and MusicXML.",
        "ca": "FreeScores.com: partitures clàssiques de domini públic en PDF i MusicXML.",
        "fr": "FreeScores.com : partitions classiques du domaine public en PDF et MusicXML.",
        "de": "FreeScores.com: gemeinfreie klassische Noten in PDF und MusicXML.",
    },
    "imslp": {
        "es": "IMSLP (Biblioteca Internacional de Partituras Musicales / Petrucci): dominio público y ediciones modernas.",  # noqa: E501
        "en": "IMSLP (International Music Score Library Project / Petrucci): public domain and modern editions.",  # noqa: E501
        "ca": "IMSLP (Biblioteca Internacional de Partitures Musicals / Petrucci): domini públic i edicions modernes.",  # noqa: E501
        "fr": "IMSLP (Bibliothèque internationale de partitions musicales / Petrucci) : domaine public et éditions modernes.",  # noqa: E501
        "de": "IMSLP (Internationales Musiknotenarchiv / Petrucci): Gemeinfreiheit und moderne Ausgaben.",  # noqa: E501
    },
    "kernscores": {
        "es": "KernScores: colección académica de música en formato Humdrum **kern** (CCARH).",
        "en": "KernScores: academic collection of music in Humdrum **kern** format (CCARH).",
        "ca": "KernScores: col·lecció acadèmica de música en format Humdrum **kern** (CCARH).",
        "fr": "KernScores : collection académique de musique au format Humdrum **kern** (CCARH).",
        "de": "KernScores: akademische Musiksammlung im Humdrum-**kern**-Format (CCARH).",
    },
    "musescore": {
        "es": "MuseScore.com: comunidad de partituras creadas con MuseScore (requiere API key / OAuth).",
        "en": "MuseScore.com: community of scores created with MuseScore (requires API key / OAuth).",
        "ca": "MuseScore.com: comunitat de partitures creades amb MuseScore (requereix API key / OAuth).",
        "fr": "MuseScore.com : communauté de partitions créées avec MuseScore (nécessite une clé API / OAuth).",
        "de": "MuseScore.com: Community von mit MuseScore erstellten Noten (erfordert API-Schlüssel / OAuth).",
    },
    "musicbrainz": {
        "es": "MusicBrainz: base de datos abierta de obras y compositores; aporta metadatos e identificadores.",
        "en": "MusicBrainz: open database of works and composers; provides metadata and identifiers.",
        "ca": "MusicBrainz: base de dades oberta d'obres i compositors; aporta metadades i identificadors.",
        "fr": "MusicBrainz : base de données ouverte d'œuvres et de compositeurs ; fournit métadonnées et identifiants.",  # noqa: E501
        "de": "MusicBrainz: offene Datenbank für Werke und Komponisten; liefert Metadaten und Identifikatoren.",
    },
    "musopen": {
        "es": "Musopen: grabaciones y partituras de dominio público (API deprecada; requiere clave).",
        "en": "Musopen: public-domain recordings and scores (deprecated API; key required).",
        "ca": "Musopen: enregistraments i partitures de domini públic (API obsoleta; requereix clau).",
        "fr": "Musopen : enregistrements et partitions du domaine public (API obsolète ; clé requise).",
        "de": "Musopen: gemeinfreie Aufnahmen und Noten (veraltete API; Schlüssel erforderlich).",
    },
    "mutopia": {
        "es": "Proyecto Mutopia: partituras en dominio público grabadas con LilyPond, con fuente PDF/MIDI editable.",
        "en": "Mutopia Project: public-domain scores typeset with LilyPond, with editable PDF/MIDI source.",
        "ca": "Projecte Mutopia: partitures de domini públic gravades amb LilyPond, amb font PDF/MIDI editable.",
        "fr": "Projet Mutopia : partitions du domaine public gravées avec LilyPond, avec source PDF/MIDI éditable.",
        "de": "Mutopia-Projekt: gemeinfreie Noten mit LilyPond gesetzt, mit editierbarer PDF/MIDI-Quelle.",
    },
    "omr": {
        "es": "Open Music Repository: catálogo propio de partituras digitalizadas (MusicXML) con metadatos normalizados.",  # noqa: E501
        "en": "Open Music Repository: our own catalog of digitized scores (MusicXML) with normalized metadata.",  # noqa: E501
        "ca": "Open Music Repository: catàleg propi de partitures digitalitzades (MusicXML) amb metadades normalitzades.",  # noqa: E501
        "fr": "Open Music Repository : notre propre catalogue de partitions numérisées (MusicXML) avec métadonnées normalisées.",  # noqa: E501
        "de": "Open Music Repository: eigener Katalog digitalisierter Noten (MusicXML) mit normalisierten Metadaten.",
    },
    "openscore": {
        "es": "OpenScore: transcripciones en dominio público alojadas en GitHub, con fuentes MusicXML/MEI editables.",
        "en": "OpenScore: public-domain transcriptions hosted on GitHub, with editable MusicXML/MEI sources.",
        "ca": "OpenScore: transcripcions de domini públic allotjades a GitHub, amb fonts MusicXML/MEI editables.",
        "fr": "OpenScore : transcriptions du domaine public hébergées sur GitHub, avec sources MusicXML/MEI éditables.",
        "de": "OpenScore: gemeinfreie Transkriptionen auf GitHub, mit editierbaren MusicXML/MEI-Quellen.",
    },
    "rism": {
        "es": "RISM: Répertoire International des Sources Musicales, catálogo de fuentes musicales históricas.",
        "en": "RISM: Répertoire International des Sources Musicales, catalogue of historical music sources.",
        "ca": "RISM: Répertoire International des Sources Musicales, catàleg de fonts musicals històriques.",
        "fr": "RISM : Répertoire International des Sources Musicales, catalogue des sources musicales historiques.",
        "de": "RISM: Répertoire International des Sources Musicales, Verzeichnis historischer Musikquellen.",
    },
}

_FMT_LABEL = {
    "musicxml": "MusicXML",
    "mxl": "MusicXML",
    "xml": "MusicXML",
    "pdf": "PDF",
    "midi": "MIDI",
    "mid": "MIDI",
    "json": "metadatos",
    "ly": "LilyPond",
    "mscz": "MuseScore",
    "kern": "Humdrum",
    "rss": "RSS",
}

_LANG_SUFFIX = {
    "es": "obras",
    "en": "works",
    "ca": "obres",
    "fr": "œuvres",
    "de": "Werke",
}


def _fmt_list(formats: list[str]) -> str:
    return ", ".join(_FMT_LABEL.get(f, f) for f in formats) or "—"


def _count_suffix(lang: str, count: int) -> str:
    return f"{count:,} {_LANG_SUFFIX.get(lang, 'works')}".replace(",", ".")


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-api", default="osap-api")
    args = parser.parse_args()

    conn = pymysql.connect(
        host=args.db_host, user=args.db_user, password=args.db_password,
        database=args.db_api, charset="utf8mb4", cursorclass=DictCursor, autocommit=True,
    )
    with conn.cursor() as cur:
        cur.execute("SELECT provider_id, base_url, wired FROM providers")
        providers = cur.fetchall()
        cur.execute(
            "SELECT provider, format, COUNT(*) AS n FROM index_representations "
            "GROUP BY provider, format"
        )
        reps_by_provider: dict[str, dict[str, int]] = {}
        for r in cur.fetchall():
            reps_by_provider.setdefault(r["provider"], {})[r["format"]] = r["n"]

    updated = 0
    for row in providers:
        pid = row["provider_id"]
        base = _BASE.get(pid)
        if base is None:
            continue
        fmts = list((reps_by_provider.get(pid) or {}).keys())
        count = sum((reps_by_provider.get(pid) or {}).values())
        wired = bool(row["wired"])
        description: dict[str, str] = {}
        for lang, text in base.items():
            extras: list[str] = []
            if count:
                extras.append(_count_suffix(lang, count))
            if fmts:
                extras.append(_fmt_list(fmts))
            extras.append("conectado" if wired else ("no conectado" if lang == "es" else
                                                    ("connected" if lang == "en" else
                                                     ("connectat" if lang == "ca" else
                                                      ("connecté" if lang == "fr" else "verbunden")))))
            description[lang] = f"{text} {'. '.join(extras).rstrip('.')}."
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE providers SET description=%s WHERE provider_id=%s",
                (json.dumps(description, ensure_ascii=False), pid),
            )
        updated += 1
        print(f"  {pid:14} -> {len(description)} idiomas | "
              f"{count:,} obras | {_fmt_list(fmts)} | {wired}", flush=True)
    conn.close()
    print(f"actualizados {updated} proveedores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
