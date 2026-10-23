# Espacios para anunciantes y patrocinadores

El componente `web/src/components/SponsorSlot.tsx` pinta un espacio reservado en las fichas
públicas. Si no hay patrocinadores activos muestra un texto de captación; si los hay, muestra
sus banners. La configuración vive en `web/public/sponsors.json`, que se sirve como fichero
estático (`/sponsors.json`). **Cambiar ese fichero en producción no requiere recompilar**: el
componente lo lee en cada carga.

## Dónde está
- `work`: debajo de las representaciones de una obra.
- `composer`: debajo de las obras de un compositor.
- `composers`: al final del listado de compositores.

## Formato

```json
{
  "house": {
    "title": "Espacio para anunciantes y patrocinadores",
    "text": "¿Tienes una tienda de partituras, una editorial, un coro...?",
    "cta": "Contacta con nosotros",
    "url": "/corrections?kind=contact"
  },
  "placements": {
    "work": {
      "label": "Patrocinado por",
      "mode": "rotate",
      "rotateSeconds": 8,
      "sponsors": [
        {
          "id": "tienda-x",
          "name": "Tienda X",
          "text": "Partituras y material coral.",
          "url": "https://ejemplo.com",
          "image": "/sponsors/tienda-x.png",
          "active": true,
          "from": "2026-11-01",
          "to": "2027-01-31"
        }
      ]
    }
  }
}
```

- `mode: "rotate"` muestra un patrocinador cada `rotateSeconds` (varios en el mismo sitio).
- `mode: "stack"` muestra todos seguidos.
- `active: false`, `from` futuro o `to` pasado lo retiran sin borrar la entrada.
- `image` es opcional; si falta se usan las iniciales.
- Los enlaces se abren con `rel="sponsored noopener noreferrer"`.
- Si no hay ningún patrocinador activo, se muestra el bloque `house` (nuestro texto de
  captación).

## Añadir/retirar en producción

1. Editar `/home/ocw/openmusicrepository.com/app/sponsors.json` (mismo formato).
2. Recargar; no hay que reiniciar ni recompilar. El componente pide `no-cache`.

Para un patrocinador con imagen, subir el archivo a `app/sponsors/` y usar
`"image": "/sponsors/archivo.png"`.

## AdSense

El hueco es independiente del proveedor. Cuando se apruebe AdSense, se puede sustituir el
contenido del componente por la unidad de anuncio (respetando consentimiento/CMP) sin cambiar
la estructura de la página.
