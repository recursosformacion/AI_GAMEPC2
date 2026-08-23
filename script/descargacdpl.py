import json
import os
import time
from playwright.sync_api import sync_playwright

URL_BASE = "https://www.cpdl.org/wiki/api.php"

def extraer_cpdl_playwright():
    todos_los_registros = []
    limit = 200
    offset = 0
    mas_resultados = True

    print("Iniciando navegador para superar el Cloudflare Challenge...", flush=True)

    with sync_playwright() as p:
        # Lanzamos un navegador Chromium visible o headless
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Primera visita a la home para pasar el reto de Cloudflare y obtener cookies válidas
        print("Superando la validacion inicial de Cloudflare...", flush=True)
        page.goto("https://www.cpdl.org/wiki/index.php/Main_Page", wait_until="domcontentloaded")
        time.sleep(3)  # Espera para que valide el token/cookie

        while mas_resultados:
            print(f"Solicitando bloque desde offset {offset}...", flush=True)
            
            api_url = f"{URL_BASE}?action=cargoquery&tables=Works&fields=_pageName=Pagina,Title=Titulo,Composer=Compositor,Genre=Genero,Subgenre=Subgenero,MusicXML=MusicXML&limit={limit}&offset={offset}&format=json"

            try:
                response = page.goto(api_url)
                if response.status == 200:
                    content_text = page.locator("body").inner_text()
                    data = json.loads(content_text)

                    items = data.get("cargoquery", [])
                    cant = len(items)
                    print(f"   -> Obtenidos {cant} registros.", flush=True)

                    for item in items:
                        row = item.get("title", {})
                        pagina = row.get("Pagina", "")
                        musicxml_val = row.get("MusicXML", "") or ""

                        todos_los_registros.append({
                            "pagina": pagina,
                            "titulo": row.get("Titulo"),
                            "compositor": row.get("Compositor"),
                            "genero": row.get("Genero"),
                            "subgenero": row.get("Subgenero"),
                            "tiene_musicxml": bool(musicxml_val.strip()),
                            "url_cpdl": f"https://www.cpdl.org/wiki/index.php/{pagina.replace(' ', '_')}"
                        })

                    if cant < limit:
                        mas_resultados = False
                    else:
                        offset += limit
                        time.sleep(1)
                else:
                    print(f"[ERROR] HTTP status {response.status}. Reintentando...", flush=True)
                    time.sleep(5)

            except Exception as e:
                print(f"[ERROR] {e}. Reintentando...", flush=True)
                time.sleep(5)

        browser.close()

    return todos_los_registros

if __name__ == "__main__":
    datos = extraer_cpdl_playwright()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    archivo_salida = os.path.join(script_dir, "cpdl_bbdd_completa.json")

    with open(archivo_salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print(f"\n¡Proceso completado! Archivo guardado en:\n   {archivo_salida}")