from pathlib import Path


def test_development_routes_canonical_representation_pages_to_node_ssr() -> None:
    htaccess = Path("web/public/.htaccess").read_text(encoding="utf-8")

    assert "^(composers|obras|representacion)/(.*)$ http://127.0.0.1:3000/$1/$2" in htaccess
    assert "^(obra|compositor)/(.*)$ http://127.0.0.1:8001/$1/$2" in htaccess


def test_production_routes_canonical_representation_pages_to_node_ssr() -> None:
    nginx = Path("deploy/app.openmusicrepository.com.conf").read_text(encoding="utf-8")

    assert "location ^~ /representacion/" in nginx
    assert "proxy_pass http://127.0.0.1:3000;" in nginx
