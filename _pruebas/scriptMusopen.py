import requests

# Búsqueda por término (ejemplo: Schubert)
url = "https://musopen.org/api/v1/music/"
params = {
    "q": "Schubert",
    "type": "piece"  # 'piece' para obras, 'composer' para compositores
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    data = response.json()
    # La API interna devuelve un JSON con los resultados
    for item in data.get('results', []):
        print(f"Obra: {item.get('title')}")
        print(f"Compositor: {item.get('composer', {}).get('name')}")
        print(f"URL relativa: https://musopen.org{item.get('url')}")
        print("-" * 50)
else:
    print(f"Error {response.status_code}")