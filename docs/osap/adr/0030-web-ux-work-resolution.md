# ADR-0030 – Cliente Web: Work Resolution e Identidad Visual (V3.4)

## Estado

Aceptado. Congela la UX del cliente web centrada en la **Work Resolution** (V3.4).

## Principios

- **OpenMusicRepository es la marca visible; OSAP es el motor** ("powered by OSAP").
- **La Work Resolution es la entidad central** de la experiencia, y es un **recurso**
  (`id`, confidence, work, candidate works, representations, evidence, actions).
- **Product First**: la interfaz muestra primero el valor del producto; la administración
  queda al final.
- **Search es una acción global** (Header), no una página.
- **Progressive Disclosure** y **Workspace**: la resolución se descubre poco a poco y es
  un espacio de trabajo, no un *search result*.
- **Explainability**: todo resultado puede ser explicado (matcher/ranking/merge/evidence).
- La web **nunca habla con el dominio**; toda comunicación pasa por `ApiClient`.

## Contexto

V3.3 construyó la arquitectura del cliente web (ApiClient, Routing, Layout, Components,
State, Design System) sin identidad de producto. V3.4 convierte la web en una plataforma
de **inteligencia musical**: resolver una obra y explicar por qué esa resolución es la
correcta.

## Decisión

- **Branding**: OpenMusicRepository + "Music Intelligence Platform", OSAP como motor.
- **Header permanente**: logo, **buscador global**, selector de idioma, modo oscuro,
  usuario (placeholder).
- **Home** (no Dashboard): Hero + buscador + Recent searches / Most accessed / Recently
  added / Repository status.
- **Work Resolution Workspace**: Nivel 1 (obra + confidence + representaciones), Nivel 2
  (representaciones por proveedor), obras candidatas ordenadas por confianza, **Why this
  result?**, y **Actions** (download, view, compare, explain, open, bookmark, share,
  report).
- **Navigation**: Home · Discover · Knowledge; Administración secundaria; breadcrumb
  semántico.
- **Providers** como tarjetas; **Knowledge** en lenguaje funcional.
- **Design System** ampliado: modo oscuro, iconografía única, tokens, componentes
  accesibles (WCAG AA).
- **Responsive mobile-first**, **preferencias persistentes**, **vacíos elegantes**.
- **i18n**: es, ca, fr, en, de; sin texto hardcodeado.

## Consecuencias

- La web deja de parecer un panel administrativo y pasa a ser una plataforma de
  inteligencia musical.
- La arquitectura V3.3 y la API V3.1 **no cambian**; solo se amplía la capa de
  presentación y el Design System.
- La resolución como **recurso** permitirá compartir/guardar/comparar/exportar sin cambiar
  el contrato.
- V3.5 (Autenticación) y V3.6 (Administración) se construyen sobre esta base.
