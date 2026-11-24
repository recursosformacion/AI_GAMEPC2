# OSAP API — OpenMusicRepository

**OSAP (Open Score Acquisition Platform)** powers the public catalogue and resource-discovery website **OpenMusicRepository**.

- **Production website:** https://app.openmusicrepository.com/
- **Source repository:** https://github.com/recursosformacion/AI_GAMEPC2
- **Documentation index:** [docs/README.md](docs/README.md)

OSAP helps musicians, choirs, educators and researchers discover musical works, explore catalogue information, compare editions and representations, and reach the source or file that is actually available.

## What this repository contains

This repository contains the OSAP API, the public React web application, the federated search/index layer, SEO-rendered public catalogue pages, and integration clients for the OSAP services.

It is not the authoritative store for every catalogue record or physical file. Those responsibilities are separated into the dedicated services below.

## OSAP service boundaries

| Repository | Responsibility |
|---|---|
| **[AI_GAMEPC2](https://github.com/recursosformacion/AI_GAMEPC2)** | Public web application, API orchestration, federated search/index and integration with OSAP services |
| **[AI_osap-auth](https://github.com/recursosformacion/AI_osap-auth)** | User identity, authentication, OAuth/OIDC and service-to-service tokens |
| **[AI_osap-storage](https://github.com/recursosformacion/AI_osap-storage)** | Authoritative catalogue data, musical resources and file access |
| **[AI_osap-support](https://github.com/recursosformacion/AI_osap-support)** | Donations, memberships, recognitions and support-related operations |
| **[ai-importacion](https://github.com/recursosformacion/ai-importacion)** | Independent discovery, inventory and review of music materials |
| **[ai_recogeYouTube](https://github.com/recursosformacion/ai_recogeYouTube)** | Discovery and review of YouTube recordings associated with musical works |
| **[ai_noticias](https://github.com/recursosformacion/ai_noticias)** | News discovery and editorial feed consumed by OSAP |
| **[ai_publicidad](https://github.com/recursosformacion/ai_publicidad)** | Campaign management, ad composition, impressions and click-through |

Each service has its own configuration, database responsibilities, tests and deployment procedure. The API consumes service contracts; the public browser client must not bypass the API to access protected service databases or internal endpoints.

## Current architecture (6.x)

- **Web client:** React + TypeScript, built into `web/dist`.
- **SSR:** Node process (`web/ssr/server.mjs`) renders public work, composer, representation and classification pages on port 3000.
- **API:** FastAPI application composed through `src/osap/api/platform_app.py` and its platform/router layers.
- **Public routes:** Nginx sends canonical catalogue pages to Node SSR; legacy aliases and Los Amigos pages are handled by FastAPI.
- **Authentication:** user sessions and tokens are issued by osap-auth.
- **Service authentication:** API-to-service calls use dedicated OAuth2 client-credentials tokens with receiver-specific audiences and scopes.
- **Catalogue and files:** osap-storage is the authoritative service for catalogue records and stored files.
- **Support operations:** osap-support has its own authentication and persistence boundary.

The deployed website displayed **v6.4.1** on 2026-11-24. That visible version is evidence for the public web application only; it does not, by itself, certify the deployed revision or configuration of every backend service.

### Current catalogue model vs V6 target

The deployed code still uses the existing Work/index/Representation/resource/file structures and their current API contracts. The proposed V6 model **Work → Resource → File** is a future coordinated remodel, not a claim that production has already migrated. See [the V6 plan](docs/osap/v6-work-resource-model.md).

OMR is the repository presented to users. Data already integrated into OMR is consulted through OMR; it is not exposed as a separate repository that users need to configure.

## Development

Read [the development environment guide](docs/osap/dev-environment.md) before starting services or changing the frontend. The documented local workflow uses Apache for the SPA, Node SSR on port 3000 for canonical public pages, and FastAPI for `/api` and legacy/social routes. Rebuild both `web/dist` and `web/dist-ssr` with `script/restart-dev.ps1 -Build`.

Useful references:

- [Documentation index](docs/README.md)
- [OSAP documentation map](docs/osap/README.md)
- [Versioning and release rules](docs/osap/versioning.md)
- [Service-to-service authentication matrix](docs/osap/m2m-service-matrix.md)
- [Operational scripts](docs/osap/scripts.md)
- [Public user manual](web/public/manual/es/index.html)

## Verification and production safety

- Run the relevant tests and quality checks before committing.
- Treat migration and deployment scripts as potentially state-changing; inspect their target environment before execution.
- Do not use production credentials in development or commit secrets.
- Do not run production migrations, write production data, or deploy without explicit authorization.
- A successful API health endpoint is necessary but not sufficient: verify the actual user workflows and service-to-service operations.

## Licence

See [LICENSE](LICENSE) and the licence notices for third-party material and providers.
