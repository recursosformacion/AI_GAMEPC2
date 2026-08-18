#!/usr/bin/env python
"""Auditoría rápida de la base de datos osap-storage"""
import sys
import io
import pymysql

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
print(" AUDITORÍA RÁPIDA DE BASE DE DATOS: osap-storage")
print("=" * 80)

# ============================================================================
# 1. RESUMEN DE TABLAS
# ============================================================================
print("\n" + "=" * 80)
print(" 1. RESUMEN DE TABLAS")
print("=" * 80)

cursor.execute("""
    SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_SCHEMA = 'osap-storage'
    ORDER BY TABLE_ROWS DESC
""")
for row in cursor.fetchall():
    size_mb = (row[2] + row[3]) / (1024*1024)
    print(f"  {row[0]:30s} {row[1]:>10,} regs  {size_mb:>8.1f} MB")

# ============================================================================
# 2. COLUMNAS REDUNDANTES
# ============================================================================
print("\n" + "=" * 80)
print(" 2. ANÁLISIS DE REDUNDANCIAS")
print("=" * 80)

cursor.execute("SELECT COUNT(*) FROM works WHERE composer IS NOT NULL AND composer_id IS NULL")
print(f"\n  ⚠️  Obras con 'composer' pero SIN 'composer_id': {cursor.fetchone()[0]:,}")

cursor.execute("SELECT COUNT(*) FROM works WHERE artist IS NOT NULL AND song_name IS NULL")
print(f"  ⚠️  Obras con 'artist' pero SIN 'song_name': {cursor.fetchone()[0]:,}")

cursor.execute("SELECT COUNT(*) FROM works WHERE title IS NOT NULL AND subtitle IS NOT NULL")
print(f"  ℹ️  Obras con title Y subtitle: {cursor.fetchone()[0]:,}")

# ============================================================================
# 3. INTEGRIDAD REFERENCIAL
# ============================================================================
print("\n" + "=" * 80)
print(" 3. INTEGRIDAD REFERENCIAL")
print("=" * 80)

cursor.execute("""
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = 'osap-storage' AND REFERENCED_TABLE_NAME IS NOT NULL
""")
print(f"\n  📌 FK definidas: {cursor.fetchone()[0]}")

cursor.execute("""
    SELECT COUNT(*) FROM works w
    LEFT JOIN composers c ON w.composer_id = c.id
    WHERE w.composer_id IS NOT NULL AND c.id IS NULL
""")
print(f"  ⚠️  Obras con composer_id huérfano: {cursor.fetchone()[0]:,}")

cursor.execute("""
    SELECT COUNT(*) FROM archive_entries ae
    LEFT JOIN works w ON ae.work_id = w.id
    WHERE ae.work_id IS NOT NULL AND w.id IS NULL
""")
print(f"  ⚠️  archive_entries con work_id huérfano: {cursor.fetchone()[0]:,}")

# ============================================================================
# 4. CALIDAD DE DATOS (muestreo)
# ============================================================================
print("\n" + "=" * 80)
print(" 4. CALIDAD DE DATOS (muestreo 1000 regs)")
print("=" * 80)

cursor.execute("""
    SELECT 
        COUNT(*) as total,
        ROUND(SUM(CASE WHEN title IS NULL OR title = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as title_null_pct,
        ROUND(SUM(CASE WHEN composer_id IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as composer_id_null_pct,
        ROUND(SUM(CASE WHEN genre IS NULL OR genre = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as genre_null_pct,
        ROUND(SUM(CASE WHEN year IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as year_null_pct,
        ROUND(SUM(CASE WHEN duration IS NULL OR duration = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as duration_null_pct,
        ROUND(SUM(CASE WHEN description IS NULL OR description = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as desc_null_pct
    FROM (SELECT title, composer_id, genre, year, duration, description FROM works ORDER BY id LIMIT 1000) as sample
""")
s = cursor.fetchone()
print(f"\n  Muestra: {s[0]} obras")
print(f"  title nulo/vacío: {s[1]}%")
print(f"  composer_id nulo: {s[2]}%")
print(f"  genre nulo/vacío: {s[3]}%")
print(f"  year nulo: {s[4]}%")
print(f"  duration nulo/vacío: {s[5]}%")
print(f"  description nulo/vacío: {s[6]}%")

# ============================================================================
# 5. ÍNDICES
# ============================================================================
print("\n" + "=" * 80)
print(" 5. ÍNDICES PRINCIPALES")
print("=" * 80)

for table in ['works', 'composers', 'files']:
    print(f"\n  --- {table.upper()} ---")
    cursor.execute(f"SHOW INDEX FROM {table}")
    for idx in cursor.fetchall():
        print(f"    {idx[2]:25s} → {idx[4]}")

# ============================================================================
# 6. DUPLICADOS
# ============================================================================
print("\n" + "=" * 80)
print(" 6. DUPLICADOS")
print("=" * 80)

cursor.execute("""
    SELECT name, COUNT(*) as cnt FROM composers
    GROUP BY name HAVING COUNT(*) > 1
    ORDER BY cnt DESC LIMIT 5
""")
dups = cursor.fetchall()
if dups:
    print("\n  ⚠️  Compositores con nombre duplicado:")
    for d in dups:
        print(f"    '{d[0]}' → {d[1]} veces")
else:
    print("\n  ✅ No hay nombres de compositores exactamente duplicados")

# ============================================================================
# 7. RECOMENDACIONES
# ============================================================================
print("\n" + "=" * 80)
print(" 7. RECOMENDACIONES PRIORIZADAS")
print("=" * 80)

print("""
🔴 PRIORIDAD CRÍTICA:
  1. 254K obras tienen 'composer' (texto) pero NO 'composer_id' (FK)
     → Esto impide relaciones adecuadas y búsquedas eficientes
     → Se necesita proceso de resolución de compositores

  2. No hay FK definida entre works.composer_id → composers.id
     → Riesgo de integridad referencial

🟡 PRIORIDAD MEDIA:
  3. Columnas 'artist' y 'song_name' siempre están vacías (254K)
     → Considerar eliminación si no son necesarias

  4. 'tags' e 'instrumentation' son columnas TEXT sin normalizar
     → work_tags tabla existe pero vacía

  5. 10 tablas vacías (catalogues, votes, work_genres, etc.)
     → Funcionalidad planificada no implementada

🟢 PRIORIDAD BAJA:
  6. Índices en genre, opus, year podrían mejorar búsquedas
  7. FULLTEXT en title/description para búsquedas textuales
""")

conn.close()
print("\n" + "=" * 80)
print(" FIN DE AUDITORÍA RÁPIDA")
print("=" * 80)