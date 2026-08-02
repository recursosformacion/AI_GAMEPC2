from pathlib import Path

from src.osap.domain.errors import ResourceUnavailableError
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.infrastructure.catalogs.pdmx import PdmxCatalogProvider

_CSV = (
    "title,subtitle,composer_name,artist_name,license,license_conflict,rating,genres,"
    "song_length.seconds,song_length.bars,has_lyrics,n_notes,notes_per_bar,"
    "subset:no_license_conflict,mxl,pdf,mid\n"
    "Ave verum corpus,,Wolfgang Amadeus Mozart,Mozart,publicdomain,False,4.5,classical,"
    "120,40,True,300,7.5,True,./mxl/1/1/x.mxl,./pdf/1/1/x.pdf,./mid/1/1/x.mid\n"
    "Nocturne in E-flat,,Frederic Chopin,Chopin,publicdomain,False,4.8,classical,"
    "300,80,False,800,10.0,True,./mxl/2/2/y.mxl,./pdf/2/2/y.pdf,./mid/2/2/y.mid\n"
    "Ave Maria,,Franz Schubert,Schubert,publicdomain,True,3.0,classical,"
    "150,50,True,400,8.0,False,./mxl/3/3/z.mxl,,\n"
)


def _provider(tmp_path: Path) -> PdmxCatalogProvider:
    csv_file = tmp_path / "pdmx.csv"
    csv_file.write_text(_CSV, encoding="utf-8")
    provider = PdmxCatalogProvider(index_path=tmp_path / "index.db", local_csv=csv_file)
    provider.sync()
    return provider


class TestPdmxCatalogProvider:
    def test_search_by_composer(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)
        candidates = provider.search(ResolveRequest(composer="Mozart"))
        assert len(candidates) >= 1
        assert "Mozart" in (candidates[0].work_descriptor.composer or "")
        assert candidates[0].format == OutputFormat.MUSICXML

    def test_search_by_title(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)
        candidates = provider.search(ResolveRequest(title="Nocturne"))
        assert len(candidates) == 1
        assert candidates[0].work_descriptor.title == "Nocturne in E-flat"

    def test_search_by_format(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)
        candidates = provider.search(ResolveRequest(title="Ave Maria", desired_format=OutputFormat.MUSICXML))
        assert all(c.format == OutputFormat.MUSICXML for c in candidates)

    def test_no_match(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)
        assert provider.search(ResolveRequest(title="Sinfonia")) == ()

    def test_download_without_base_unavailable(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)
        candidate = provider.search(ResolveRequest(composer="Mozart"))[0]
        try:
            provider.download(candidate)
            raise AssertionError("expected ResourceUnavailableError")
        except ResourceUnavailableError:
            pass

    def test_download_from_mirror(self, tmp_path: Path) -> None:
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        mxl_bytes = b"PK\x03\x04 fake-mxl-content"

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path.startswith("/mxl/"):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.end_headers()
                    self.wfile.write(mxl_bytes)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args: object) -> None:  # noqa: ARG002
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            csv_file = tmp_path / "pdmx.csv"
            csv_file.write_text(_CSV, encoding="utf-8")
            provider = PdmxCatalogProvider(
                index_path=tmp_path / "index2.db",
                local_csv=csv_file,
                download_base=f"http://127.0.0.1:{port}",
            )
            provider.sync()
            candidate = provider.search(ResolveRequest(composer="Mozart"))[0]
            acquisition = provider.download(candidate)
            assert acquisition.source.content == mxl_bytes
            assert acquisition.source.format == OutputFormat.MUSICXML
        finally:
            server.shutdown()
            server.server_close()

    def test_download_validates_invalid_content(self, tmp_path: Path) -> None:
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"NOT A VALID MXL")

            def log_message(self, *args: object) -> None:  # noqa: ARG002
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            port = server.server_address[1]
            csv_file = tmp_path / "pdmx.csv"
            csv_file.write_text(_CSV, encoding="utf-8")
            provider = PdmxCatalogProvider(
                index_path=tmp_path / "index3.db",
                local_csv=csv_file,
                download_base=f"http://127.0.0.1:{port}",
            )
            provider.sync()
            candidate = provider.search(ResolveRequest(composer="Mozart"))[0]
            try:
                provider.download(candidate)
                raise AssertionError("expected ResourceUnavailableError")
            except ResourceUnavailableError:
                pass
        finally:
            server.shutdown()
            server.server_close()

    def test_metadata(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)
        assert provider.metadata().catalog_id.value == "pdmx"
        assert provider.provider_id.value == "pdmx"
