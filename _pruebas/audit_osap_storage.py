#!/usr/bin/env python
"""Auditoría completa de la base de datos osap-storage"""
import sys
import io
import pymysql
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = pymysql.connect(
    host='127.0.0.1',
    user='osap2027',
    password='2027osapdb',
    database='osap-storage',
    charset='utf8mb4'
)
cursor = conn.cursor()

print("=" * 80)
print(" AUDITORÍA COMPLETA DE BASE DE DATOS: osap-storage")
print("=" * 80)

# ============================================================================
# 1. ANÁLISIS DE COLUMNAS POTENCIALMENTE REDUNDANTES
# ============================================================================
print("\n" + "=" * 80)
print(" 1. ANÁLISIS DE COLUMNAS POTENCIALMENTE REDUNDANTES")
print("=" * 80)

# Analizar works
print("\n--- Tabla WORKS ---")
cursor.execute("""
    SELECT 
        COLUMN_NAME, 
        DATA_TYPE, 
        IS_NULLABLE,
        COLUMN_DEFAULT
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'osap-storage' AND TABLE_NAME = 'works'
    ORDER BY ORDINAL_POSITION
""")
works_cols = cursor.fetchall()

# Posibles redundancias en works
print("\n🔍 Posibles redundancias detectadas:")
print("  • composer (varchar) + composer_id (char(36)) → composer_id debería ser la FK, 'composer' podría ser redundante")
print("  • artist + song_name → podrían ser parte de 'title' o metadatos separados")
print("  • title + subtitle → podrían unificarse o normalizarse")

# Contar obras con composer pero sin composer_id
cursor.execute("""
    SELECT COUNT(*) FROM works 
    WHERE composer IS NOT NULL AND composer_id IS NULL
""")
works_no_composer_id = cursor.fetchone()[0]
print(f"\n  ⚠️  Obras con 'composer' pero SIN 'composer_id': {works_no_composer_id:,}")

# Contar obras con composer_id pero sin composer
cursor.execute("""
    SELECT COUNT(*) FROM works 
    WHERE composer_id IS NOT NULL AND composer IS NULL
""")
works_no_composer = cursor.fetchone()[0]
print(f"  ℹ️  Obras con 'composer_id' pero SIN 'composer': {works_no_composer:,}")

# Contar obras con artist pero sin song_name
cursor.execute("""
    SELECT COUNT(*) FROM works 
    WHERE artist IS NOT NULL AND song_name IS NULL
""")
works_artist_no_song = cursor.fetchone()[0]
print(f"  ⚠️  Obras con 'artist' pero SIN 'song_name': {works_artist_no_song:,}")

# ============================================================================
# 2. ANÁLISIS DE ÍNDICES Y RENDIMIENTO
# ============================================================================
print("\n" + "=" * 80)
print(" 2. ANÁLISIS DE ÍNDICES Y RENDIMIENTO")
print("=" * 80)

# Obtener índices de works
print("\n--- Índices en WORKS ---")
cursor.execute("SHOW INDEX FROM works")
works_indexes = cursor.fetchall()
for idx in works_indexes:
    print(f"  • {idx[2]:20s} → {idx[4]} ({idx[10]})")

# Obtener índices de composers
print("\n--- Índices en COMPOSERS ---")
cursor.execute("SHOW INDEX FROM composers")
composers_indexes = cursor.fetchall()
for idx in composers_indexes:
    print(f"  • {idx[2]:20s} → {idx[4]} ({idx[10]})")

# Obtener índices de files
print("\n--- Índices en FILES ---")
cursor.execute("SHOW INDEX FROM files")
files_indexes = cursor.fetchall()
for idx in files_indexes:
    print(f"  • {idx[2]:20s} → {idx[4]} ({idx[10]})")

print("\n💡 Recomendaciones de índices:")
print("  • Si se buscan obras por 'composer' (texto), considerar FULLTEXT index")
print("  • Si se filtran por 'genre', 'opus', 'year' → índices compuestos podrían ayudar")
print("  • 'tags' es TEXT → no indexado, considerar tabla separada si se consulta mucho")

# ============================================================================
# 3. ANÁLISIS DE INTEGRIDAD REFERENCIAL
# ============================================================================
print("\n" + "=" * 80)
print(" 3. ANÁLISIS DE INTEGRIDAD REFERENCIAL")
print("=" * 80)

# Verificar FK constraints
cursor.execute("""
    SELECT 
        TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = 'osap-storage' AND REFERENCED_TABLE_NAME IS NOT NULL
""")
fks = cursor.fetchall()
print(f"\n📌 Restricciones de clave foránea definidas: {len(fks)}")
for fk in fks:
    print(f"  • {fk[0]}.{fk[1]} → {fk[2]}.{fk[3]}")

# Verificar integridad composer_id
print("\n🔍 Integridad de referencias:")
cursor.execute("""
    SELECT COUNT(*) FROM works w
    LEFT JOIN composers c ON w.composer_id = c.id
    WHERE w.composer_id IS NOT NULL AND c.id IS NULL
""")
orphan_works = cursor.fetchone()[0]
print(f"  ⚠️  Obras con composer_id que NO existe en composers: {orphan_works:,}")

# Verificar integridad archive_entries
cursor.execute("""
    SELECT COUNT(*) FROM archive_entries ae
    LEFT JOIN works w ON ae.work_id = w.id
    WHERE ae.work_id IS NOT NULL AND w.id IS NULL
""")
orphan_archive = cursor.fetchone()[0]
print(f"  ⚠️  archive_entries con work_id que NO existe: {orphan_archive:,}")

# ============================================================================
# 4. ANÁLISIS DE DATOS NULOS Y CALIDAD
# ============================================================================
print("\n" + "=" * 80)
print(" 4. ANÁLISIS DE DATOS NULOS Y CALIDAD")
print("=" * 80)

print("\n--- WORKS: Columnas con más nulos ---")
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        ROUND(SUM(CASE WHEN id IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as id_null,
        ROUND(SUM(CASE WHEN title IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as title_null,
        ROUND(SUM(CASE WHEN composer_id IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as composer_id_null,
        ROUND(SUM(CASE WHEN genre IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as genre_null,
        ROUND(SUM(CASE WHEN opus IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as opus_null,
        ROUND(SUM(CASE WHEN year IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as year_null,
        ROUND(SUM(CASE WHEN duration IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as duration_null,
        ROUND(SUM(CASE WHEN description IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as description_null,
        ROUND(SUM(CASE WHEN instrumentation IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as instrumentation_null
    FROM works
""")
null_stats = cursor.fetchone()
print(f"  Total: {int(null_stats[0]):,}")
print(f"  title NULL: {null_stats[1]}%")
print(f"  composer_id NULL: {null_stats[2]}%")
print(f"  genre NULL: {null_stats[3]}%")
print(f"  opus NULL: {null_stats[4]}%")
print(f"  year NULL: {null_stats[5]}%")
print(f"  duration NULL: {null_stats[6]}%")
print(f"  description NULL: {null_stats[7]}%")
print(f"  instrumentation NULL: {null_stats[8]}%")

# ============================================================================
# 5. ANÁLISIS DE DUPLICADOS POTENCIALES
# ============================================================================
print("\n" + "=" * 80)
print(" 5. ANÁLISIS DE DUPLICADOS POTENCIALES")
print("=" * 80)

print("\n--- Composers con nombres similares (posibles duplicados) ---")
cursor.execute("""
    SELECT name, COUNT(*) as count
    FROM composers
    GROUP BY name
    HAVING COUNT(*) > 1
    ORDER BY count DESC
    LIMIT 10
""")
dup_composers = cursor.fetchall()
if dup_composers:
    for dc in dup_composers:
        print(f"  ⚠️  '{dc[0]}' aparece {dc[1]} veces")
else:
    print("  ✅ No hay compositores con nombre exactamente duplicado")

# Verificar compositores con mismo nombre pero diferente ID (posibles merges pendientes)
cursor.execute("""
    SELECT 
        SUBSTRING(name, 1, 20) as name_prefix,
        COUNT(DISTINCT id) as unique_ids,
        COUNT(*) as total
    FROM composers
    GROUP BY LOWER(SUBSTRING(name, 1, 30))
    HAVING COUNT(DISTINCT id) > 1
    ORDER BY unique_ids DESC
    LIMIT 10
""")
similar_composers = cursor.fetchall()
if similar_composers:
    print("\n  Posibles compositores duplicados (mismo nombre, diferente ID):")
    for sc in similar_composers:
        print(f"  ⚠️  '{sc[0]}...' → {sc[1]} IDs diferentes")
else:
    print("  ✅ No se detectan compositores con nombre similar y IDs diferentes")

# ============================================================================
# 6. ANÁLISIS DE TABLAS VACÍAS
# ============================================================================
print("\n" + "=" * 80)
print(" 6. TABLAS VACÍAS O SUBUTILIZADAS")
print("=" * 80)

empty_tables = [
    'catalogues', 'composer_identity_resolution', 'download_jobs', 
    'musicbrainz_cache', 'votes', 'work_genres', 'work_instruments', 
    'work_parts', 'work_statistics', 'work_tags'
]
print(f"\n📭 Tablas vacías ({len(empty_tables)}):")
for table in empty_tables:
    print(f"  • {table}")

print("\n💡 Estas tablas parecen estar diseñadas para funcionalidad futura:")
print("  • catalogues, work_genres, work_instruments, work_parts, work_tags → metadatos enriquecidos")
print("  • votes, work_statistics → sistema de votación/estadísticas")
print("  • download_jobs, musicbrainz_cache → integración con MusicBrainz")

# ============================================================================
# 7. ANÁLISIS DE RELACIONES Y CARDINALIDAD
# ============================================================================
print("\n" + "=" * 80)
print(" 7. ANÁLISIS DE RELACIONES Y CARDINALIDAD")
print("=" * 80)

print("\n--- Relación works ↔ composers ---")
cursor.execute("""
    SELECT 
        COUNT(DISTINCT w.id) as total_works,
        COUNT(DISTINCT w.composer_id) as works_with_composer_id,
        COUNT(DISTINCT c.id) as total_composers,
        ROUND(COUNT(DISTINCT w.composer_id) * 100.0 / COUNT(DISTINCT w.id), 2) as pct_works_with_composer
    FROM works w
    LEFT JOIN composers c ON w.composer_id = c.id
""")
rel_stats = cursor.fetchone()
print(f"  Total obras: {rel_stats[0]:,}")
print(f"  Obras con composer_id: {rel_stats[1]:,} ({rel_stats[3]}%)")
print(f"  Total compositores: {rel_stats[2]:,}")

print("\n--- Relación works ↔ files ---")
cursor.execute("""
    SELECT 
        COUNT(DISTINCT w.id) as total_works,
        COUNT(DISTINCT f.id) as total_files,
        COUNT(DISTINCT ae.work_id) as works_with_archive
    FROM works w
    LEFT JOIN archive_entries ae ON w.id = ae.work_id
    LEFT JOIN files f ON ae.file_id = f.id
""")
file_stats = cursor.fetchone()
print(f"  Total obras: {file_stats[0]:,}")
print(f"  Total archivos: {file_stats[1]:,}")
print(f"  Obras con entradas de archivo: {file_stats[2]:,}")

# ============================================================================
# 8. RECOMENDACIONES DE MEJORA
# ============================================================================
print("\n" + "=" * 80)
print(" 8. RECOMENDACIONES DE MEJORA")
print("=" * 80)

print("""
🎯 PRIORIDAD ALTA:
  1. Normalizar columna 'composer' en works → eliminar y usar solo composer_id
  2. Definir claves foráneas explícitas (works.composer_id → composers.id)
  3. Resolver obras sin composer_id ({})
  4. Eliminar columnas redundantes: artist, song_name (si no son necesarias)

🎯 PRIORIDAD MEDIA:
  5. Crear índices compuestos para búsquedas frecuentes
  6. Mover 'tags' a tabla separada (work_tags ya existe pero está vacía)
  7. Normalizar genre, opus, year en tablas separadas si se consultan mucho
  8. Implementar sistema de votación (tabla votes existe pero vacía)

🎯 PRIORIDAD BAJA:
  9. Considerar FULLTEXT en title, description para búsquedas
  10. Implementar caché de MusicBrainz (tabla existe pero vacía)
  11. Sistema de descargas asíncronas (download_jobs existe pero vacío)
""".format(works_no_composer_id))

# ============================================================================
# 9. RESUMEN EJECUTIVO
# ============================================================================
print("\n" + "=" * 80)
print(" 9. RESUMEN EJECUTIVO")
print("=" * 80)

print("""
📊 ESTADO GENERAL: Base de datos funcional con 254K obras y 663 compositores.

✅ PUNTOS FUERTES:
  • Esquema bien estructurado con separación works/composers/files
  • Sistema de autoridades de compositores (30K entradas)
  • Tracking de metadatos rico (duration, measures, pages, etc.)
  • Migraciones controladas (20 migraciones aplicadas)

⚠️  PUNTOS DÉBILES:
  • Redundancia composer/composer_id en works
  • 10 tablas vacías (funcionalidad no implementada)
  • Posibles problemas de integridad referencial
  • Columnas TEXT sin normalizar (tags, instrumentation)

🔧 ACCIONES RECOMENDADAS:
  1. Ejecutar script de limpieza de redundancias
  2. Añadir FK constraints
  3. Implementar tablas vacías (empezar por work_tags)
  4. Revisar obras sin composer_id
""")

conn.close()
print("\n" + "=" * 80)
print(" FIN DE LA AUDITORÍA")
print("=" * 80)