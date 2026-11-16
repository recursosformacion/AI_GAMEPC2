"""Taxonomía global de agrupaciones y plantillas de cargos/secciones.

La ficha de cada grupo guarda su propia copia editable; estas tablas son la
propuesta común que se usa al crear un grupo y la referencia de Admin.
"""

from __future__ import annotations

# (código, nombre, padre, kind)
GROUP_TYPES: tuple[tuple[str, str, str | None, str], ...] = (
    ("vocal", "Agrupaciones Vocales", None, "coral"),
    ("coral", "Coral", "vocal", "coral"),
    ("coro_mixto", "Coro Mixto (SATB)", "coral", "coral"),
    ("coro_voces_blancas", "Coro de Voces Blancas", "coral", "coral"),
    ("coro_voces_graves", "Coro de Voces Graves", "coral", "coral"),
    ("ensemble_vocal", "Ensemble Vocal", "vocal", "ensemble"),
    ("grupo_camara_vocal", "Grupo de Cámara Vocal", "vocal", "ensemble"),
    ("cuarteto_vocal", "Cuarteto Vocal", "vocal", "ensemble"),
    ("escolania", "Escolanía", "vocal", "coral"),
    ("orfeon", "Orfeón", "vocal", "coral"),
    ("schola_cantorum", "Schola Cantorum", "vocal", "coral"),
    ("orquestal", "Agrupaciones Orquestales", None, "orquesta"),
    ("orquesta_sinfonica", "Orquesta Sinfónica", "orquestal", "orquesta"),
    ("orquesta_filarmonica", "Orquesta Filarmónica", "orquestal", "orquesta"),
    ("orquesta_camara", "Orquesta de Cámara", "orquestal", "orquesta"),
    ("orquesta_cuerdas", "Orquesta de Cuerdas", "orquestal", "orquesta"),
    ("orquesta_barroca", "Orquesta Barroca", "orquestal", "orquesta"),
    ("orquesta_pulso_pua", "Orquesta de Pulso y Púa (Rondalla / Plectro)", "orquestal", "orquesta"),
    ("bandas", "Bandas y Agrupaciones de Viento", None, "banda"),
    ("banda_musica", "Banda de Música", "bandas", "banda"),
    ("banda_sinfonica", "Banda Sinfónica", "bandas", "banda"),
    ("banda_militar", "Banda Militar", "bandas", "banda"),
    ("agrupacion_musical", "Agrupación Musical (Procesional)", "bandas", "banda"),
    ("cornetas_tambores", "Banda de Cornetas y Tambores", "bandas", "banda"),
    ("fanfarria", "Fanfarria", "bandas", "banda"),
    ("brass_band", "Brass Band", "bandas", "banda"),
    ("charanga", "Charanga", "bandas", "banda"),
    ("camara", "Música de Cámara", None, "ensemble"),
    ("duo", "Dúo", "camara", "ensemble"),
    ("trio_piano", "Trío con Piano", "camara", "ensemble"),
    ("trio_cuerdas", "Trío de Cuerdas", "camara", "ensemble"),
    ("cuarteto_cuerdas", "Cuarteto de Cuerdas", "camara", "ensemble"),
    ("quinteto_madera", "Quinteto de Viento-Madera", "camara", "ensemble"),
    ("quinteto_metales", "Quinteto de Metales", "camara", "ensemble"),
    ("octeto", "Octeto", "camara", "ensemble"),
    ("jazz", "Jazz, Moderna y Popular", None, "grupo"),
    ("big_band", "Big Band", "jazz", "grupo"),
    ("combo_jazz", "Combo de Jazz", "jazz", "grupo"),
    ("rock_pop", "Grupo de Rock / Pop", "jazz", "grupo"),
    ("blues_funk", "Banda de Blues / Funk", "jazz", "grupo"),
    ("orquesta_baile", "Orquesta de Baile / Verbena", "jazz", "grupo"),
    ("tradicional", "Tradicional y Folclore", None, "grupo"),
    ("grupo_folk", "Grupo Folk", "tradicional", "grupo"),
    ("banda_gaitas", "Banda de Gaitas", "tradicional", "banda"),
    ("cobla", "Cobla", "tradicional", "grupo"),
    ("tuna", "Tuna", "tradicional", "grupo"),
    ("mariachi", "Mariachi", "tradicional", "grupo"),
    ("grupo_tradicional", "Grupo de Música Tradicional", "tradicional", "grupo"),
)

ADMIN_ROLES: tuple[tuple[str, str], ...] = (
    ("president", "Presidencia"),
    ("secretary", "Secretaría"),
    ("treasurer", "Tesorería"),
    ("board_member", "Vocalía"),
    ("librarian", "Bibliotecario/a"),
)

ROLE_TEMPLATES: dict[str, tuple[tuple[str, str], ...]] = {
    "coral": (("music_director", "Dirección"), ("assistant_director", "Subdirección"),
              ("vocal_coach", "Preparación vocal"), ("singer", "Coralista")),
    "banda": (("music_director", "Dirección"), ("assistant_director", "Subdirección"),
              ("section_leader", "Jefe de sección"), ("musician", "Músico")),
    "orquesta": (("music_director", "Dirección"), ("concertmaster", "Concertino"),
                  ("section_leader", "Jefe de sección"), ("musician", "Músico")),
    "grupo": (("music_director", "Dirección"), ("coordinator", "Coordinación"),
              ("musician", "Componente")),
    "ensemble": (("music_director", "Dirección"), ("coordinator", "Coordinación"),
                  ("musician", "Componente")),
}

SECTION_TEMPLATES: dict[str, tuple[tuple[str, str], ...]] = {
    "coral": (("soprano", "Soprano"), ("mezzo", "Mezzosoprano"),
              ("alto", "Contralto"), ("tenor", "Tenor"), ("baritone", "Barítono"),
              ("bass", "Bajo")),
    "banda": (("flute", "Flauta"), ("oboe", "Oboe"), ("requinto", "Requinto"),
              ("clarinet", "Clarinete"), ("saxophone", "Saxofón"), ("trumpet", "Trompeta"),
              ("flugelhorn", "Fliscorno"), ("horn", "Trompa"), ("trombone", "Trombón"),
              ("euphonium", "Bombardino"), ("tuba", "Tuba"), ("percussion", "Percusión")),
    "orquesta": (("violin_1", "Violín I"), ("violin_2", "Violín II"), ("viola", "Viola"),
                  ("cello", "Violonchelo"), ("double_bass", "Contrabajo"), ("flute", "Flauta"),
                  ("oboe", "Oboe"), ("clarinet", "Clarinete"), ("bassoon", "Fagot"),
                  ("horn", "Trompa"), ("trumpet", "Trompeta"), ("trombone", "Trombón"),
                  ("tuba", "Tuba"), ("percussion", "Percusión"), ("harp", "Arpa")),
    "grupo": (),
    "ensemble": (),
}
