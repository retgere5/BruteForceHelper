"""The Rust core (native/) checked against the Python code it mirrors.

These tests need the built program (cargo build --release --manifest-path
native/Cargo.toml). Without it they are skipped, unless BFH_REQUIRE_NATIVE=1
asks for a failure instead (CI sets it, so a broken build cannot hide)."""
import itertools
import os
import random
import subprocess
import sys
import threading

import pytest

import PassGenerator as pg

MOD_KEYS = ('uppercase', 'capitalize', 'reverse', 'reverse_capitalize', 'reverse_upper', 'leet', 'turkish')
# Turkish letters, characters whose case forms are longer than one character
# (ß -> SS, ǆ -> ǅ, ﬁ -> FI), a digit and a symbol
ALPHABET = 'abcıiİIşŞğĞüÜöÖçÇßǆﬁ1!'


def _hex(text):
    return text.encode('utf-8').hex()


def _unhex(text):
    return bytes.fromhex(text).decode('utf-8')


@pytest.fixture(scope='module')
def core():
    path = pg._native_binary()
    if path is None:
        if os.environ.get('BFH_REQUIRE_NATIVE') == '1':
            pytest.fail('bfh-core is missing: cargo build --release --manifest-path native/Cargo.toml')
        pytest.skip('bfh-core is not built')
    return path


def _ask(core, command, lines):
    """Run one of the core's line-in, line-out commands and return its answer lines."""
    job = '\n'.join([f'{pg.NATIVE_PROTOCOL} {command}', *lines, 'go', '']).encode('ascii')
    done = subprocess.run([core], input=job, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert done.returncode == 0, done.stderr.decode('utf-8', 'replace')
    return done.stdout.decode('ascii').splitlines()


def _random_words(seed, count, longest=6):
    rng = random.Random(seed)
    return [''.join(rng.choice(ALPHABET) for _ in range(rng.randint(1, longest))) for _ in range(count)]


# --- what Python tells the core -------------------------------------------------------

def test_char_table_lists_the_non_ascii_characters_of_the_input():
    rows = pg._char_table(['aß', 'İ', 'ßa'], turkish=False)
    assert [_unhex(row.split()[1]) for row in rows] == ['ß', 'İ']  # ASCII needs no row


def test_char_table_rows_carry_pythons_case_forms():
    (row,) = pg._char_table(['ß'], turkish=False)
    assert row == f"char {_hex('ß')} {_hex('SS')} {_hex('ß')} {_hex('Ss')}"
    (row,) = pg._char_table(['İ'], turkish=False)
    assert row == f"char {_hex('İ')} {_hex('İ')} {_hex('i' + chr(0x307))} {_hex('İ')}"


def test_char_table_adds_the_turkish_letters_when_turkish_case_is_on():
    assert pg._char_table(['ab'], turkish=False) == []
    assert [_unhex(row.split()[1]) for row in pg._char_table(['ab'], turkish=True)] == ['İ', 'ı']


def test_job_spec_lists_every_option():
    job = pg._native_job(['ab', 'ç'], 2, 5, 'x', None, (True, False, False, False, False, True, False),
                         dedup=True, limit=10, max_memory_bytes=None, use_gzip=False, threads=0)
    assert job.decode('ascii').splitlines() == [
        'BFH1 generate',
        'words 6162 c3a7',
        'min 2',
        'max 5',
        'start 78',
        'end -',
        'mods 1000010',
        'dedup memory',
        'limit 10',
        'maxmem -',
        'gzip 0',
        'newline ' + os.linesep.encode('ascii').hex(),
        'threads 0',
        'char c3a7 c387 c3a7 c387',
        'go',
    ]


def test_job_spec_marks_missing_options():
    job = pg._native_job(['a'], None, None, None, '!', (False,) * 7, dedup=False, limit=None,
                         max_memory_bytes=4096, use_gzip=True, threads=3).decode('ascii').splitlines()
    assert job[2:13] == ['min 0', 'max -', 'start -', 'end 21', 'mods 0000000', 'dedup none',
                         'limit -', 'maxmem 4096', 'gzip 1', 'newline ' + os.linesep.encode('ascii').hex(),
                         'threads 3']


# --- variations -----------------------------------------------------------------------

def test_variations_match_python_for_every_modifier_combination(core):
    words = _random_words(7, 60) + ['ali', 'IŞIK', 'istanbul', 'İZMİR', 'ßß', 'ǆa', 'ﬁﬁ', 'a', 'Aa1!']
    for bits in itertools.product('01', repeat=len(MOD_KEYS)):
        mods = {key: bit == '1' for key, bit in zip(MOD_KEYS, bits)}
        answer = _ask(core, 'variants', ['mods ' + ''.join(bits),
                                         *pg._char_table(words, mods['turkish']),
                                         *('line ' + _hex(word) for word in words)])
        got = [[_unhex(item) for item in row.split()] for row in answer]
        assert got == [pg.apply_modifications(word, mods) for word in words], mods


def test_core_refuses_a_character_it_has_no_case_data_for(core):
    job = f'{pg.NATIVE_PROTOCOL} variants\nmods 1000000\nline {_hex("ç")}\ngo\n'.encode('ascii')
    done = subprocess.run([core], input=job, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert done.returncode == 2
    assert 'U+00E7' in done.stderr.decode('utf-8', 'replace')


def test_core_refuses_another_protocol(core):
    done = subprocess.run([core], input=b'BFH0 variants\ngo\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert done.returncode == 2
    assert subprocess.run([core, '--protocol'], stdout=subprocess.PIPE).stdout.split() == [b'BFH1']


# --- whole runs -----------------------------------------------------------------------

def _generate(engine, monkeypatch, out, words, shortest, longest, **options):
    """One quiet run through the chosen engine ('python' or 'native')."""
    if engine == 'python':
        monkeypatch.setenv('BFH_NATIVE', '0')
    else:
        monkeypatch.delenv('BFH_NATIVE', raising=False)
    return pg.generate_and_save_combinations(words, str(out), shortest, longest, quiet=True, **options)


def _same_run(monkeypatch, tmp_path, words, shortest, longest, **options):
    """Runs both engines and checks that the core wrote Python's bytes and counts."""
    python = _generate('python', monkeypatch, tmp_path / 'python.out', words, shortest, longest, **options)
    native = _generate('native', monkeypatch, tmp_path / 'native.out', words, shortest, longest, **options)
    assert (python['engine'], native['engine']) == ('python', 'native')
    assert (tmp_path / 'native.out').read_bytes() == (tmp_path / 'python.out').read_bytes()
    for key in ('written', 'stopped_by', 'filtered', 'filtered_total', 'skipped'):
        assert native[key] == python[key], key
    return native


RUNS = [
    # words, min, max, options
    (['a', 'b', 'c'], 1, 4, {}),
    (['ab', 'c', 'ğü'], 2, 5, {'word_start': 'x'}),
    (['admin', 'root', '2024'], 6, 12, {'word_end': '!', 'uppercase': True, 'leet': True}),
    (['a', 'a', 'bc'], 2, 4, {}),                                  # a word twice
    (['a', 'ab', 'b'], 1, 5, {}),                                  # 'ab' is also 'a' + 'b'
    (['x', 'yy'], 3, None, {}),                                    # no maximum
    (['x', 'yy', 'zzz'], None, None, {'capitalize': True}),
    (['abc'], 7, 8, {}),                                           # nothing fits
    (['a', 'bbbb'], 6, 8, {'reverse': True}),
    (['ali', 'İz', 'ış', '1'], 2, 8, {'uppercase': True, 'capitalize': True, 'turkish': True}),
    (['ılık', 'Işık', 'i', '7'], 2, 9, {'reverse_capitalize': True, 'reverse_upper': True, 'turkish': True,
                                       'leet': True, 'word_start': 'x', 'word_end': 'ß'}),
    (['Ab', 'c', '12'], 2, 7, {'reverse': True, 'capitalize': True, 'word_end': 'Z'}),
    (['ß', 'ǆ', 'ﬁ'], 1, 3, {'uppercase': True, 'capitalize': True, 'reverse_capitalize': True}),
    (['aB', 'İ'], 1, 6, {'capitalize': True, 'reverse_capitalize': True, 'word_start': 'ıX', 'word_end': 'yİ'}),
    (['a', 'b'], 1, 6, {'dedup': False, 'uppercase': True}),       # repeats are kept
    (['a', 'b', 'c'], 1, 5, {'limit': 37}),
    (['a', 'a', 'b'], 1, 5, {'limit': 20, 'capitalize': True}),    # the limit counts unique lines
    (['a', 'b'], 1, 3, {'limit': 14}),                             # the limit is the last line
    (['a', 'b'], 1, 3, {'limit': 500}),                            # a limit past the end
    (['a', 'A', '1'], 1, 6, {'uppercase': True, 'dedup': False, 'limit': 301}),
    (['😀', 'a'], 1, 4, {'reverse': True, 'uppercase': True}),
]


@pytest.mark.parametrize('words, shortest, longest, options', RUNS)
def test_core_writes_the_same_file_as_python(core, tmp_path, monkeypatch, words, shortest, longest, options):
    _same_run(monkeypatch, tmp_path, words, shortest, longest, **options)


def test_random_runs_match_python(core, tmp_path, monkeypatch):
    rng = random.Random(11)
    for i in range(40):
        words = _random_words(100 + i, rng.randint(1, 5), longest=3)
        if rng.random() < 0.3:
            words.append(rng.choice(words))
        shortest = rng.randint(1, 4)
        longest = rng.choice([None, shortest + rng.randint(0, 4)])
        options = {key: rng.random() < 0.35 for key in MOD_KEYS}
        options['dedup'] = rng.random() < 0.8
        if rng.random() < 0.3:
            options['limit'] = rng.randint(1, 400)
        if rng.random() < 0.3:
            options['word_start'] = ''.join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 2)))
        if rng.random() < 0.3:
            options['word_end'] = ''.join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 2)))
        case = tmp_path / str(i)
        case.mkdir()
        _same_run(monkeypatch, case, words, shortest, longest, **options)


def test_live_counters_and_progress_reach_the_totals(core, tmp_path, monkeypatch):
    live, calls = {}, []
    monkeypatch.delenv('BFH_NATIVE', raising=False)
    result = pg.generate_and_save_combinations(['a', 'a', 'b'], str(tmp_path / 'o.txt'), 1, 4, quiet=True,
                                               uppercase=True, live=live,
                                               progress=lambda done, total: calls.append((done, total)))
    total = pg.calculate_total_combinations(['a', 'a', 'b'], 1, 4, {'uppercase': True})
    assert result['engine'] == 'native'
    assert live == {'processed': total, 'filtered_total': 0}
    assert calls[-1] == (result['written'], total)


def test_console_run_through_the_core_prints_the_usual_report(core, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('BFH_NATIVE', raising=False)
    out = tmp_path / 'o.txt'
    result = pg.generate_and_save_combinations(['a', 'b'], str(out), 1, 3)
    printed = capsys.readouterr().out
    assert result['engine'] == 'native' and result['written'] == 14
    for text in ('Combinations saved successfully', 'Total combinations generated', 'Processing time',
                 'Memory usage', str(out)):
        assert text in printed


@pytest.mark.parametrize('words, options', [
    (['aΣ', 'b'], {'capitalize': True}),     # capital sigma lowercases by context
    (['a', ''], {}),                         # an empty word
    (['a\nb', 'c'], {}),                     # a line break inside a word
    (['a', 'b'], {'word_end': 'Σ'}),
    (['a', 'b'], {'resume': True}),
    (['a', 'b'], {'disk_dedup': True}),
    (['a', 'b'], {'filters': ['repetitive_chars']}),
    (['a', 'b'], {'limit': -1}),
    (['a', 'b'], {'use_gzip': True}),
])
def test_runs_the_core_cannot_do_stay_in_python(core, tmp_path, monkeypatch, words, options):
    monkeypatch.delenv('BFH_NATIVE', raising=False)
    result = pg.generate_and_save_combinations(words, str(tmp_path / 'o.txt'), 1, 3, quiet=True, **options)
    assert result['engine'] == 'python'


def test_a_stop_set_before_the_run_stays_in_python(core, tmp_path, monkeypatch):
    monkeypatch.delenv('BFH_NATIVE', raising=False)
    stop = threading.Event()
    stop.set()
    result = pg.generate_and_save_combinations(['a', 'b'], str(tmp_path / 'o.txt'), 1, 3, quiet=True,
                                               stop_event=stop)
    assert (result['engine'], result['written'], result['stopped_by']) == ('python', 0, 'user')


def test_python_takes_over_when_the_core_is_missing_or_broken(core, tmp_path, monkeypatch):
    monkeypatch.delenv('BFH_NATIVE', raising=False)
    for stand_in in (str(tmp_path / 'no-such-program'), sys.executable):
        monkeypatch.setenv('BFH_CORE', stand_in)
        out = tmp_path / 'o.txt'
        result = pg.generate_and_save_combinations(['a', 'b'], str(out), 1, 2, quiet=True)
        assert result['engine'] == 'python'
        assert out.read_text(encoding='utf-8').split() == ['a', 'b', 'aa', 'ab', 'ba', 'bb']


def test_missing_output_folder_raises_the_same_error(core, tmp_path, monkeypatch):
    monkeypatch.delenv('BFH_NATIVE', raising=False)
    with pytest.raises(FileNotFoundError):
        pg.generate_and_save_combinations(['a'], str(tmp_path / 'missing' / 'o.txt'), quiet=True)


def _line(number, letters='abcdefghij'):
    """Line `number` (from zero) of the run over ten one-letter words: every
    one-letter line, then every two-letter line, and so on."""
    length = 1
    while number >= 10 ** length:
        number -= 10 ** length
        length += 1
    return ''.join(letters[int(digit)] for digit in str(number).zfill(length))


def _size_of_first(count, ending):
    """Bytes the first `count` lines of that run take."""
    size, length = 0, 1
    while count > 0:
        here = min(10 ** length, count)
        size += here * (length + ending)
        count -= here
        length += 1
    return size


def test_stop_event_ends_the_core_and_keeps_whole_lines(core, tmp_path, monkeypatch):
    monkeypatch.delenv('BFH_NATIVE', raising=False)
    stop = threading.Event()
    out = tmp_path / 'o.txt'
    words = list('abcdefghij')
    result = pg.generate_and_save_combinations(words, str(out), 1, 12, quiet=True, stop_event=stop,
                                               progress=lambda done, total: done and stop.set())
    written = result['written']
    assert (result['engine'], result['stopped_by']) == ('native', 'user')
    assert 0 < written < pg.calculate_total_combinations(words, 1, 12, {})
    ending = os.linesep.encode('ascii')
    assert out.stat().st_size == _size_of_first(written, len(ending))
    with open(out, 'rb') as lines:
        head = [lines.readline() for _ in range(min(3000, written))]
        last = _line(written - 1).encode('ascii') + ending
        lines.seek(-len(last), os.SEEK_END)
        assert lines.read() == last
    assert head == [_line(number).encode('ascii') + ending for number in range(len(head))]


def test_an_error_in_the_callers_callback_stops_the_core(core, tmp_path, monkeypatch):
    monkeypatch.delenv('BFH_NATIVE', raising=False)
    out = tmp_path / 'o.txt'

    def interrupt(done, total):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        pg.generate_and_save_combinations(list('abcdefghij'), str(out), 1, 9, quiet=True, progress=interrupt)
    out.unlink()  # the core has let go of the file
