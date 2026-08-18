#!/usr/bin/env python
"""Script para revisar la base de datos osap-storage"""
import sys
import io
import pymysql

# Configurar stdout para soportar UTF-8 en Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = pymysql.connect(
    host='127.0.0.1',
    user='osap2027',
    password='2027osapdb',
    database='osap-storage',
    charset='utf8mb4'
)
cursor = conn.cursor()

tables = [
    'archive_entries', 'archives', 'catalogues', 'composer_aliases',
    'composer_authority', 'composer_authority_names', 'composer_evidence',
    'composer_identifiers', 'composer_identity_resolution', 'composer_merge_history',
    'composers', 'download_jobs', 'files', 'import_sources', 'musicbrainz_cache',
    'schema_migrations', 'statistics', 'statistics_runs', 'storage_locations',
    'storage_providers', 'votes', 'work_genres', 'work_instruments', 'work_parts',
    'work_statistics', 'work_tags', 'works'
]

print("=" * 60)
print("BASE DE DATOS: osap-storage")
print("=" * 60)

print("\n=== CONTEO DE REGISTROS POR TABLA ===\n")
for table in tables:
    cursor.execute(f'SELECT COUNT(*) FROM {table}')
    count = cursor.fetchone()[0]
    print(f"  {table:35s} {count:>10,}")

print("\n=== ESTRUCTURA DE TABLAS PRINCIPALES ===\n")
for table in ['works', 'composers', 'files', 'catalogues']:
    print(f"--- Tabla: {table} ---")
    cursor.execute(f'DESCRIBE {table}')
    for col in cursor.fetchall():
        key_info = col[3] if col[3] else ''
        null_info = 'NULL' if col[2] == 'YES' else 'NOT NULL'
        default_info = f"DEFAULT {col[4]}" if col[4] is not None else ''
        print(f"  {col[0]:25s} {col[1]:20s} {null_info:10s} {key_info:5s} {default_info}")
    print()

print("\n=== ÚLTIMOS REGISTROS EN WORKS ===\n")
cursor.execute('SELECT id, title, composer_id, created_at FROM works ORDER BY id DESC LIMIT 5')
for row in cursor.fetchall():
    print(f"  id={row[0]}, title='{row[1][:50]}', composer_id={row[2]}, created_at={row[3]}")

print("\n=== ÚLTIMOS REGISTROS EN COMPOSERS ===\n")
cursor.execute('SELECT id, name, birth_year, death_year FROM composers ORDER BY id DESC LIMIT 5')
for row in cursor.fetchall():
    print(f"  id={row[0]}, name='{row[1][:50]}', birth_year={row[2]}, death_year={row[3]}")

print("\n=== MIGRACIONES DE ESQUEMA ===\n")
cursor.execute('SELECT id, name, applied_at FROM schema_migrations ORDER BY id DESC LIMIT 10')
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} - {row[2]}")

conn.close()
print("\n=== FIN DEL REPORTE ===")