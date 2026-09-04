import requests

# Ejemplo: Manifiesto IIIF de un manuscrito en la BnF (Gallica)
manifest_url = "https://gallica.bnf.fr/iiif/ark:/12148/btv1b8451620h/manifest.json"

response = requests.get(manifest_url)
if response.status_code == 200:
    data = response.json()
    
    # Título de la obra
    title = data.get("label", "Sin título")
    print(f"Obra: {title}\n" + "-"*40)
    
    # Recorrer los Canvases (Lienzos) para extraer la imagen de cada página/hoja
    sequences = data.get("sequences", [])[0]
    canvases = sequences.get("canvases", [])
    
    for idx, canvas in enumerate(canvases, 1):
        # En IIIF v2 la imagen se encuentra en images[0]['resource']['@id']
        image_url = canvas["images"][0]["resource"]["@id"]
        print(f"Página {idx}: {image_url}")