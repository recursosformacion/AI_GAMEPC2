from src.osap.infrastructure.http import HttpClient


class TestHttpClientBuildUrl:
    def test_build_url_with_params(self) -> None:
        url = HttpClient.build_url("https://api.example.org", "/path", {"a": "1", "b": "dos palabras"})
        assert url == "https://api.example.org/path?a=1&b=dos+palabras"
