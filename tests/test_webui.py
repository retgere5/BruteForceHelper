"""Tests for the local web interface: security checks, the JSON API and jobs."""
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

import PassGenerator as pg
import WordlistFixer as wf
from webui import server as webui

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never route via a proxy


class Client:
    def __init__(self, httpd):
        self.app = httpd.app
        self.base = f"http://127.0.0.1:{httpd.app.port}"

    def request(self, method, path, body=None, headers=None, token=True, raw=None):
        sent = {"X-Token": self.app.token} if token else {}
        data = raw
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            sent["Content-Type"] = "application/json"
        sent.update(headers or {})
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=sent)
        try:
            with _OPENER.open(req, timeout=15) as res:
                return res.status, res.headers, res.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read()

    def json(self, method, path, body=None, **kwargs):
        status, _, payload = self.request(method, path, body, **kwargs)
        return status, json.loads(payload or b"null")

    def wait(self, job_id, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status, job = self.json("GET", f"/api/jobs/{job_id}")
            assert status == 200
            if job["state"] != "running":
                return job
            time.sleep(0.05)
        raise AssertionError("job did not finish in time")


@pytest.fixture
def ui(tmp_path):
    httpd = webui.create_server(port=0, output_dir=str(tmp_path / "out"))
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield Client(httpd)
    httpd.shutdown()
    httpd.server_close()
    httpd.app.shutdown()


BIG_RUN = {"words": list("abcdefghijklmnop"), "max_length": 10}


# --- page and security ----------------------------------------------------------

def test_index_embeds_token_and_sets_csp(ui):
    status, headers, body = ui.request("GET", "/", token=False)
    assert status == 200
    assert ui.app.token.encode() in body
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Frame-Options"] == "DENY"


def test_static_files_are_whitelisted(ui):
    assert ui.request("GET", "/static/app.js", token=False)[0] == 200
    assert ui.request("GET", "/static/app.css", token=False)[0] == 200
    assert ui.request("GET", "/static/server.py", token=False)[0] == 404
    assert ui.request("GET", "/static/../server.py", token=False)[0] == 404


def test_bundled_fonts_are_served_locally(ui):
    for name in ("archivo-latin.woff2", "archivo-latin-ext.woff2"):
        status, headers, body = ui.request("GET", f"/static/fonts/{name}", token=False)
        assert status == 200
        assert headers["Content-Type"] == "font/woff2"
        assert body[:4] == b"wOF2"
    # only the whitelisted font files, nothing else from that folder
    assert ui.request("GET", "/static/fonts/OFL.txt", token=False)[0] == 404
    _, headers, _ = ui.request("GET", "/", token=False)
    assert "font-src 'self'" in headers["Content-Security-Policy"]


def test_api_requires_token(ui):
    assert ui.json("GET", "/api/meta", token=False)[0] == 403
    assert ui.json("GET", "/api/meta", token=False, headers={"X-Token": "wrong"})[0] == 403
    assert ui.json("GET", "/api/meta")[0] == 200


def test_foreign_host_header_is_refused(ui):
    # A DNS-rebinding page reaches 127.0.0.1 but keeps its own host name
    assert ui.request("GET", "/", token=False, headers={"Host": "evil.example"})[0] == 403
    assert ui.json("GET", "/api/meta", headers={"Host": "evil.example"})[0] == 403


def test_cross_origin_post_is_refused(ui):
    status, _ = ui.json("POST", "/api/generate/preview", {"words": ["a"]},
                        headers={"Origin": "http://evil.example"})
    assert status == 403


def test_json_endpoints_require_json(ui):
    status, _ = ui.json("POST", "/api/generate/preview", raw=b"words=a",
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert status == 415


@pytest.mark.parametrize("raw, expected", [
    ("../../etc/passwd", "passwd"),
    ("C:\\Windows\\win.ini", "win.ini"),
    ("CON.txt", "_CON.txt"),
    ("   ", "default.txt"),
    ("liste<>|.txt", "liste_.txt"),
    ("şifreler.txt", "şifreler.txt"),
])
def test_clean_filename(raw, expected):
    assert webui.clean_filename(raw, "default.txt") == expected


# --- generator ------------------------------------------------------------------

def test_meta_lists_every_filter(ui):
    status, meta = ui.json("GET", "/api/meta")
    assert status == 200
    names = [name for group in meta["groups"].values() for name in group]
    assert set(names) == set(wf.Settings.DEFAULT_FILTERS)
    assert set(meta["filter_text"]["en"]) >= set(names)
    assert meta["output_dir"] == ui.app.output_dir


def test_preview_matches_generator(ui):
    body = {"words": ["ab", "c"], "min_length": 2, "max_length": 5, "modifiers": {"uppercase": True}}
    status, data = ui.json("POST", "/api/generate/preview", body)
    assert status == 200
    mods = {key: key == "uppercase" for key in webui.MODIFIER_KEYS}
    assert data["estimate"] == pg.calculate_total_combinations(["ab", "c"], 2, 5, mods)
    assert data["sample"] == pg.preview_combinations(["ab", "c"], 2, 5, mods, count=webui.PREVIEW_LINES)


def test_preview_reports_huge_estimates_as_exponent(ui):
    status, data = ui.json("POST", "/api/generate/preview", {"words": list("abcdefghij"), "max_length": 40})
    assert status == 200
    assert data["estimate"] is None and data["exponent"] >= 39


@pytest.mark.parametrize("body, field", [
    ({"words": []}, "words"),
    ({"words": ["a\nb"]}, "words"),
    ({"words": ["a"], "min_length": 5, "max_length": 2}, "max_length"),
    ({"words": ["a"], "limit": 0}, "limit"),
    ({"words": ["a"], "dedup": "magic"}, "dedup"),
])
def test_generate_validation(ui, body, field):
    status, data = ui.json("POST", "/api/generate", body)
    assert status == 400 and data == {"error": "invalid", "field": field}


def test_generate_job_writes_same_lines_as_cli(ui, tmp_path):
    body = {"words": ["ab", "c", "ab"], "min_length": 1, "max_length": 4,
            "modifiers": {"capitalize": True, "leet": True}, "prefix": "x", "output": "mine.txt"}
    status, job = ui.json("POST", "/api/generate", body)
    assert status == 202 and job["state"] == "running"
    job = ui.wait(job["id"])
    assert job["state"] == "done", job

    reference = tmp_path / "ref.txt"
    pg.generate_and_save_combinations(["ab", "c", "ab"], str(reference), 1, 4, capitalize=True, leet=True,
                                      word_start="x", quiet=True)
    expected = reference.read_text(encoding="utf-8").splitlines()
    result = job["result"]
    produced = os.path.join(ui.app.output_dir, "mine.txt")
    assert result["file"]["path"] == produced
    with open(produced, encoding="utf-8") as f:
        assert f.read().splitlines() == expected
    assert result["written"] == len(expected)
    assert result["head"] == expected[:webui.HEAD_LINES]

    status, headers, data = ui.request(
        "GET", f"/api/files/{result['file']['id']}/download?token={ui.app.token}", token=False)
    assert status == 200 and data.decode("utf-8").splitlines() == expected
    assert headers["Content-Disposition"].startswith("attachment")


def test_output_names_never_overwrite(ui):
    paths = []
    for _ in range(2):
        _, job = ui.json("POST", "/api/generate", {"words": ["a"], "output": "../../list.txt"})
        paths.append(ui.wait(job["id"])["result"]["file"]["path"])
    assert [os.path.basename(p) for p in paths] == ["list.txt", "list-2.txt"]
    assert all(os.path.dirname(p) == ui.app.output_dir for p in paths)


def test_gzip_output(ui):
    _, job = ui.json("POST", "/api/generate", {"words": ["a", "b"], "gzip": True, "output": "pack.txt"})
    result = ui.wait(job["id"])["result"]
    assert result["file"]["name"] == "pack.txt.gz"
    assert result["head"][:2] == ["a", "b"]


def test_generate_can_be_stopped(ui):
    _, job = ui.json("POST", "/api/generate", BIG_RUN)
    time.sleep(0.3)
    status, _ = ui.json("POST", f"/api/jobs/{job['id']}/stop")
    assert status == 200
    job = ui.wait(job["id"])
    assert job["state"] == "stopped"
    assert job["result"]["stopped_by"] == "user"
    assert job["result"]["written"] > 0


def test_running_job_limit(ui, monkeypatch):
    monkeypatch.setattr(webui, "MAX_RUNNING_JOBS", 1)
    _, first = ui.json("POST", "/api/generate", BIG_RUN)
    status, data = ui.json("POST", "/api/generate", {"words": ["a"]})
    assert status == 429 and data["error"] == "busy"
    ui.json("POST", f"/api/jobs/{first['id']}/stop")
    ui.wait(first["id"])


# --- cleaner and analyzer -------------------------------------------------------

def test_clean_job_from_local_path(ui, tmp_path):
    src = tmp_path / "list.txt"
    src.write_text("123456\nStr0ngPass!\naaaa\nqwerty12\n", encoding="utf-8")
    status, data = ui.json("POST", "/api/files/local", {"path": f'"{src}"'})  # pasted with quotes
    assert status == 201 and data["file"]["origin"] == "local"
    body = {"file_id": data["file"]["id"], "stats": True, "output": "clean.txt",
            "filters": {"number_only": True, "repetitive_chars": True, "keyboard_patterns": True}}
    status, job = ui.json("POST", "/api/clean", body)
    assert status == 202
    job = ui.wait(job["id"])
    assert job["state"] == "done", job
    result = job["result"]
    assert (result["total"], result["remaining"]) == (4, 1)
    assert result["filters"]["keyboard_patterns"] == 1
    assert result["head"] == ["Str0ngPass!"]
    assert os.path.isfile(result["stats_file"]["path"])


def test_upload_then_analyze(ui, tmp_path):
    content = "a\nbb\n123456\nPass!\n"
    status, data = ui.json("POST", "/api/upload", raw=content.encode("utf-8"),
                           headers={"X-File-Name": "my%20list.txt", "Content-Type": "application/octet-stream"})
    assert status == 201
    info = data["file"]
    assert info["name"] == "my list.txt" and info["origin"] == "upload" and "path" not in info

    status, job = ui.json("POST", "/api/analyze", {"file_id": info["id"]})
    assert status == 202
    job = ui.wait(job["id"])
    assert job["state"] == "done", job
    reference = tmp_path / "ref.txt"
    reference.write_text(content, encoding="utf-8")
    expected = wf.analyze_wordlist(str(reference))
    stats = job["result"]["stats"]
    assert stats["total"] == expected["total"] == 4
    assert stats["length_counts"] == {str(k): v for k, v in expected["length_counts"].items()}

    # An upload is an input, not a result: it can't be downloaded back
    status = ui.request("GET", f"/api/files/{info['id']}/download?token={ui.app.token}", token=False)[0]
    assert status == 404


def test_unknown_ids_and_paths(ui):
    assert ui.json("GET", "/api/jobs/deadbeef")[0] == 404
    assert ui.json("POST", "/api/analyze", {"file_id": "deadbeef"})[0] == 404
    status, data = ui.json("POST", "/api/files/local", {"path": "Z:/definitely/missing.txt"})
    assert status == 404 and data["error"] == "file_missing"


# --- startup --------------------------------------------------------------------

def test_stale_upload_folders_are_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(webui.tempfile, "gettempdir", lambda: str(tmp_path))
    stale = tmp_path / (webui.UPLOAD_PREFIX + "old")
    fresh = tmp_path / (webui.UPLOAD_PREFIX + "new")
    unrelated = tmp_path / "keep-me"
    for folder in (stale, fresh, unrelated):
        folder.mkdir()
        (folder / "list.txt").write_text("a\n", encoding="utf-8")
    old = time.time() - webui.STALE_UPLOAD_SECONDS - 60
    os.utime(stale, (old, old))
    os.utime(unrelated, (old, old))
    webui.remove_stale_uploads()
    assert not stale.exists()
    assert fresh.exists() and unrelated.exists()


def test_busy_default_port_falls_back(monkeypatch, tmp_path):
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    taken = blocker.getsockname()[1]
    monkeypatch.setattr(webui, "DEFAULT_PORT", taken)
    httpd = webui.create_server(output_dir=str(tmp_path))
    try:
        assert httpd.app.port != taken
    finally:
        httpd.server_close()
        blocker.close()


def test_run_prints_link_and_opens_browser(monkeypatch, capsys, tmp_path):
    opened = []
    monkeypatch.setattr(webui.webbrowser, "open", lambda url: opened.append(url))
    monkeypatch.setattr(webui, "DEFAULT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(webui, "remove_stale_uploads", lambda: None)  # keep the real temp dir untouched

    def fake_serve(self, poll_interval=0.5):
        time.sleep(0.6)  # let the browser timer fire
        raise KeyboardInterrupt

    monkeypatch.setattr(webui.LocalServer, "serve_forever", fake_serve)
    webui.run(port=0, start_tab="clean")
    out = capsys.readouterr().out
    assert len(opened) == 1
    assert opened[0].startswith("http://127.0.0.1:") and opened[0].endswith("/#clean")
    assert opened[0] in out


# --- cleaning rules while generating ------------------------------------------------

def test_preview_with_rules(ui):
    body = {"words": ["a", "b"], "min_length": 4, "max_length": 4, "filters": ["repetitive_chars"]}
    status, data = ui.json("POST", "/api/generate/preview", body)
    assert status == 200
    assert "aaaa" not in data["sample"] and "bbbb" not in data["sample"]
    assert len(data["sample"]) == 14
    assert data["filtered"] is True and data["estimate"] == 16  # an upper bound while rules are on


def test_generate_with_rules_matches_cli(ui, tmp_path):
    body = {"words": ["a", "b"], "min_length": 4, "max_length": 4,
            "filters": ["repetitive_chars", "pattern_repetition"], "output": "ruled.txt"}
    status, job = ui.json("POST", "/api/generate", body)
    assert status == 202
    job = ui.wait(job["id"])
    assert job["state"] == "done", job

    reference = tmp_path / "ref.txt"
    pg.generate_and_save_combinations(["a", "b"], str(reference), 4, 4, quiet=True,
                                      filters=["repetitive_chars", "pattern_repetition"])
    expected = reference.read_text(encoding="utf-8").splitlines()
    with open(os.path.join(ui.app.output_dir, "ruled.txt"), encoding="utf-8") as f:
        assert f.read().splitlines() == expected
    result = job["result"]
    assert result["written"] == len(expected) == 12
    assert result["filtered_total"] == 4
    assert result["filtered"] == {"repetitive_chars": 2, "pattern_repetition": 2}
    assert job["progress"]["processed"] == 16 and job["progress"]["filtered"] == 4


@pytest.mark.parametrize("rules", [["nope"], "repetitive_chars", [1]])
def test_unknown_rule_rejected(ui, rules):
    body = {"words": ["a"], "filters": rules}
    status, data = ui.json("POST", "/api/generate/preview", body)
    assert status == 400 and data == {"error": "invalid", "field": "filters"}


def test_preview_reports_exact_size(ui):
    body = {"words": ["ab", "c"], "min_length": 2, "max_length": 5, "prefix": "x",
            "modifiers": {"capitalize": True}}
    status, data = ui.json("POST", "/api/generate/preview", body)
    assert status == 200
    assert data["bytes"] == pg.estimate_output_bytes(["ab", "c"], 2, 5, {"capitalize": True}, word_start="x")
