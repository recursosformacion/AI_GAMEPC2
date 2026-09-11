"""PlatformApi: mixin de providers/admin operativo (F5.4)."""


from src.osap.api.contracts import (
    ProviderResponse,
)
from src.osap.api.platform import _support as _support
from src.osap.api.platform._support import (
    _known_formats_for,
    _remote_online,
    _replace_provider_description,
)
from src.osap.api.platform.core import PlatformApiCore

VERSION = "3.1"














class ProvidersMixin(PlatformApiCore):
    def list_providers(self) -> list[ProviderResponse]:
        # `index` y `local` son proveedores internos (índice local / disco): no se
        # muestran como fuentes al usuario.
        responses = [
            self._provider_response(provider)
            for provider in self._container.catalog_manager().providers()
            if provider.provider_id.value not in ("index", "local")
        ]
        active_ids = {r.provider_id for r in responses}
        for pid, name, _base_url, wired in self._container.defined_providers():
            if pid in active_ids or pid in ("local", "index"):
                continue
            responses.append(
                ProviderResponse(
                    provider_id=pid,
                    name=name,
                    available=wired,
                    formats=_known_formats_for(pid),
                    last_sync=None,
                )
            )
        # Descripción multi-idioma + website desde la BD operativa.
        try:
            enrich: dict[str, tuple[dict[str, str], str | None]] = {}
            for row in self._store.list_providers():
                pid = str(row.get("provider_id"))
                desc = row.get("description")
                clean: dict[str, str] = {}
                if isinstance(desc, dict):
                    clean = {str(k): str(v) for k, v in desc.items() if isinstance(v, str)}
                base_url = row.get("base_url")
                website = str(base_url) if base_url else None
                if clean or website:
                    enrich[pid] = (clean, website)
        except Exception:  # noqa: BLE001
            enrich = {}
        for i, r in enumerate(responses):
            if r.provider_id in enrich:
                clean, website = enrich[r.provider_id]
                responses[i] = _replace_provider_description(r, clean, website)
        return responses

    def get_provider(self, provider_id: str) -> ProviderResponse | None:
        for provider in self._container.catalog_manager().providers():
            if provider.provider_id.value == provider_id:
                return self._provider_response(provider)
        return None

    @staticmethod
    def _provider_response(provider: object) -> ProviderResponse:
        capabilities = provider.capabilities()  # type: ignore[attr-defined]
        availability = str(capabilities.metadata.get("availability") or "")
        available = availability != "index_missing"
        info = provider.metadata()  # type: ignore[attr-defined]
        provider_id = provider.provider_id.value  # type: ignore[attr-defined]
        name = "OpenMusicRepository" if provider_id == "openmusicrepository" else info.name
        if provider_id == "openmusicrepository":
            # The OpenMusicRepository provider is the storage repository: online if its
            # Provider API (version endpoint) responds.
            available = _remote_online("https://storage.openmusicrepository.com/api/v1/health")
        return ProviderResponse(
            provider_id=provider_id,
            name=name,
            available=available,
            formats=[f.value for f in capabilities.formats],
            last_sync=None,
        )

    # --- votes & statistics (v1) --------------------------------------------

    def list_op_providers(self, token: str | None) -> list[dict[str, object]]:
        self._require_admin(token)
        return self._store.list_providers()

    def upsert_op_provider(
        self,
        token: str | None,
        provider_id: str,
        name: str,
        base_url: str | None,
        wired: bool,
        config: dict[str, object],
        description: dict[str, str] | None = None,
        endpoints: dict[str, object] | None = None,
        mapping: dict[str, object] | None = None,
        resources: dict[str, object] | None = None,
        transforms: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self._require_admin(token)
        return self._store.upsert_provider(
            provider_id, name, base_url=base_url, wired=wired, kind="dynamic",
            config=config, description=description, endpoints=endpoints,
            mapping=mapping, resources=resources, transforms=transforms,
        )

    def delete_op_provider(self, token: str | None, provider_id: str) -> bool:
        self._require_admin(token)
        return self._store.delete_provider(provider_id)

    def set_op_provider_wired(self, token: str | None, provider_id: str, wired: bool) -> dict[str, object] | None:
        self._require_admin(token)
        return self._store.set_provider_wired(provider_id, wired)

    def get_op_config(self, token: str | None) -> dict[str, object]:
        self._require_admin(token)
        out: dict[str, object] = {}
        for key in (
            "deployment",
            "dev_mode",
            "imslp_base_url",
            "library_root",
            "default_output_format",
            "default_quality_level",
        ):
            value = self._store.get_config(key)
            if value is not None:
                out[key] = value
        return out

    def set_op_config(self, token: str | None, key: str, value: str) -> dict[str, object]:
        self._require_admin(token)
        self._store.set_config(key, value)
        return {"key": key, "value": value}

    # --- knowledge (read-only) ----------------------------------------------

