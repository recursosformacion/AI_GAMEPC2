# Investigación de fuentes externas — estado

Registro del repaso de fuentes de música externas (listas de la página UGR y de
repositorios MusicXML). Conclusión: las fuentes abiertas **realmente aprovechables** son las
ya integradas en la capa de proveedores; el resto queda clasificado como **por descubrir**
(no investigable hoy, revisar cuando sea accesible).

## Integradas (fuente de compositor y/o partituras)

| Fuente | Aporta | Vía |
|---|---|---|
| OMR | composer + scores | `OmrStorageFetcher` (token) |
| IMSLP | composer + scores | `MediaWikiFetcher` (cookie disclaimer; cert caducado) |
| MusicBrainz | composer (relations) | `MusicBrainzFetcher` |
| RISM | composer (incl. "Anonymus") | `RismFetcher` (opac RSS) |
| Wikidata | validación ISNI/VIAF + obra→compositor | `composer_identifiers`, `WikidataWorkAttributor` |
| VIAF | autoridad persona (API frágil) | complemento |

## Por descubrir (no investigables hoy — revisar si se abren)

Fuentes potencialmente relevantes para himnos/canciones/folk/partituras, pero **bloqueadas,
caídas, o sin API consultable** en la actualidad. No se investigan ahora; se dejan anotadas.

**Himnos/coral (alta relevancia para nuestro corpus):**
- Hymnary.org — himnos con compositor + MusicXML. **403 (Cloudflare)**.
- Cyber Hymnal (hymntime.com/tch) — himnos. Conexión rechazada.
- Musica Internacional (musicanet.org) — coral/partituras. Viva pero buscador POST/JS (tienda).
- Dave Marney — nuevos himnos (MusicXML).

**Folk/canciones populares:**
- Cançons Populars d'Europa (xtec.es) — canciones con letra/partitura. Timeout.
- Folkopedia — transcripción de folk inglés (MusicXML/PDF/MIDI).
- Lusthof der Muziek — folk flamenco/holandés (MusicXML).
- Folkoteca Galega — música gallega (MusicXML/PDF/MIDI).

**Compositores clásicos:**
- Classical Composers Database (classical-composers.org) — host roto (500/400).
- Composer Biographies (cl.cam.ac.uk), Classical Net, Classical Composers Archive.

**Ópera (nicho, no nuestro corpus principal):**
- Operissimo, Operabase, Aria Database, Metastasio.

**Amplias / comerciales:**
- All Music Guide (allmusic.com) — API de pago.

## No relevantes para "compositor de una canción"

Repositorios de **partituras** (MusicXML/PDF) y bases **bibliográficas/niche** que no dan
atribución de compositor por búsqueda:
- Score repos: Josquin Project, Ponchielli, NEUMA, SymbTr, Gutenberg, Guitar Loot,
  Hausmusik, ASAP, Sonatas Mozart, SEILS, Jingju, LifeWay, Seely clarinet, La mà de guido.
- Medieval/Renacimiento/chant: CANTUS, DIAMM, Medieval Music DB, Thesaurus Musicarum,
  Latin Motet Index, LEXICON MUSICUM LATINUM, Watermarks, RELICS.
- Bibliográfico/académico: Music Index, MESS, Doctoral Dissertations, Musical Borrowing,
  Beethoven Bibliography, Tuning & Temperament, Women's Studies, IIMP (pago).
- Nicho: Jazz Discography, BHRAMS/IRCAM, Ardal Powell (flauta s.XVIII).

## Conclusión operativa
- Las fuentes **consultables** son las integradas (OMR/IMSLP/MB/RISM/Wikidata/VIAF).
- El trabajo de obra = **toda la información** (compositor + identificadores + scores PDF/
  MusicXML/MIDI en `resources`). Como buscador de partituras, se filtran las fuentes con
  `resources`; para identificación del compositor, cuentan todas y se valida (Wikidata).
- La lista "por descubrir" se revisará si alguna fuente se abre o expone API.


sin clasificar
https://www.musicnotes.com/
Lista de obras completas , se descarga en https://josquin.stanford.edu/cgi-bin/jrp?a=worklist-json
los números de catálogo desde esta URL: https://josquin.stanford.edu/data?a=list


Hablar con
https://www.lamadeguido.com/cat_comp.html


python script/extract_composers_from_dump.py \
    --in latest-all.json.bz2 \
    --out data/authority/composers_wikidata.json