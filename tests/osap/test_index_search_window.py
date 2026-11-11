from src.osap.infrastructure.catalogs.index.index_catalog_provider import IndexCatalogProvider


def test_index_provider_keeps_a_wide_candidate_window():
    """Una ventana de 400 dejaba fuera obras válidas en búsquedas amplias por título."""
    provider = IndexCatalogProvider()
    assert provider._max_results == 2000
