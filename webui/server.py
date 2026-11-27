"""HTTP server and JSON API behind the web interface.

The server binds to 127.0.0.1 only. Every API call must carry the token that is
embedded in the page, and requests whose Host header is not the local address
are refused, so other sites open in the same browser cannot drive the tools.
Generation, cleaning and analysis run as background jobs that the page polls.
"""
import gzip
import hmac
import json
import math
import os
import re
import secrets
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from colorama import Fore, Style

import PassGenerator as pg
import WordlistFixer as wf
from modules.language_manager import LanguageManager
from modules.settings_manager import FilterRecommender, Settings

HOST = '127.0.0.1'
DEFAULT_PORT = 8765
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
STATIC_TYPES = {
    'app.css': 'text/css; charset=utf-8',
    'app.js': 'text/javascript; charset=utf-8',
    'favicon.svg': 'image/svg+xml',
    'fonts/archivo-latin.woff2': 'font/woff2',
    'fonts/archivo-latin-ext.woff2': 'font/woff2',
}
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, 'output')

MAX_JSON_BYTES = 1024 * 1024
MAX_RUNNING_JOBS = 3
MAX_WORDS = 200
MAX_WORD_CHARS = 100
MAX_LENGTH = 128
PREVIEW_LINES = 40
HEAD_LINES = 40
COPY_CHUNK = 1024 * 1024
EXACT_ESTIMATE_LIMIT = 10 ** 15
UPLOAD_PREFIX = 'bfh-uploads-'
STALE_UPLOAD_SECONDS = 6 * 3600

MODIFIER_KEYS = ('uppercase', 'capitalize', 'reverse', 'reverse_capitalize', 'reverse_upper', 'leet')
DEDUP_MODES = ('memory', 'disk', 'none')

SECURITY_HEADERS = (
    ('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; "
                                "font-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
                                "form-action 'none'; frame-ancestors 'none'"),
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('Referrer-Policy', 'no-referrer'),
    ('Cross-Origin-Opener-Policy', 'same-origin'),
    ('Cross-Origin-Resource-Policy', 'same-origin'),
    ('Cache-Control', 'no-store'),
)

_RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{i}' for p in ('COM', 'LPT') for i in range(1, 10)}
_DIGITS = re.compile(r'\d+', re.ASCII)


class ApiError(Exception):
    """An error sent back as JSON: {"error": code, "field": field}."""

    def __init__(self, status, code, field=None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.field = field


# --- input validation -------------------------------------------------------

def _int(value, field, low=1, high=None):
    """Optional whole number (int or digit string); None when left empty."""
    if value is None or value == '':
        return None
    if isinstance(value, str) and _DIGITS.fullmatch(value.strip()):
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(400, 'invalid', field)
    if value < low or (high is not None and value > high):
        raise ApiError(400, 'invalid', field)
    return value


def _text(value, field):
    """Optional single-line string, such as a prefix or suffix."""
    if value is None or value == '':
        return None
    if not isinstance(value, str) or len(value) > MAX_WORD_CHARS or '\n' in value or '\r' in value:
        raise ApiError(400, 'invalid', field)
    return value


def parse_generate(params):
    """Validate the generator form and map it onto PassGenerator's arguments."""
    words = params.get('words')
    if not isinstance(words, list) or not words or len(words) > MAX_WORDS:
        raise ApiError(400, 'invalid', 'words')
    for word in words:
        if not isinstance(word, str) or not word or len(word) > MAX_WORD_CHARS or '\n' in word or '\r' in word:
            raise ApiError(400, 'invalid', 'words')
    min_length = _int(params.get('min_length'), 'min_length', 1, MAX_LENGTH) or 1
    max_length = _int(params.get('max_length'), 'max_length', 1, MAX_LENGTH)
    if max_length is not None and min_length > max_length:
        raise ApiError(400, 'invalid', 'max_length')
    modifiers = params.get('modifiers') or {}
    if not isinstance(modifiers, dict):
        raise ApiError(400, 'invalid', 'modifiers')
    dedup = params.get('dedup') or 'memory'
    if dedup not in DEDUP_MODES:
        raise ApiError(400, 'invalid', 'dedup')
    filters = params.get('filters') or []
    if not isinstance(filters, list) or any(name not in pg.filter_rule_names() for name in filters):
        raise ApiError(400, 'invalid', 'filters')
    return {
        'filters': sorted(set(filters)),
        'words': list(words),
        'min_length': min_length,
        'max_length': max_length,
        'modifiers': {key: bool(modifiers.get(key)) for key in MODIFIER_KEYS},
        'word_start': _text(params.get('prefix'), 'prefix'),
        'word_end': _text(params.get('suffix'), 'suffix'),
        'limit': _int(params.get('limit'), 'limit'),
        'max_memory': _int(params.get('max_memory'), 'max_memory'),
        'dedup': dedup,
        'gzip': bool(params.get('gzip')),
        'output': params.get('output'),
    }


# --- files ------------------------------------------------------------------

def clean_filename(name, default):
    """A bare file name: no folders, no characters that are unsafe on disk."""
    if not isinstance(name, str):
        name = ''
    name = name.replace('\\', '/').split('/')[-1]
    name = re.sub(r'[^\w.\- ()]+', '_', name).strip(' .')[:120]
    if not name:
        name = default
    if name.split('.')[0].upper() in _RESERVED_NAMES:
        name = '_' + name
    return name


def output_filename(name, default, use_gzip=False):
    name = clean_filename(name, default)
    if '.' not in name:
        name += '.txt'
    if use_gzip and not name.lower().endswith('.gz'):
        name += '.gz'
    return name


def _split_ext(name):
    stem, ext = os.path.splitext(name)
    if ext.lower() == '.gz':
        inner_stem, inner_ext = os.path.splitext(stem)
        if inner_ext:
            return inner_stem, inner_ext + ext
    return stem, ext


def reserve_path(directory, name):
    """Create an empty `name` in `directory` (as name-2, name-3... when taken) and
    return its path, so results never overwrite an earlier file."""
    os.makedirs(directory, exist_ok=True)
    stem, ext = _split_ext(name)
    for n in range(1, 10000):
        candidate = name if n == 1 else f'{stem}-{n}{ext}'
        path = os.path.join(directory, candidate)
        try:
            with open(path, 'x'):
                pass
            return path
        except FileExistsError:
            continue
    raise ApiError(409, 'name_taken')


def _discard_if_empty(path):
    try:
        if os.path.getsize(path) == 0:
            os.remove(path)
    except OSError:
        pass


def read_head(path, count=HEAD_LINES):
    """First `count` lines of a (possibly gzipped) text file, for display."""
    lines = []
    try:
        if path.endswith('.gz'):
            handle = gzip.open(path, 'rt', encoding='utf-8', errors='replace')
        else:
            handle = open(path, 'r', encoding='utf-8', errors='replace')
        with handle:
            for line in handle:
                lines.append(line.rstrip('\r\n'))
                if len(lines) >= count:
                    break
    except (OSError, EOFError):
        pass
    return lines


def remove_stale_uploads(max_age=STALE_UPLOAD_SECONDS):
    """Delete upload copies left behind by a server that was not stopped with
    Ctrl+C (for example when its terminal window was closed)."""
    root = tempfile.gettempdir()
    now = time.time()
    try:
        names = os.listdir(root)
    except OSError:
        return
    for name in names:
        if not name.startswith(UPLOAD_PREFIX):
            continue
        path = os.path.join(root, name)
        try:
            if os.path.isdir(path) and now - os.path.getmtime(path) > max_age:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def reveal_in_file_manager(path):
    """Open the folder holding `path` in Explorer / Finder / the desktop file manager."""
    if sys.platform.startswith('win'):
        subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', '-R', path])
    else:
        subprocess.Popen(['xdg-open', os.path.dirname(path)])


# --- jobs -------------------------------------------------------------------

class Job:
    """A background run (generate / clean / analyze) that the page polls."""

    def __init__(self, kind):
        self.id = secrets.token_hex(8)
        self.kind = kind
        self.state = 'running'  # running | done | stopped | error
        self.progress = {}
        self.result = None
        self.error = None
        self.started = time.time()
        self.finished = None
        self.stop_event = threading.Event()
        self.thread = None
        self._lock = threading.Lock()

    def update(self, **values):
        with self._lock:
            self.progress.update(values)

    def finish(self, state, result=None, error=None):
        with self._lock:
            self.state = state
            self.result = result
            self.error = error
            self.finished = time.time()

    def to_dict(self):
        with self._lock:
            return {
                'id': self.id,
                'kind': self.kind,
                'state': self.state,
                'progress': dict(self.progress),
                'result': self.result,
                'error': self.error,
                'elapsed': (self.finished or time.time()) - self.started,
            }


class WebApp:
    """State shared by every request: the token, known files and jobs."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = os.path.abspath(output_dir)
        self.token = secrets.token_urlsafe(32)
        self.port = None
        self.jobs = {}
        self.files = {}
        self.upload_dir = None
        self._lock = threading.Lock()

    # files

    def add_file(self, path, origin):
        path = os.path.abspath(path)
        size = os.path.getsize(path)
        recommender = FilterRecommender()
        info = {
            'id': secrets.token_hex(8),
            'name': os.path.basename(path),
            'path': path,
            'size': size,
            'origin': origin,  # output | upload | local
            'suggest': [{'key': key, 'filters': recommender.common_combinations[key]}
                        for key, _ in recommender.get_recommendations(size)],
        }
        with self._lock:
            self.files[info['id']] = info
        return info

    def get_file(self, file_id, outputs_only=False):
        with self._lock:
            info = self.files.get(file_id) if isinstance(file_id, str) else None
        if info is None or (outputs_only and info['origin'] != 'output'):
            raise ApiError(404, 'not_found')
        if not os.path.isfile(info['path']):
            raise ApiError(404, 'file_missing')
        return info

    @staticmethod
    def public(info):
        data = {key: info[key] for key in ('id', 'name', 'size', 'origin', 'suggest')}
        if info['origin'] != 'upload':  # an upload's temp path means nothing to the user
            data['path'] = info['path']
        return data

    def save_upload(self, name, length, stream):
        with self._lock:
            if self.upload_dir is None:
                self.upload_dir = tempfile.mkdtemp(prefix=UPLOAD_PREFIX)
        folder = os.path.join(self.upload_dir, secrets.token_hex(4))
        os.makedirs(folder)
        path = os.path.join(folder, clean_filename(name, 'wordlist.txt'))
        remaining = length
        try:
            with open(path, 'wb') as out:
                while remaining > 0:
                    chunk = stream.read(min(COPY_CHUNK, remaining))
                    if not chunk:
                        break
                    out.write(chunk)
                    remaining -= len(chunk)
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        if remaining:
            shutil.rmtree(folder, ignore_errors=True)
            raise ApiError(400, 'incomplete_upload')
        return self.add_file(path, 'upload')

    def local_file(self, params):
        raw = params.get('path')
        if not isinstance(raw, str) or not raw.strip():
            raise ApiError(400, 'invalid', 'path')
        path = os.path.abspath(os.path.expanduser(raw.strip().strip('"\'')))
        if not os.path.isfile(path):
            raise ApiError(404, 'file_missing')
        return self.add_file(path, 'local')

    # jobs

    def start_job(self, kind, work):
        with self._lock:
            running = sum(1 for job in self.jobs.values() if job.state == 'running')
            if running >= MAX_RUNNING_JOBS:
                raise ApiError(429, 'busy')
            job = Job(kind)
            self.jobs[job.id] = job

        def target():
            try:
                result = work(job)
            except Exception as exc:  # shown in the page instead of the terminal
                job.finish('error', error=str(exc) or type(exc).__name__)
            else:
                job.finish('stopped' if job.stop_event.is_set() else 'done', result=result)

        job.thread = threading.Thread(target=target, name=f'bfh-{kind}-{job.id}', daemon=True)
        job.thread.start()
        return job

    def get_job(self, job_id):
        with self._lock:
            job = self.jobs.get(job_id)
        if job is None:
            raise ApiError(404, 'not_found')
        return job

    def meta(self):
        texts = LanguageManager().translations
        langs = ('tr', 'en')
        return {
            'output_dir': self.output_dir,
            'groups': Settings().get_filter_groups(),
            'filter_text': {lang: texts[lang]['filter_descriptions'] for lang in langs},
            'group_text': {lang: texts[lang]['filter_groups'] for lang in langs},
            'suggest_text': {lang: texts[lang]['filter_recommendations'] for lang in langs},
            'large_threshold': pg.LARGE_COMBINATION_WARNING,
            'limits': {'words': MAX_WORDS, 'word_chars': MAX_WORD_CHARS, 'length': MAX_LENGTH},
        }

    def preview(self, params):
        opts = parse_generate(params)
        estimate = pg.calculate_total_combinations(
            opts['words'], opts['min_length'], opts['max_length'], opts['modifiers'])
        size = pg.estimate_output_bytes(opts['words'], opts['min_length'], opts['max_length'], opts['modifiers'],
                                        opts['word_start'], opts['word_end'])
        if opts['limit'] and estimate > opts['limit']:
            size = size * opts['limit'] // estimate
            estimate = opts['limit']
        sample = pg.preview_combinations(
            opts['words'], opts['min_length'], opts['max_length'], opts['modifiers'],
            opts['word_start'], opts['word_end'], count=PREVIEW_LINES, dedup=opts['dedup'] != 'none',
            filters=opts['filters'])
        return {
            'estimate': estimate if estimate <= EXACT_ESTIMATE_LIMIT else None,
            'exponent': int(math.log10(estimate)) if estimate > 0 else 0,
            'sample': sample,
            'bytes': size,
            # with rules on, the estimate is only an upper bound
            'filtered': bool(opts['filters']),
        }

    def generate(self, params):
        opts = parse_generate(params)
        use_gzip = opts['gzip'] or str(opts['output'] or '').lower().endswith('.gz')
        path = reserve_path(self.output_dir, output_filename(opts['output'], 'combinations.txt', use_gzip))
        mods = opts['modifiers']

        def work(job):
            job.update(done=0, total=None, processed=0, filtered=0)
            live = {}

            def progress(written, total):
                job.update(done=written, total=total,
                           processed=live.get('processed', 0), filtered=live.get('filtered_total', 0))

            try:
                summary = pg.generate_and_save_combinations(
                    opts['words'], path, opts['min_length'], opts['max_length'],
                    uppercase=mods['uppercase'], capitalize=mods['capitalize'], reverse=mods['reverse'],
                    reverse_capitalize=mods['reverse_capitalize'], reverse_upper=mods['reverse_upper'],
                    leet=mods['leet'], word_start=opts['word_start'], word_end=opts['word_end'],
                    use_gzip=use_gzip, limit=opts['limit'],
                    max_memory_mb=opts['max_memory'] if opts['dedup'] == 'memory' else None,
                    dedup=opts['dedup'] != 'none', disk_dedup=opts['dedup'] == 'disk',
                    quiet=True, stop_event=job.stop_event, progress=progress,
                    filters=opts['filters'], live=live)
            except Exception:
                _discard_if_empty(path)
                raise
            info = self.add_file(path, 'output')
            return {
                'file': self.public(info),
                'written': summary['written'],
                'stopped_by': summary['stopped_by'],
                'filtered': summary['filtered'],
                'filtered_total': summary['filtered_total'],
                'skipped': summary['skipped'],
                'head': read_head(path),
            }

        return self.start_job('generate', work)

    def clean(self, params):
        source = self.get_file(params.get('file_id'))
        filters = params.get('filters') or {}
        if not isinstance(filters, dict):
            raise ApiError(400, 'invalid', 'filters')
        min_length = _int(params.get('min_length'), 'min_length', 1, 10 ** 6)
        max_length = _int(params.get('max_length'), 'max_length', 1, 10 ** 6)
        if min_length and max_length and min_length > max_length:
            raise ApiError(400, 'invalid', 'max_length')
        path = reserve_path(self.output_dir, output_filename(params.get('output'), 'optimized.txt'))
        options = {key: bool(filters.get(key)) for key in Settings.DEFAULT_FILTERS}
        options.update(input=source['path'], output=path, min_length=min_length,
                       max_length=max_length, keep_stats=bool(params.get('stats')))

        def work(job):
            job.update(done=0, total=None, removed=0, filters={})
            optimizer = wf.WordlistOptimizer(options, LanguageManager())
            try:
                summary = optimizer.optimize(
                    quiet=True, stop_event=job.stop_event,
                    progress=lambda done, total, removed, counts: job.update(
                        done=done, total=total, removed=removed, filters=counts))
            except Exception:
                _discard_if_empty(path)
                raise
            result = {
                'file': self.public(self.add_file(path, 'output')),
                'total': summary['total'],
                'removed': summary['removed'],
                'remaining': summary['remaining'],
                'filters': summary['filter_stats'],
                'head': read_head(path),
            }
            if summary['stats_file']:
                result['stats_file'] = self.public(self.add_file(summary['stats_file'], 'output'))
            return result

        return self.start_job('clean', work)

    def analyze(self, params):
        source = self.get_file(params.get('file_id'))
        compressed = source['path'].lower().endswith('.gz')

        def work(job):
            size = os.path.getsize(source['path'])
            job.update(done=0, fraction=None if compressed else 0.0)

            def on_progress(lines, chars):
                # chars + newlines approximates bytes read (exact for ASCII lists)
                fraction = None if compressed or not size else min(0.99, (chars + lines) / size)
                job.update(done=lines, fraction=fraction)

            stats = wf.analyze_wordlist(source['path'], progress=on_progress, stop_event=job.stop_event)
            stats['length_counts'] = {str(k): v for k, v in sorted(stats['length_counts'].items())}
            return {'file': self.public(source), 'stats': stats}

        return self.start_job('analyze', work)

    def shutdown(self, timeout=5.0):
        with self._lock:
            jobs = list(self.jobs.values())
        for job in jobs:
            job.stop_event.set()
        deadline = time.monotonic() + timeout
        for job in jobs:
            if job.thread is not None:
                job.thread.join(max(0.0, deadline - time.monotonic()))
        if self.upload_dir:
            shutil.rmtree(self.upload_dir, ignore_errors=True)


# --- HTTP -------------------------------------------------------------------

ROUTES = (
    ('GET', re.compile(r'/api/meta'), 'api_meta'),
    ('POST', re.compile(r'/api/generate/preview'), 'api_preview'),
    ('POST', re.compile(r'/api/generate'), 'api_generate'),
    ('POST', re.compile(r'/api/clean'), 'api_clean'),
    ('POST', re.compile(r'/api/analyze'), 'api_analyze'),
    ('POST', re.compile(r'/api/upload'), 'api_upload'),
    ('POST', re.compile(r'/api/files/local'), 'api_local_file'),
    ('GET', re.compile(r'/api/files/([0-9a-f]+)/download'), 'api_download'),
    ('POST', re.compile(r'/api/files/([0-9a-f]+)/reveal'), 'api_reveal'),
    ('GET', re.compile(r'/api/jobs/([0-9a-f]+)'), 'api_job'),
    ('POST', re.compile(r'/api/jobs/([0-9a-f]+)/stop'), 'api_stop'),
)


class Handler(BaseHTTPRequestHandler):
    server_version = 'BruteForceHelper'
    sys_version = ''

    @property
    def app(self):
        return self.server.app

    def log_message(self, format, *args):
        pass  # keep the terminal quiet; problems are reported in the page

    def do_GET(self):
        self._handle('GET')

    def do_POST(self):
        self._handle('POST')

    def _handle(self, method):
        try:
            if not self._host_allowed():
                raise ApiError(403, 'forbidden')
            url = urlparse(self.path)
            if method == 'GET' and url.path in ('/', '/index.html'):
                self._send_index()
            elif method == 'GET' and url.path.startswith('/static/'):
                self._send_static(url.path[len('/static/'):])
            elif url.path.startswith('/api/'):
                self._api(method, url)
            else:
                raise ApiError(404, 'not_found')
        except ApiError as err:
            self._try_send_json(err.status, {'error': err.code, 'field': err.field})
        except ConnectionError:
            pass  # the browser went away mid-response
        except Exception as exc:
            self._try_send_json(500, {'error': 'server_error', 'message': str(exc)})

    def _allowed_hosts(self):
        port = self.server.server_address[1]
        return (f'{HOST}:{port}', f'localhost:{port}')

    def _host_allowed(self):
        # Rejects DNS-rebinding: a foreign name pointed at 127.0.0.1 keeps its own Host header
        return (self.headers.get('Host') or '').strip().lower() in self._allowed_hosts()

    def _api(self, method, url):
        supplied = self.headers.get('X-Token') or (parse_qs(url.query).get('token') or [''])[0]
        if not hmac.compare_digest(supplied.encode('utf-8', 'replace'), self.app.token.encode('ascii')):
            raise ApiError(403, 'forbidden')
        if method == 'POST':
            origin = (self.headers.get('Origin') or '').lower()
            if origin and origin not in tuple('http://' + host for host in self._allowed_hosts()):
                raise ApiError(403, 'forbidden')
        for verb, pattern, name in ROUTES:
            if verb == method:
                match = pattern.fullmatch(url.path)
                if match:
                    getattr(self, name)(*match.groups())
                    return
        raise ApiError(404, 'not_found')

    # endpoints

    def api_meta(self):
        self._send_json(200, self.app.meta())

    def api_preview(self):
        self._send_json(200, self.app.preview(self._read_json()))

    def api_generate(self):
        self._send_json(202, self.app.generate(self._read_json()).to_dict())

    def api_clean(self):
        self._send_json(202, self.app.clean(self._read_json()).to_dict())

    def api_analyze(self):
        self._send_json(202, self.app.analyze(self._read_json()).to_dict())

    def api_upload(self):
        length = self.headers.get('Content-Length') or ''
        if not _DIGITS.fullmatch(length):
            raise ApiError(411, 'length_required')
        name = unquote(self.headers.get('X-File-Name') or '')
        info = self.app.save_upload(name, int(length), self.rfile)
        self._send_json(201, {'file': WebApp.public(info)})

    def api_local_file(self):
        info = self.app.local_file(self._read_json())
        self._send_json(201, {'file': WebApp.public(info)})

    def api_download(self, file_id):
        info = self.app.get_file(file_id, outputs_only=True)
        self._send_file(info['path'], info['name'])

    def api_reveal(self, file_id):
        info = self.app.get_file(file_id, outputs_only=True)
        try:
            reveal_in_file_manager(info['path'])
        except OSError:
            raise ApiError(500, 'reveal_failed')
        self._send_json(200, {'ok': True})

    def api_job(self, job_id):
        self._send_json(200, self.app.get_job(job_id).to_dict())

    def api_stop(self, job_id):
        job = self.app.get_job(job_id)
        job.stop_event.set()
        self._send_json(200, job.to_dict())

    # plumbing

    def _read_json(self):
        content_type = (self.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if content_type != 'application/json':
            raise ApiError(415, 'unsupported_type')
        length = self.headers.get('Content-Length') or '0'
        if not _DIGITS.fullmatch(length):
            raise ApiError(400, 'invalid')
        if int(length) > MAX_JSON_BYTES:
            raise ApiError(413, 'too_large')
        try:
            data = json.loads(self.rfile.read(int(length)).decode('utf-8') or '{}')
        except ValueError:
            raise ApiError(400, 'invalid')
        if not isinstance(data, dict):
            raise ApiError(400, 'invalid')
        return data

    def _send(self, status, body, content_type, headers=()):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        for name, value in SECURITY_HEADERS + tuple(headers):
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, payload):
        self._send(status, json.dumps(payload).encode('utf-8'), 'application/json; charset=utf-8')

    def _try_send_json(self, status, payload):
        try:
            self._send_json(status, payload)
        except Exception:
            pass

    def _send_index(self):
        with open(os.path.join(STATIC_DIR, 'index.html'), 'r', encoding='utf-8') as f:
            page = f.read().replace('{{TOKEN}}', self.app.token)
        self._send(200, page.encode('utf-8'), 'text/html; charset=utf-8')

    def _send_static(self, name):
        content_type = STATIC_TYPES.get(name)
        if content_type is None:
            raise ApiError(404, 'not_found')
        with open(os.path.join(STATIC_DIR, name), 'rb') as f:
            self._send(200, f.read(), content_type)

    def _send_file(self, path, name):
        fallback = re.sub(r'[^\x20-\x7e]|"', '_', name)
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(os.path.getsize(path)))
        self.send_header('Content-Disposition',
                         f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name)}")
        for header in SECURITY_HEADERS:
            self.send_header(*header)
        self.end_headers()
        with open(path, 'rb') as f:
            shutil.copyfileobj(f, self.wfile, COPY_CHUNK)


class LocalServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # a busy port should fail, not be shared

    def server_bind(self):
        # HTTPServer.server_bind does a reverse DNS lookup that can stall for
        # seconds on Windows; the name is not needed for a loopback server.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


def create_server(port=None, output_dir=None):
    """Bind to 127.0.0.1. An explicit port must be free; otherwise the first free
    port from DEFAULT_PORT upwards is used."""
    candidates = [port] if port is not None else list(range(DEFAULT_PORT, DEFAULT_PORT + 10)) + [0]
    error = None
    for candidate in candidates:
        try:
            httpd = LocalServer((HOST, candidate), Handler)
        except (OSError, OverflowError) as exc:
            error = exc
            continue
        httpd.app = WebApp(output_dir or DEFAULT_OUTPUT_DIR)
        httpd.app.port = httpd.server_address[1]
        return httpd
    raise error


def run(port=None, open_browser=True, start_tab=None):
    """Start the web interface and serve until Ctrl+C."""
    remove_stale_uploads()
    try:
        httpd = create_server(port)
    except (OSError, OverflowError) as exc:
        print(f"{Fore.RED}Could not start the web interface: {exc}{Style.RESET_ALL}")
        return
    url = f'http://{HOST}:{httpd.app.port}/' + (f'#{start_tab}' if start_tab else '')
    print(f"\n{Fore.GREEN}BruteForce Helper web interface is running:{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{url}{Style.RESET_ALL}")
    print(f"  Files are saved in {httpd.app.output_dir}")
    print("  Only this computer can open it. Press Ctrl+C to stop.\n")
    if open_browser:
        timer = threading.Timer(0.4, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        httpd.server_close()
        httpd.app.shutdown()
