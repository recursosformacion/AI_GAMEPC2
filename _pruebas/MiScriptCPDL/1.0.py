import requests
import json
import time

API_URL = "https://www.cpdl.org/wiki/api.php"
EXPORT_URL = "https://www.cpdl.org/wiki/index.php/Special:Export"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def obtener_todos_los_titulos():
    """Obtiene la lista completa de títulos de páginas de CPDL mediante paginado con apfrom/apcontinue."""
    print("Obteniendo la lista completa de títulos de CPDL...")
    titulos = []
    apcontinue = None
    
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "aplimit": "max",  # Máximo por llamada API (generalmente 500)
            "format": "json"
        }
        if apcontinue:
            params["apcontinue"] = apcontinue

        res = requests.get(API_URL, headers=headers, params=params)
        if res.status_code != 200:
            print(f"Error al consultar la API: {res.status_code}")
            break

        data = res.json()
        pages = data.get("query", {}).get("allpages", [])
        for page in pages:
            titulos.append(page["title"])

        # Verificar si hay más páginas (paginado)
        if "continue" in data and "apcontinue" in data["continue"]:
            apcontinue = data["continue"]["apcontinue"]
            print(f"Obtenidos {len(titulos)} títulos hasta ahora...")
            time.sleep(0.5) # Pausa amigable para el servidor
        else:
            break

    print(f"¡Total de páginas encontradas en CPDL: {len(titulos)}!")
    return titulos

def descargar_xml_por_bloques(titulos, tamano_bloque=4000):
    """Envía peticiones POST en lotes menores a 5,000 para evitar el límite de truncado."""
    for i in range(0, len(titulos), tamano_bloque):
        bloque = titulos[i:i + tamano_bloque]
        numero_lote = (i // tamano_bloque) + 1
        print(f"Descargando bloque {numero_lote} ({len(bloque)} páginas)...")

        payload = {
            "pages": "\n".join(bloque), # MediaWiki acepta lista de títulos separados por salto de línea
            "curonly": "1"              # Solo la versión actual
        }

        res = requests.post(EXPORT_URL, headers=headers, data=payload)
        
        if res.status_code == 200:
            nombre_archivo = f"cpdl_dump_lote_{numero_lote}.xml"
            with open(nombre_archivo, "wb") as f:
                f.write(res.content)
            print(f"Guardado '{nombre_archivo}' con éxito.")
        else:
            print(f"Error en bloque {numero_lote}: HTTP {res.status_code}")

# Ejecución
if __name__ == "__main__":
    todos_los_titulos = obtener_todos_los_titulos()
    if todos_los_titulos:
        descargar_xml_por_bloques(todos_los_titulos, tamano_bloque=4000)