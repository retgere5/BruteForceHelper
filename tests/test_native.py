"""The Rust core (native/) checked against the Python code it mirrors.

These tests need the built program (cargo build --release --manifest-path
native/Cargo.toml). Without it they are skipped, unless BFH_REQUIRE_NATIVE=1
asks for a failure instead (CI sets it, so a broken build cannot hide)."""
import itertools
import os
import random
import subprocess

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
