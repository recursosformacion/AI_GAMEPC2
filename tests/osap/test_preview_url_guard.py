"""Guard SSRF de `preview_source` (ADR-0036): solo http(s) y fuera de rangos privados."""

from src.osap.api.platform import _validate_preview_url


def test_public_https_allowed() -> None:
    assert _validate_preview_url("https://example.com/scores.json") is None


def test_public_http_allowed() -> None:
    assert _validate_preview_url("http://example.com/data.json") is None


def test_public_ip_allowed() -> None:
    assert _validate_preview_url("https://93.184.216.34/x.json") is None


def test_unsupported_schemes_rejected() -> None:
    assert _validate_preview_url("file:///etc/passwd") is not None
    assert _validate_preview_url("ftp://example.com/x") is not None
    assert _validate_preview_url("gopher://example.com/_x") is not None


def test_private_and_loopback_ips_rejected() -> None:
    for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.0.1", "169.254.0.1", "::1", "fe80::1"):
        assert _validate_preview_url(f"https://{ip}/x.json") is not None, ip


def test_local_hostnames_rejected() -> None:
    for host in ("localhost", "myhost", "intranet", "nas.local", "db.internal", "svc.localhost"):
        assert _validate_preview_url(f"https://{host}/x.json") is not None, host


def test_empty_or_malformed_rejected() -> None:
    assert _validate_preview_url("") is not None
    assert _validate_preview_url("not a url") is not None
