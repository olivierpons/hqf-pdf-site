import tomllib
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from api_keys.models import ApiKey
from api_keys.server_config import (
    _nginx_string,
    _toml_basic_string,
    render_clients_toml,
    render_nginx_map,
)

FONT_STORE = Path("/srv/fonts")


class TestTomlString:
    def test_a_plain_path_is_just_quoted(self):
        assert _toml_basic_string("/srv/fonts/acme") == '"/srv/fonts/acme"'

    def test_a_backslash_and_a_quote_are_escaped(self):
        assert _toml_basic_string('a\\b"c') == '"a\\\\b\\"c"'


class TestNginxString:
    def test_a_bearer_token_is_just_quoted(self):
        assert _nginx_string("Bearer sk_live_x") == '"Bearer sk_live_x"'

    def test_a_quote_is_escaped(self):
        assert _nginx_string('a"b') == '"a\\"b"'


class TestRenderClientsToml:
    def make(self, **fields):
        fields.setdefault("client_name", "acme")
        fields.setdefault("allowed_to_use_its_own_fonts", False)
        fields.setdefault("max_pages", None)
        return ApiKey(**fields)

    def test_a_bare_client_carries_only_the_font_flag(self):
        toml = render_clients_toml([self.make()], FONT_STORE)
        assert "[clients.acme]" in toml
        assert "allowed_to_use_its_own_fonts = false" in toml
        assert "max_pages" not in toml
        assert "font_dir" not in toml

    def test_a_page_cap_is_written_as_a_bare_integer(self):
        toml = render_clients_toml([self.make(max_pages=50)], FONT_STORE)
        assert "max_pages = 50" in toml

    def test_a_client_allowed_its_own_fonts_gets_a_font_dir_named_for_it(self):
        toml = render_clients_toml(
            [self.make(allowed_to_use_its_own_fonts=True)], FONT_STORE
        )
        assert 'font_dir = "/srv/fonts/acme"' in toml

    def test_a_bare_client_gets_no_font_dir_the_server_would_reject(self):
        toml = render_clients_toml([self.make()], FONT_STORE)
        assert "font_dir" not in toml

    def test_the_output_is_valid_toml_the_server_could_parse(self):
        keys = [
            self.make(client_name="acme", allowed_to_use_its_own_fonts=True),
            self.make(client_name="beta", max_pages=10),
        ]
        parsed = tomllib.loads(render_clients_toml(keys, FONT_STORE))
        assert parsed["clients"]["acme"]["allowed_to_use_its_own_fonts"] is True
        assert parsed["clients"]["acme"]["font_dir"] == "/srv/fonts/acme"
        assert parsed["clients"]["beta"]["max_pages"] == 10
        assert parsed["clients"]["beta"]["allowed_to_use_its_own_fonts"] is False

    def test_no_keys_yields_a_parseable_file_with_no_clients(self):
        parsed = tomllib.loads(render_clients_toml([], FONT_STORE))
        assert parsed.get("clients", {}) == {}

    def test_clients_come_out_sorted_so_the_file_is_stable(self):
        keys = [self.make(client_name="zulu"), self.make(client_name="alpha")]
        toml = render_clients_toml(keys, FONT_STORE)
        assert toml.index("[clients.alpha]") < toml.index("[clients.zulu]")


class TestRenderNginxMap:
    def make(self, client_name, key):
        return ApiKey(client_name=client_name, key=key)

    def test_a_key_is_matched_with_its_bearer_prefix(self):
        text = render_nginx_map([self.make("acme", "sk_live_abc")])
        assert '"Bearer sk_live_abc" acme;' in text

    def test_an_unknown_caller_falls_to_the_empty_string(self):
        text = render_nginx_map([])
        assert 'default "";' in text
        assert text.strip().startswith("# ")

    def test_the_block_opens_and_closes(self):
        text = render_nginx_map([self.make("acme", "sk_live_abc")])
        assert "map $http_authorization $pdf_client {" in text
        assert text.rstrip().endswith("}")

    def test_clients_come_out_sorted_so_the_file_is_stable(self):
        keys = [self.make("zulu", "sk_live_z"), self.make("alpha", "sk_live_a")]
        text = render_nginx_map(keys)
        assert text.index("zulu;") > text.index("alpha;")


@pytest.mark.django_db
class TestWriteCommand:
    def paths(self, tmp_path, settings):
        clients = tmp_path / "clients.toml"
        nginx = tmp_path / "clients.map"
        settings.PDF_SERVER_CLIENTS_FILE = clients
        settings.PDF_SERVER_NGINX_MAP_FILE = nginx
        settings.PDF_SERVER_FONT_STORE_DIR = tmp_path / "fonts"
        return clients, nginx

    def test_it_writes_both_files_from_the_live_keys(self, account, tmp_path, settings):
        clients, nginx = self.paths(tmp_path, settings)
        ApiKey.objects.create(
            account=account,
            client_name="acme",
            key="sk_live_abc",
            allowed_to_use_its_own_fonts=True,
            max_pages=50,
        )
        call_command("write_pdf_server_config")

        parsed = tomllib.loads(clients.read_text())
        assert parsed["clients"]["acme"]["max_pages"] == 50
        assert parsed["clients"]["acme"]["font_dir"] == str(tmp_path / "fonts" / "acme")
        assert '"Bearer sk_live_abc" acme;' in nginx.read_text()

    def test_a_revoked_key_leaves_both_files(self, account, tmp_path, settings):
        clients, nginx = self.paths(tmp_path, settings)
        key = ApiKey.objects.create(
            account=account, client_name="acme", key="sk_live_abc"
        )
        key.revoke()
        call_command("write_pdf_server_config")

        assert "[clients.acme]" not in clients.read_text()
        assert "sk_live_abc" not in nginx.read_text()

    def test_rewriting_unchanged_keys_is_byte_identical(
        self, account, tmp_path, settings
    ):
        clients, nginx = self.paths(tmp_path, settings)
        ApiKey.objects.create(account=account, client_name="acme", key="sk_live_abc")
        call_command("write_pdf_server_config")
        first = clients.read_text(), nginx.read_text()
        call_command("write_pdf_server_config")
        assert (clients.read_text(), nginx.read_text()) == first

    def test_dry_run_writes_no_file(self, account, tmp_path, settings):
        clients, nginx = self.paths(tmp_path, settings)
        ApiKey.objects.create(account=account, client_name="acme", key="sk_live_abc")
        out = StringIO()
        call_command("write_pdf_server_config", "--dry-run", stdout=out)
        assert not clients.exists()
        assert not nginx.exists()
        assert "[clients.acme]" in out.getvalue()

    def test_it_makes_one_query_for_the_keys(self, account, tmp_path, settings):
        self.paths(tmp_path, settings)
        ApiKey.objects.create(account=account, client_name="acme", key="sk_live_abc")
        with CaptureQueriesContext(connection) as ctx:
            call_command("write_pdf_server_config")
        selects = [q for q in ctx.captured_queries if "api_keys" in q["sql"].lower()]
        assert len(selects) == 1
