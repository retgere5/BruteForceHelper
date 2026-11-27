# 🛠️ BruteForce Helper Tools

![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![Maintained](https://img.shields.io/badge/Maintained%3F-yes-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Build and clean password wordlists — simple, fast, for learning and authorized testing.**
**Şifre listeleri oluştur ve temizle — basit, hızlı; öğrenme ve yetkili test için.**

🌍 **English** · [Türkçe ↓](#turkce)

---

<a id="english"></a>

## 📖 What is this?

Two small command-line tools:

- **🔑 PassGenerator** — turns a few words or characters into every possible password combination. It can also add variations: `UPPERCASE`, `Capitalized`, reversed, leet (`a→4`), prefixes and suffixes. Great for building your own wordlist.
- **🔍 WordlistOptimizer** — takes a big password list and **cleans** it, removing weak or junk passwords (too short, `aaaaaa`, `123456`, `qwerty`, keyboard patterns…) so you keep a smaller, better list. It can also **analyze** a list and tell you what's inside.

> ⚠️ For **learning and authorized security testing only**. Only use it on systems you own or have permission to test.

## 🚀 Setup

You need **Python 3.6 or newer**. Then:

```bash
git clone https://github.com/retgere5/BruteForceHelper.git
cd BruteForceHelper
pip install -r requirements.txt
```

## 🔑 PassGenerator — make a wordlist

See how one word turns into many:

```bash
python PassGenerator.py -w password -AB -L337
# → password, PASSWORD, p455w0rd ...
```

Combine several words (names, years, etc.):

```bash
python PassGenerator.py -w admin root 2024
# → admin, root, adminroot, admin2024, root2024 ...
```

The result is saved to **`combinations.txt`** (change it with `-o myfile.txt`).

### Handy options

| Option | What it does |
|---|---|
| `-w` | The words/characters to combine **(required)** |
| `-o` | Output file name (default `combinations.txt`) |
| `-m` / `-M` | Minimum / maximum length |
| `-AB` | `UPPERCASE` |
| `-Ab` | `Capitalize` |
| `-ba` | reverse (`test → tset`) |
| `-L337` | leet speak (`a→4`, `e→3`, `o→0`…) |
| `-ws` / `-we` | add text **before** / **after** each word |

> 💡 Run `python PassGenerator.py` with no options to see live examples, or `-h` for the full list.

<details>
<summary>⚙️ Advanced (for very large runs)</summary>

- `-z` — save compressed (`.gz`)
- `-c config.json` — read all options from a file
- `--limit N` — stop after N results
- `--no-dedup` / `--max-memory 512` / `--disk-dedup` — handle huge runs without filling memory
- `--resume` — if interrupted (Ctrl+C), run the same command again to continue
- `--filters all` (or rule names such as `pattern_repetition`) — drop weak lines with the cleaning rules while generating: a smaller file, a slower run

Example `config.json`:
```json
{ "words": ["admin", "root"], "min_length": 6, "AB": true, "L337": true }
```
</details>

## 🔍 WordlistOptimizer — clean a wordlist

Just run it and answer the questions (language, input/output file, which filters to apply):

```bash
python WordlistFixer.py
```

It walks you through everything and shows live statistics while it works. You choose what to remove — short passwords, repeated characters, sequences, keyboard patterns, common words, and more.

**Only want to inspect a list?**

```bash
python WordlistFixer.py --analyze rockyou.txt
# → total count, shortest/average/longest length, most common lengths,
#   and the character mix (digits only, letters only, has symbols…)
```

**Run it without questions** (settings from a file):

```bash
python WordlistFixer.py --config config.json --lang en
```

> 💡 `.gz` files work directly for both input and output. The interactive `q` (stop) / `c` (checkpoint) keys are Windows-only; everything else runs on Windows, Linux and macOS.

## 🖥️ Web interface

Prefer clicking to typing? Start the web interface:

```bash
python PassGenerator.py --webui
```

Your browser opens at `http://127.0.0.1:8765` with all three tools: **Generate**, **Clean** and **Analyze**. You see the first lines of your list while you type, you can drop a wordlist straight onto the page, and every screen shows the matching command line.

- Runs only on your computer (127.0.0.1). Nothing is sent anywhere.
- Results are saved in the `output/` folder.
- `--port 9000` picks another port, `--no-browser` only prints the link.
- `python WordlistFixer.py --webui` opens it on the Clean tab.

## ⚠️ Disclaimer

This project is for **educational purposes only**. You are responsible for making sure you have permission to test any system you use it against. The author is not responsible for any misuse.

## 📝 License

MIT — see [LICENSE](LICENSE).

> 🧪 *Developers:* `pip install -r requirements-dev.txt && pytest`

---

<a id="turkce"></a>

## 📖 Bu nedir?

İki küçük komut satırı aracı:

- **🔑 PassGenerator** — birkaç kelime ya da karakteri alıp olası tüm şifre kombinasyonlarını üretir. Ayrıca varyasyon ekleyebilir: `BÜYÜK HARF`, `Baş Harf`, ters çevirme, leet (`a→4`), ön ek ve son ek. Kendi şifre listeni oluşturmak için birebir.
- **🔍 WordlistOptimizer** — büyük bir şifre listesini alıp **temizler**; zayıf/işe yaramaz şifreleri (çok kısa, `aaaaaa`, `123456`, `qwerty`, klavye dizilimleri…) atar, elinde daha küçük ve kaliteli bir liste kalır. Ayrıca bir listeyi **analiz edip** içinde ne olduğunu gösterebilir.

> ⚠️ Yalnızca **öğrenme ve yetkili güvenlik testi** içindir. Sadece sana ait olan ya da test izni bulunan sistemlerde kullan.

## 🚀 Kurulum

**Python 3.6 veya üstü** gerekir. Sonra:

```bash
git clone https://github.com/retgere5/BruteForceHelper.git
cd BruteForceHelper
pip install -r requirements.txt
```

## 🔑 PassGenerator — liste oluştur

Bir kelimenin nasıl çoğaldığını gör:

```bash
python PassGenerator.py -w password -AB -L337
# → password, PASSWORD, p455w0rd ...
```

Birden fazla kelimeyi birleştir (isim, yıl vb.):

```bash
python PassGenerator.py -w admin root 2024
# → admin, root, adminroot, admin2024, root2024 ...
```

Sonuç **`combinations.txt`** dosyasına kaydedilir (`-o dosyam.txt` ile değiştir).

### İşe yarayan seçenekler

| Seçenek | Ne yapar |
|---|---|
| `-w` | Birleştirilecek kelimeler/karakterler **(zorunlu)** |
| `-o` | Çıktı dosyası adı (varsayılan `combinations.txt`) |
| `-m` / `-M` | En kısa / en uzun uzunluk |
| `-AB` | `BÜYÜK HARF` |
| `-Ab` | `Baş harf büyük` |
| `-ba` | ters çevir (`test → tset`) |
| `-L337` | leet (`a→4`, `e→3`, `o→0`…) |
| `-ws` / `-we` | her kelimenin **başına** / **sonuna** ek |

> 💡 Hiç seçenek vermeden `python PassGenerator.py` çalıştırırsan canlı örnekleri, `-h` ile tüm listeyi görürsün.

<details>
<summary>⚙️ Gelişmiş (çok büyük işler için)</summary>

- `-z` — sıkıştırılmış kaydet (`.gz`)
- `-c config.json` — tüm seçenekleri dosyadan oku
- `--limit N` — N sonuçtan sonra dur
- `--no-dedup` / `--max-memory 512` / `--disk-dedup` — belleği doldurmadan devasa işleri yürüt
- `--resume` — kesilirse (Ctrl+C) aynı komutu tekrar çalıştırıp kaldığın yerden devam et
- `--filters all` (ya da `pattern_repetition` gibi kural adları) — zayıf satırları üretirken temizleme kurallarıyla at: dosya küçülür, üretim yavaşlar

Örnek `config.json`:
```json
{ "words": ["admin", "root"], "min_length": 6, "AB": true, "L337": true }
```
</details>

## 🔍 WordlistOptimizer — liste temizle

Çalıştır ve soruları yanıtla (dil, giriş/çıkış dosyası, hangi filtreler):

```bash
python WordlistFixer.py
```

Seni adım adım yönlendirir ve çalışırken canlı istatistik gösterir. Neyin atılacağını sen seçersin — kısa şifreler, tekrar eden karakterler, sıralı diziler, klavye dizilimleri, yaygın kelimeler ve daha fazlası.

**Sadece bir listeyi incelemek mi istiyorsun?**

```bash
python WordlistFixer.py --analyze rockyou.txt
# → toplam sayı, en kısa/ortalama/en uzun uzunluk, en sık uzunluklar,
#   ve karakter dağılımı (sadece rakam, sadece harf, özel karakter var mı…)
```

**Sorusuz çalıştır** (ayarlar bir dosyadan):

```bash
python WordlistFixer.py --config config.json --lang tr
```

> 💡 `.gz` dosyaları giriş ve çıkışta doğrudan çalışır. İnteraktif `q` (durdur) / `c` (checkpoint) tuşları yalnızca Windows'ta; gerisi Windows, Linux ve macOS'ta çalışır.

## 🖥️ Web arayüzü

Yazmak yerine tıklamayı mı seversin? Web arayüzünü başlat:

```bash
python PassGenerator.py --webui
```

Tarayıcın `http://127.0.0.1:8765` adresinde üç araçla açılır: **Üret**, **Temizle** ve **Analiz et**. Yazarken listenin ilk satırlarını görürsün, bir listeyi doğrudan sayfaya sürükleyip bırakabilirsin ve her ekran aynı işin komut satırı karşılığını gösterir.

- Yalnızca senin bilgisayarında çalışır (127.0.0.1). Hiçbir şey dışarı gönderilmez.
- Sonuçlar `output/` klasörüne kaydedilir.
- `--port 9000` başka bir port seçer, `--no-browser` yalnızca linki yazar.
- `python WordlistFixer.py --webui` arayüzü Temizle sekmesinde açar.

## ⚠️ Sorumluluk Reddi

Bu proje yalnızca **eğitim amaçlıdır**. Test ettiğin her sistem için izninin olduğundan emin olmak senin sorumluluğundadır. Yazar, kötüye kullanımdan sorumlu değildir.

## 📝 Lisans

MIT — bkz. [LICENSE](LICENSE).

> 🧪 *Geliştiriciler:* `pip install -r requirements-dev.txt && pytest`

---

Made with ❤️ by [retgere5](https://github.com/retgere5)
