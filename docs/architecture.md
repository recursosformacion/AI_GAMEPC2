# OSAP — architecture (consolidado)


## Parte: OSAP_Architecture_Book.md

---

# OSAP — Architecture Book

## Documento general del aplicativo

**Versión:** 3.x  
**Estado:** arquitectura en evolución  
**Propósito:** presentar OSAP como un sistema completo, sus componentes, responsabilidades, contratos, flujo de información y evolución.

---

# 1. Resumen ejecutivo

OSAP es una plataforma orientada a la búsqueda, integración, normalización y resolución de información musical procedente de múltiples proveedores.

La idea central es separar claramente:

- **los proveedores**, que conocen sus propios datos y recursos;
- **OSAP-API**, que integra y normaliza esa información;
- **OSAP-Storage**, que actúa como proveedor de información y recursos;
- **OSAP-Auth**, previsto como aplicación independiente para identidad y usuarios;
- **el frontend**, que consume los servicios de OSAP sin conocer estructuras físicas de almacenamiento.

OSAP no debe depender de la estructura interna de un repositorio concreto. Un proveedor puede ser REST, MediaWiki, GitHub, filesystem u otra fuente especializada. La información que obtiene OSAP pasa después por su propio proceso de normalización, canonicalización, matching, ranking y resolución.

---

# 2. La arquitectura conceptual

```text
                       ┌──────────────────────┐
                       │      Usuarios        │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │      Frontend        │
                       └───────┬───────┬──────┘
                               │       │
                         ┌─────▼───┐ ┌─▼────────┐
                         │OSAP-API │ │ OSAP-Auth │
                         └────┬────┘ └──────────┘
                              │
                 ┌────────────┴────────────┐
                 │                         │
                 ▼                         ▼
          Proveedores externos       OSAP-Storage
          OMR / IMSLP / ...          información + recursos
```

La frontera fundamental es:

> **Storage proporciona información; API interpreta, integra y resuelve.**

---

# 3. OSAP-Storage

OSAP-Storage es un proveedor.

Su responsabilidad es conocer la información disponible en su repositorio y devolverla de forma suficientemente completa para que OSAP-API no tenga que reconstruirla mediante múltiples llamadas.

Storage conoce:

- las obras que tiene indexadas;
- la metadata disponible;
- los alias;
- los recursos físicos asociados a cada Work;
- las estadísticas que realmente mantenga;
- dónde están físicamente los ficheros;
- cómo generar sus enlaces de descarga.

Storage no conoce:

- Matching Works;
- Work Resolution;
- Relationships;
- Knowledge Hub;
- lógica de matching de OSAP;
- Canonicalizer de OSAP;
- ranking de OSAP.

## Principio de Work autocontenida

Una llamada normal de búsqueda debe poder devolver una Work suficientemente completa para que OSAP-API pueda iniciar su proceso sin ejecutar un patrón N+1.

```text
GET /api/search?q=mozart
        │
        ▼
   Works completas
        │
        ▼
     OSAP-API
        │
        ▼
Canonicalización → Matching → Ranking → Resolución
```

Existe además una consulta ligera para casos en los que solo sea necesario localizar candidatos.

```text
GET /api/lookup?q=mozart
```

`lookup` devuelve únicamente:

- id
- title
- composer
- catalogue
- confidence

También existe el servicio de detalle:

```text
GET /api/resource/{id}
```

que devuelve una única Work completa.

La descarga es responsabilidad del proveedor:

```text
GET /api/download/{resource_id}
```

Storage conoce CDN, R2, disco, IPFS, hashes y rutas físicas. Esos detalles no forman parte del modelo interno de OSAP-API.

---

# 4. OSAP-API

OSAP-API es la capa de integración y resolución.

Recibe información de proveedores y la transforma a su modelo interno.

## Responsabilidades

1. consultar proveedores;
2. recibir sus Works;
3. aplicar mapping;
4. normalizar los datos;
5. pasar las Works por Canonicalizer;
6. identificar candidatos equivalentes;
7. realizar matching;
8. aplicar ranking;
9. fusionar información cuando corresponde;
10. construir Work Resolution;
11. establecer Relationships;
12. exponer una API unificada;
13. gestionar votos y estadísticas de valoración de OSAP.

El proveedor no necesita conocer cómo funciona ninguna de estas capas.

---

# 5. Sistema declarativo de proveedores

La incorporación de proveedores debe evitar la creación de código específico siempre que sea posible.

La configuración de un proveedor se organiza mediante:

```text
providers/
    omr/
        provider.yaml
        endpoints.yaml
        mapping.yaml
        resources.yaml
```

## provider.yaml

Define la identidad y configuración general del proveedor.

## endpoints.yaml

Define:

- URL base;
- endpoints;
- método;
- parámetros;
- estructura de llamada;
- plantillas de consulta.

## mapping.yaml

Define la equivalencia entre los campos que devuelve el proveedor y el modelo Work de OSAP.

El mapping es la tabla de traducción entre ambos mundos.

Conceptualmente:

```text
campo proveedor
       │
       ▼
mapping
       │
       ▼
campo OSAP
```

El mapping pertenece al proveedor y es único para ese proveedor.

## resources.yaml

Define cómo se interpretan los recursos físicos que aparecen en la respuesta del proveedor.

No representa una segunda consulta: forma parte del conocimiento necesario para interpretar la Work recibida.

---

# 6. Proveedores de distintos tipos

No todos los proveedores tienen por qué ser REST.

La arquitectura contempla distintos niveles:

### Nivel 1 — proveedor declarativo

Cuando el proveedor ofrece una API REST suficientemente compatible:

```text
REST → JSON → mapping YAML → ProviderWork
```

### Nivel 2 — fetcher/adaptador ligero

Cuando el origen utiliza una API o protocolo particular:

```text
MediaWiki / GitHub / otra API
              │
              ▼
       JSON normalizado
              │
              ▼
          mapping
```

Esto permite reutilizar el mismo mecanismo de mapping sin obligar al proveedor externo a adoptar el contrato interno de OSAP.

### Nivel 3 — proveedor especializado

Para fuentes como filesystem o sistemas con lógica específica puede existir código propio.

La arquitectura no obliga artificialmente a que todas las fuentes sean REST.

---

# 7. Separación entre Work y Resource

Una Work representa conocimiento musical.

Un Resource representa un fichero o recurso físico que Storage sabe localizar.

La API de OSAP puede considerar los recursos como parte de la información que necesita para construir su modelo, pero Storage no necesita conocer el concepto de **Representation** de OSAP.

La separación conceptual es:

```text
Work
 ├── identidad
 ├── metadata
 ├── estadísticas disponibles
 └── resources
       ├── id
       ├── format
       ├── mime_type
       ├── available
       └── enlaces
```

OSAP-API puede transformar posteriormente esa información a su propio modelo interno.

---

# 8. Flujo principal

```text
Proveedor
   │
   │ Work completa
   ▼
Provider Adapter
   │
   ▼
ProviderWork
   │
   ▼
Canonicalizer
   │
   ▼
Matching
   │
   ▼
Ranking
   │
   ▼
Merge
   │
   ▼
Work Resolution
   │
   ▼
Relationships
   │
   ▼
Knowledge Hub / API / Frontend
```

El punto importante es que la Work obtenida del proveedor entra completa en el proceso de OSAP.

No debe existir una secuencia artificial:

```text
search → resource → metadata → representations → statistics
```

cuando el proveedor ya puede entregar toda la información en `search`.

---

# 9. Canonicalización

La información recibida de un proveedor no tiene por qué utilizar exactamente la terminología de OSAP.

Por ello:

```text
Work del proveedor
        │
        ▼
Mapping
        │
        ▼
ProviderWork
        │
        ▼
Canonicalizer
```

El Canonicalizer no pertenece al proveedor.

El proveedor únicamente entrega los datos que conoce.

---

# 10. Matching, ranking y fusión

Una vez recibidas las Works, OSAP puede comparar información procedente de diferentes fuentes.

Ejemplo:

```text
OMR ─────────────┐
                 │
IMSLP ───────────┼──► Matching
                 │
OpenScore ───────┘
                       │
                       ▼
                    Ranking
                       │
                       ▼
                      Merge
                       │
                       ▼
                Work Resolution
```

Esto permite que una misma obra pueda ser encontrada en distintos repositorios sin que ninguno de ellos tenga que conocer a los demás.

---

# 11. Compositores

A partir de la versión 3 se incorpora una gestión específica de compositores.

La base de compositores debe ser gestionada por **OSAP-Storage**.

Debe permitir:

- identidad del compositor;
- múltiples alias;
- nombres encontrados en diferentes proveedores;
- sinónimos;
- fusiones manuales;
- administración de compositores;
- conservación de las variantes históricas.

La aplicación dispondrá de una página de administración para revisar los compositores detectados y decidir fusiones cuando el sistema no pueda establecerlas automáticamente.

Los sinónimos también servirán como ayuda para interpretar futuras consultas y datos de proveedores.

---

# 12. Votaciones de obras

La valoración de obras pertenece a **OSAP-API**.

La propuesta funcional es:

- solo usuarios registrados pueden votar;
- un usuario puede emitir como máximo un voto al día;
- el voto se asocia a una obra;
- las votaciones se almacenan;
- un proceso nocturno calcula agregados;
- la valoración media de las obras de un compositor permite obtener una valoración del compositor.

Conceptualmente:

```text
Usuario registrado
        │
        ▼
      voto
        │
        ▼
      Work
        │
        ▼
proceso nocturno
        │
        ▼
estadísticas
        │
        ▼
valoración del compositor
```

Las reglas definitivas de cálculo de la valoración deberán quedar documentadas como parte del diseño funcional.

---

# 13. OSAP-Auth

La autenticación se plantea como una aplicación independiente:

```text
OSAP-Auth
```

Su función será gestionar:

- usuarios;
- identidad;
- autenticación;
- sesiones/tokens;
- autorización.

OSAP-API utilizará esa identidad para las funciones que requieran usuario registrado, como las votaciones.

OSAP-Storage no debe quedar expuesto directamente a Internet como un servicio de consumo general. El acceso externo debe estar protegido y controlado, aunque pueda existir acceso interno entre servicios.

---

# 14. Seguridad

La arquitectura de seguridad prevista es:

```text
Internet
   │
   ▼
Frontend / API pública
   │
   ├── OSAP-Auth
   │
   ├── OSAP-API
   │
   └── acceso controlado → OSAP-Storage
```

El hecho de que Storage sea accesible por OSAP-API no implica que deba ser accesible directamente por los usuarios.

Los secretos, credenciales y mecanismos internos del almacenamiento deben permanecer fuera del contrato público.

---

# 15. Estadísticas

Hay que distinguir dos conceptos.

## Estadísticas propias del proveedor

Storage puede conocer:

- descargas;
- visitas;
- favoritos;
- rating;

pero solo debe devolverlas si realmente las mantiene y puede construirlas.

No se deben declarar estadísticas ficticias simplemente porque el contrato tenga esos campos.

## Estadísticas de OSAP

OSAP-API puede construir sus propias estadísticas:

- votos;
- valoraciones;
- actividad;
- agregados;
- valoraciones de compositores.

Esto permite separar las métricas de un repositorio concreto de las métricas globales de OSAP.

---

# 16. Frontend

El frontend consume OSAP-API.

No debe conocer:

- hashes;
- rutas físicas;
- estructura de CDN;
- R2;
- filesystem;
- detalles de IMSLP;
- detalles de GitHub;
- lógica de proveedores.

El frontend trabaja con el modelo público de OSAP.

Entre sus futuras áreas funcionales:

- búsqueda;
- ficha de obra;
- recursos disponibles;
- compositores;
- valoración de obras;
- valoración de compositores;
- administración;
- autenticación.

---

# 17. Administración

La administración permitirá gestionar aquello que no debe quedar exclusivamente en manos de algoritmos.

Especialmente:

### Compositores

- listar todos;
- buscar;
- revisar alias;
- revisar sinónimos;
- fusionar compositores;
- corregir identificaciones.

### Proveedores

La configuración declarativa permitirá controlar:

- proveedor;
- endpoints;
- mappings;
- recursos.

### Calidad

La administración podrá servir posteriormente para revisar casos de matching ambiguos y mejorar los mappings.

---

# 18. Evolución de la arquitectura

OSAP ha ido evolucionando hacia una separación más clara de responsabilidades.

### Etapa inicial

Proveedores con lógica específica y acceso directo a sus fuentes.

### Etapa declarativa

Introducción de:

```text
provider.yaml
endpoints.yaml
mapping.yaml
resources.yaml
```

### V3

Separación entre:

- proveedor;
- integración;
- resolución;
- autenticación;
- almacenamiento;
- frontend.

### Evolución prevista

```text
V3
 │
 ├── proveedores declarativos
 ├── compositores
 ├── autenticación
 ├── votos
 ├── estadísticas
 └── administración
```

---

# 19. Principios arquitectónicos

## 1. El proveedor conoce sus datos

No se debe trasladar al proveedor la lógica de OSAP.

## 2. Storage entrega tanta información como conozca

Evitar N+1 cuando la información ya está disponible.

## 3. Lookup es opcional y ligero

Cuando solo se necesita localizar candidatos, existe una operación mínima.

## 4. Search es la operación principal

Para el pipeline de OSAP, `search` puede devolver Works completas.

## 5. Resource es un servicio de detalle

Permite obtener una única Work cuando alguien conoce su id o necesita ese servicio, pero no debe ser una fase obligatoria del pipeline de búsqueda.

## 6. Los recursos físicos son responsabilidad del proveedor

OSAP no construye URLs a partir de hashes o rutas.

## 7. Canonicalizer pertenece a OSAP

Todo proveedor termina entrando en el mismo proceso de normalización.

## 8. No introducir lógica superior en Storage

Storage no debe conocer Matching, Work Resolution o Knowledge Hub.

## 9. La configuración de proveedores debe ser declarativa siempre que sea posible

Agregar un proveedor REST compatible debería requerir configuración y mapping, no nuevo código.

## 10. Los servicios deben poder evolucionar independientemente

OSAP-Auth, OSAP-API y OSAP-Storage tienen responsabilidades separadas.

---

# 20. Estructura de proyecto

La consolidación del proyecto puede organizarse bajo una carpeta común:

```text
D:\Proyectos\AI\_OSAP\
    osap-api\
    osap-storage\
    osap-auth\
    ...
```

La carpeta común representa el aplicativo OSAP; cada componente mantiene su propio repositorio y ciclo de desarrollo.

---

# 21. Estado y documentación

Este documento debe actuar como **Architecture Book** del aplicativo.

No sustituye los contratos técnicos específicos de cada servicio.

La documentación se divide conceptualmente en:

```text
Architecture Book
        │
        ├── OSAP global
        │
        ├── osap-api
        │     └── contrato / arquitectura / API
        │
        ├── osap-storage
        │     └── contrato / proveedores / almacenamiento
        │
        └── osap-auth
              └── identidad / autenticación
```

Los documentos de implementación pueden evolucionar sin perder la visión global.

---

# 22. Glosario

**Work**  
Entidad musical que representa una obra y su información conocida.

**Resource**  
Recurso físico que puede descargarse o visualizarse.

**Provider**  
Fuente externa o interna que proporciona información musical.

**ProviderWork**  
Representación de una Work recibida y normalizada desde un proveedor antes del procesamiento interno de OSAP.

**Canonicalizer**  
Componente de OSAP que normaliza la información para permitir comparación e interpretación consistente.

**Matching**  
Proceso para determinar si distintas Works representan la misma obra.

**Ranking**  
Ordenación de candidatos según su relevancia o confianza.

**Merge**  
Fusión de información procedente de distintas fuentes.

**Work Resolution**  
Resultado de resolución construido por OSAP-API.

**Relationship**  
Relación entre entidades musicales identificada por OSAP.

**Knowledge Hub**  
Capa superior de conocimiento construida sobre las resoluciones.

**Lookup**  
Consulta ligera para localizar rápidamente candidatos.

**Mapping**  
Configuración que traduce los campos del proveedor al modelo de OSAP.

---

# 23. Resumen final

La arquitectura OSAP se basa en una idea sencilla:

> **Los proveedores aportan conocimiento; OSAP lo interpreta y lo integra.**

Storage conoce sus datos y sus ficheros.

Los proveedores externos conocen sus propias fuentes.

OSAP-API recibe la información y ejecuta el proceso común:

```text
Provider
   ↓
Work
   ↓
Mapping
   ↓
Canonicalizer
   ↓
Matching
   ↓
Ranking
   ↓
Merge
   ↓
Work Resolution
   ↓
Knowledge Hub
```

La autenticación, los usuarios, las votaciones y las funciones sociales se construyen como servicios separados, manteniendo la arquitectura modular.

El objetivo final es que incorporar nuevas fuentes de información no obligue a modificar el núcleo de OSAP y que la plataforma pueda crecer desde un conjunto de repositorios musicales hacia un sistema abierto de conocimiento musical.



## Parte: OSAP_Persistence_Architecture_v1.md

---

# OSAP — Arquitectura de Persistencia v1

**Estado:** CONGELADO v1.
**Alcance:** propiedad de las bases de datos, tablas por aplicación y qué datos pueden
cruzar entre aplicaciones (y cuáles están prohibidos).
**Complementa:** contratos de `osap-auth`, `osap-api` y `osap-storage`.

---

# 1. Regla fundamental

> **Cada aplicación es propietaria de sus datos y de su base de datos. Ninguna aplicación
> consulta directamente la base de datos de otra.**

La comunicación entre servicios se realiza **exclusivamente** mediante las APIs y contratos
definidos, **nunca** mediante acceso directo a la BD de otro servicio.

Esta regla convierte a osap-auth en un **Identity Provider interno** de OSAP: emite la
identidad (`user_id` UUID) y la provee a los demás servicios, sin que nadie toque su BD.

---

# 2. Modelo de bases de datos

Por simplicidad de despliegue, las tres BD pueden vivir **en el mismo servidor MySQL**
(inicialmente), pero siempre como **bases independientes**, con **usuarios MySQL
independientes**, **credenciales independientes** y **permisos mínimos** (cada servicio solo
puede operar sobre su propia BD).

```
MySQL server
│
├── osap_auth       → propietario: osap-auth
├── osap_api        → propietario: osap-api
└── osap_storage    → propietario: osap-storage
```

Posteriormente, si es necesario, se separan físicamente en hosts distintos
(`auth-db.example`, `api-db.example`, `storage-db.example`) **sin cambiar la arquitectura
de las aplicaciones**.

---

# 3. Propietarios y tablas

## osap_auth (propietario: osap-auth) — identidad y autenticación

| Tabla | Contenido |
|-------|-----------|
| `users` | identidad: `id` (UUID), `email_lookup` (HMAC), `email_cipher` (AEAD), `email_verified_at`, `password_hash` (Argon2id), `roles`, `status`, `key_version` |
| `sessions` | sesiones activas: `id` (jti), `user_id`, `refresh_token_hash`, `refresh_expires_at`, `created_at`, `last_used_at`, `revoked_at`, `ip`, `user_agent`, `device_label` |
| `refresh_tokens` | hashes de refresh tokens (opacos, rotados) |
| `verification` | tokens de verificación de email (un solo uso, caducan) |
| `password_reset` | tokens de recuperación de contraseña (un solo uso, caducan) |
| `service_clients` | clientes machine-to-machine: `client_id`, `client_secret_hash`, `scopes`, `enabled` |
| `audit` | auditoría de autenticación (append-only) |

## osap_api (propietario: osap-api) — lógica de aplicación

| Tabla | Contenido |
|-------|-----------|
| `votes` | `id`, `user_id` (UUID opaco), `work_id`, `vote`, `voted_at`, `vote_day`; `UNIQUE(user_id, vote_day, work_id)` |
| `works` (derivadas / resolución) | resultado de resolución, estadísticas de obras |
| `composer_ratings` | valoraciones agregadas de compositores |
| `work_ratings` | valoraciones agregadas de obras |
| otras tablas funcionales | estadísticas, resolución (Work Resolution), etc. |

## osap_storage (propietario: osap-storage) — catálogo y recursos

| Tabla | Contenido |
|-------|-----------|
| `works` | catálogo / metadata de obras |
| `composers` | compositores (identidad, alias, sinónimos) |
| `resources` | recursos físicos / ficheros |
| `download_urls` / rutas | localización de ficheros, enlaces de descarga |

---

# 4. Datos que pueden cruzar entre aplicaciones

| Origen → Destino | Dato permitido | Cómo viaja |
|------------------|----------------|------------|
| osap-auth → osap-api | `user_id` (UUID) | en el access token JWT (`sub`) y en `GET /auth/me` |
| osap-auth → osap-api | claims de identidad | JWT: `sub`, `jti`, `roles`, `email_verified`, `aud`, `exp` (sin PII) |
| osap-auth → osap-api | evento `user.deleted` | evento/webhook `{ user_id, deleted_at }` |
| osap-auth → osap-storage | nada | osap-storage no recibe identidad de usuario |
| osap-api → osap-storage | tokens de servicio | `client_credentials` con scope `storage:read` |
| osap-api → osap-auth | credenciales de servicio | `client_id` + `client_secret` (para obtener token) |
| osap-api → osap-auth | `user_id` para consultas | en `GET /auth/me`, `DELETE /auth/me`, etc. |

Solo viaja **`user_id` (UUID opaco)** entre osap-auth y osap-api. Entre osap-api y
osap-storage viajan **tokens de servicio**, nunca identidad de usuario.

---

# 5. Datos PROHIBIDOS de cruzar

Entre aplicaciones **NO pueden cruzar** (ni siquiera cifrados):

- `email` (ni en claro, ni `email_lookup`, ni `email_cipher`).
- contraseñas / hashes de contraseñas.
- refresh tokens y sus hashes.
- tokens de verificación / reset.
- datos personales (nombre, etc.) salvo lo que el usuario muestra vía API a sí mismo.
- estado interno de autenticación.
- cómo se cifra el email (claves, algoritmos internos).
- acceso directo a tablas de otra BD.

**Regla dura:** el email y cualquier dato personal **nunca** son identificador entre
aplicaciones. Si un servicio necesita el email del usuario, lo obtiene a través de
osap-auth (`GET /auth/me`) bajo demanda y **solo para mostrárselo al propio usuario**;
nunca lo almacena ni lo usa como clave.

---

# 6. `user_id` permanente

- Se **genera en osap-auth** en el registro (UUID).
- Es **permanente mientras exista la identidad**; no se reutiliza.
- Se replica (como UUID opaco) en `osap_api.votes.user_id` y en futuros servicios OSAP.
- Al eliminar la cuenta: osap-auth emite `user.deleted` → osap-api **anonimiza** el
  `user_id` en los votos (conservando el agregado estadístico) y **recalcula** las valoraciones.

---

# 7. Permisos y despliegue

- Cada servicio MySQL tiene **usuario y credenciales propios** limitados a su propia BD
  (permisos mínimos: CRUD sobre sus tablas, sin acceso a las de otros).
- Los secretos de BD se configuran por entorno (variables de entorno / secrets), nunca en
  el código ni en el contrato.
- La separación física (`auth-db.example`, etc.) es una decisión de despliegue **posterior**
  que no altera la arquitectura de las aplicaciones.

---

# 8. Consecuencias para los contratos existentes

- El contrato `osap-auth-api-v1.0.md` declara que osap-auth es **único propietario** de la
  BD de identidad y que `user_id` es permanente (sección "Persistencia y propiedad de datos").
- `authentication-integration-v1.md` declara que osap-api guarda votos en su BD propia con
  solo `user_id` opaco.
- `service-auth-v1.md` queda sin cambios (osap-storage no conoce usuarios).

---
*Arquitectura de persistencia de OSAP v1 (2026-08).*



## Parte: V3-architecture.md

---

V3-architecture.md
# OSAP V3 — Arquitectura y evolución

## 1. Objetivo

## 2. Componentes

### osap-auth
### osap-storage
### osap-api
### Aplicación

## 3. Autenticación y autorización

### Acceso público
### Acceso autenticado
### Administración
### Comunicación interna entre servicios

## 4. Compositores

### Modelo
### Aliases
### Sinónimos
### Fusión
### Administración

## 5. Votaciones

### Usuarios autorizados
### Regla de un voto diario
### Identificación de usuario
### Persistencia
### Protección contra duplicados

## 6. Estadísticas

### Estadísticas de obra
### Estadísticas de compositor
### Proceso nocturno
### Recalculación

## 7. API

### Cambios necesarios en osap-api
### Cambios necesarios en osap-storage
### Nuevos endpoints
### Autorización

## 8. Evolución del modelo

## 9. Plan de implementación

### Fase 1 — osap-auth
### Fase 2 — seguridad de servicios
### Fase 3 — compositores en osap-storage
### Fase 4 — integración de compositores en osap-api
### Fase 5 — votaciones
### Fase 6 — estadísticas
### Fase 7 — administración


## Parte: V3-architecture.md

---




