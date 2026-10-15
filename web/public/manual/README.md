# Manual de usuario de OSAP

## Estructura

- `es/`: versión castellana que debe revisarse y corregirse antes de traducir.
- `assets/manual.css`: estilos compartidos; las páginas son HTML estático independiente de React.
- Enlaces previstos para futuras traducciones: `ca/`, `en/`, `fr/` y `de/`, manteniendo los mismos nombres de página en cada idioma.

## Idioma y SEO

Cada página declara `<html lang="es">`, canonical propio y alternate `hreflang="es"`. Cuando se publiquen las traducciones, cada página deberá incluir un alternate por cada traducción realmente disponible (por ejemplo `ca`, `en`, `fr`, `de`) y un `x-default`. No se deben enlazar versiones de idioma que todavía no existan.

## Publicación

El contenido está en `web/public/manual/` para que Vite lo copie sin transformarlo a `web/dist/manual/`. Las páginas no dependen de React. La URL prevista es `/manual/es/`.

## Alcance y revisión

El texto se ha redactado a partir de las rutas, menús y páginas visibles en el código de `web/src`. Antes de considerar el manual definitivo, revisar el texto contra la instalación desplegada y confirmar los detalles que dependen de los servicios externos (storage, support, autenticación, proveedores y pagos). No incluir credenciales, tokens ni datos reales de usuarios.
