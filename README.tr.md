<div align="center">

<img src="webui/static/favicon.svg" width="76" alt="">

# BruteForce Helper

**Kendi kelimelerinden şifre listesi üret, elindeki listeleri temizle.**

[![tests](https://github.com/retgere5/BruteForceHelper/actions/workflows/tests.yml/badge.svg)](https://github.com/retgere5/BruteForceHelper/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.9%2B-3776ab)
![license](https://img.shields.io/badge/license-MIT-2ea44f)

[English](README.md) · **Türkçe**

</div>

---

Şifre listeleri için iki komut satırı aracı ve ikisini de tarayıcıdan kullandıran bir web arayüzü.

| Araç | Ne yapar |
|---|---|
| **PassGenerator** | Verdiğin kelimelerden şifre listesi üretir: bütün birleşimler, istersen büyük/küçük harf, ters çevirme ve leet varyasyonlarıyla |
| **WordlistOptimizer** | Elindeki bir listeyi 14 kuralla temizler ya da içinde ne olduğunu gösterir |
| **Web arayüzü** | İki araç da tarayıcıda, yalnızca kendi bilgisayarında çalışır |

> **Önemli:** yalnızca öğrenme ve yetkili güvenlik testi içindir. Sadece sana ait olan ya da test etme iznin bulunan sistemlerde kullan.

**İçindekiler:** [Kurulum](#kurulum) · [PassGenerator](#passgenerator) · [WordlistOptimizer](#wordlistoptimizer) · [Web arayüzü](#web-arayüzü) · [Perde arkası](#perde-arkası) · [Geliştirme](#geliştirme) · [Lisans](#sorumlu-kullanım-ve-lisans)

## Kurulum

Python 3.9 ya da üstü gerekir. Windows, Linux ve macOS'ta çalışır (Windows ve Linux'ta test edilir).

```bash
git clone https://github.com/retgere5/BruteForceHelper.git
cd BruteForceHelper
pip install -r requirements.txt
```

Sonra nereden başlayacağını seç:

```bash
python PassGenerator.py -w admin 2024    # liste üret
python WordlistFixer.py                  # bir listeyi temizle ya da incele
python PassGenerator.py --webui          # ikisini de tarayıcıda yap
```

## PassGenerator

Birkaç kelime ver; bunların bütün birleşimlerini satır satır `combinations.txt` dosyasına yazar.

```bash
python PassGenerator.py -w admin root 2024
# admin, root, 2024, adminadmin, adminroot, admin2024, ...   39 satır

python PassGenerator.py -w admin root 2024 -M 9 -Ab
# admin, Admin, root, Root, 2024, adminroot, Adminroot, ...   18 satır

python PassGenerator.py -w password -AB -L337
# password, PASSWORD, p455w0rd, P455W0RD
```

`-M` vermezsen bir satır en çok verdiğin kelime sayısı kadar kelimeden oluşur (ilk örnekte üç).

### Seçenekler

| Seçenek | Ne yapar | Örnek |
|---|---|---|
| `-w KELİME ...` | Birleştirilecek kelime ya da karakterler (zorunlu) | `-w admin 2024 !` |
| `-m N`, `-M N` | En kısa ve en uzun satır, karakter olarak | `-m 8 -M 12` |
| `-o DOSYA` | Çıktı dosyası | `-o listem.txt` |
| `-AB` | Büyük harf | `test` → `TEST` |
| `-Ab` | Baş harf büyük | `test` → `Test` |
| `-ba` | Ters | `test` → `tset` |
| `-Ba`, `-BA` | Ters, sonra baş harf büyük ya da tamamı büyük | `test` → `Tset`, `TSET` |
| `-L337` | Leet: `a→4 b→8 e→3 g→6 i→1 l→1 o→0 s→5 t→7 z→2` | `password` → `p455w0rd` |
| `-TR` | Her harf varyasyonunun Türkçe biçimini de ekler | `ali` → `ALI`, `ALİ` |
| `-ws`, `-we` | Her satırın başına ve sonuna eklenen metin | `-ws x_ -we _23` → `x_admin_23` |

Daha çok örnek için `python PassGenerator.py` komutunu seçeneksiz, tam liste için `-h` ile çalıştır.

<details>
<summary><b>Büyük işler</b>: gzip, sınırlar, bellek, kaldığı yerden devam, ayar dosyası</summary>
<br>

| Seçenek | Ne yapar |
|---|---|
| `-z` | gzip olarak yazar (`.gz`). Dosya adının `.gz` ile bitmesi de aynı işi görür |
| `--limit N` | N satırdan sonra durur |
| `--filters KURAL ...` | Zayıf satırları üretirken [temizleme kurallarıyla](#kurallar) atar. `all` bütün kuralları açar |
| `--no-dedup` | Tekrar eden satırları ayıklamaz: bellek sabit kalır |
| `--max-memory MB` | Tekrar ayıklamada kullanılan bellek bu boyuta ulaşınca durur |
| `--disk-dedup` | Tekrarları diskte ayıklar (SQLite): bellek sınırlı kalır, daha yavaştır |
| `--resume` | Çalışırken ilerlemeyi kaydeder. İş kesilirse aynı komutu yeniden çalıştırınca kaldığı yerden sürer |
| `-c DOSYA` | Seçenekleri bir JSON dosyasından okur. Komut satırında yazdıkların önceliklidir |

```json
{ "words": ["admin", "root"], "min_length": 6, "AB": true, "L337": true }
```

`--filters` ile, satırın içinde bir şey arayan kurallar (tekrar, sıra, yıl gibi) bütün satır gruplarını daha üretilmeden atlar. Dosya küçülür, iş de hızlanır.

</details>

### Rust ile daha hızlı (isteğe bağlı)

Üretim döngüsü `native/` klasöründe küçük bir Rust programı olarak da var. Bütün işlemci çekirdeklerini kullanır ve bayt bayt aynı dosyayı yazar.

| 9 kelime, 8–12 karakter | Python | Rust ile |
|---|---|---|
| 5 milyon satır | 8,8 sn | 0,08 sn |
| 40 milyon aday satır (`-AB -Ab -L337`) | 47 sn | 0,5 sn |
| 11 milyon satır, gzip | 15,5 sn | 0,5 sn |

<sub>6 çekirdekli Ryzen 5 5600 üzerinde ölçüldü.</sub>

[Rust](https://rustup.rs) 1.74 ya da üstüyle bir kez derlemen yeter:

```bash
cargo build --release --manifest-path native/Cargo.toml
```

PassGenerator programı kendisi bulur, komut satırında da web arayüzünde de. Derlemezsen her şey eskisi gibi Python'la çalışır. `--filters`, `--resume` ya da `--disk-dedup` kullanılan işler her zaman Python'la çalışır; `BFH_NATIVE=0` Rust programını kapatır.

## WordlistOptimizer

Bir listeyi temizler: kuralları sen seçersin, uyan satırları siler, kalanları `optimized.txt` dosyasına yazar.

```bash
python WordlistFixer.py
```

Dili, dosyaları ve kuralları sorar; çalışırken canlı istatistik gösterir. Çalıştırmanın iki yolu daha var:

```bash
# listeye yalnızca bak: kaç satır, ne uzunlukta, hangi karakterler
python WordlistFixer.py --analyze rockyou.txt

# soru sormadan: ayarlar bir dosyadan gelir
python WordlistFixer.py --config clean.json
```

```json
{
  "input": "rockyou.txt",
  "output": "cleaned.txt",
  "min_length": 8,
  "max_length": 16,
  "repetitive_chars": true,
  "sequential_chars": true,
  "keyboard_patterns": true,
  "common_words": true
}
```

<details>
<summary><a id="kurallar"></a><b>14 kural</b></summary>
<br>

| Kural | Sildiği satır | Örnek |
|---|---|---|
| `min_length_filter` | 4 karakterden kısa | `abc` |
| `repetitive_chars` | aynı karakter art arda 4 kez geçiyor | `aaaa12` |
| `pattern_repetition` | 2 ya da daha çok karakterlik bir parça hemen ardından yineleniyor | `abab`, `1a21a2` |
| `number_only` | yalnızca rakam, 6 ya da daha çok | `482913` |
| `letter_only` | yalnızca harf, 6 ya da daha çok | `sunshine` |
| `single_char_type` | tek tür karakterden oluşuyor: hepsi rakam, hepsi harf ya da hepsi simge | `hello` |
| `sequential_chars` | alfabenin ya da rakamların art arda 4 komşusunu içeriyor, ileri ya da geri | `abcd`, `4321` |
| `keyboard_patterns` | `qwerty`, `asdfgh`, `zxcvbn`, `qwertz` ya da `azerty` içeriyor | `qwerty7` |
| `special_patterns` | `!@#` içeriyor | `pass!@#` |
| `year_patterns` | 1900 ile 2099 arasında bir yıl içeriyor | `ali1998` |
| `date_patterns` | bir tarih ya da art arda 8 rakam içeriyor | `01.02.2024` |
| `phone_patterns` | Türkiye cep telefonu numarası içeriyor | `05321234567` |
| `common_words` | `password`, `admin`, `123456`, `qwerty`, `letmein`, `welcome`, `monkey`, `dragon`, `master` ya da `football` içeriyor | `admin42` |
| `leet_speak` | bir harfi leet karşılığıyla birlikte içeriyor (`a` ile `4`, `s` ile `5` gibi) | `pa5sword` |

</details>

Bilmekte fayda var:

- `.gz` dosyaları hem girişte hem çıkışta çalışır.
- Bozuk UTF-8 içeren listeler (rockyou'da vardır) hatasız okunur; o satırlar değişmeden geri yazılır.
- Büyük listeler bütün işlemci çekirdeklerinde süzülür. Satırların sırası değişmez.
- İletiler varsayılan olarak Türkçedir. `--lang en`, `--config` ve `--analyze` çıktısını İngilizceye çevirir.
- Çalışırken `q` durdurur, `c` kayıt noktası alıp durdurur. Bu iki tuş yalnızca Windows'ta çalışır.

## Web arayüzü

```bash
python PassGenerator.py --webui
```

Tarayıcı `http://127.0.0.1:8765` adresinde üç araçla açılır: **Üret**, **Temizle** ve **Analiz et**. Yazarken listenin ilk satırları görünür, bir liste doğrudan sayfaya sürüklenip bırakılabilir ve her ekran aynı işi yapan komut satırını gösterir.

- Yalnızca kendi bilgisayarında çalışır. Hiçbir şey dışarı gönderilmez, sayfa internetten hiçbir şey yüklemez.
- Sonuçlar `output/` klasörüne yazılır.
- `--port 9000` başka bir port seçer. `--no-browser` yalnızca bağlantıyı yazar.
- `python WordlistFixer.py --webui` arayüzü Temizle sekmesinde açar.
- Sayfa Türkçe ve İngilizcedir.

## Perde arkası

- Satır sayısı ve dosya boyutu, daha hiçbir şey yazılmadan kelime uzunluklarından hesaplanır. Web arayüzü bunları sen yazarken gösterir.
- Üretici yalnızca `-m` ile `-M` arasına hâlâ sığabilecek kelime dizilerini izler. `--filters` ile, bir kuralın zaten sileceği dalları da bütünüyle atlar: tek kural açıkken 9 kelimelik örnekte silinen 2,2 milyon satırın 2,0 milyonu hiç üretilmez.
- Rust çekirdeği Python döngüsüyle aynı baytları yazmak zorundadır. Testler ikisini de sabit ve rastgele işlerde çalıştırıp dosyaları karşılaştırır.
- Tekrar eden satırlar Rust'ta satır başına yaklaşık 20 baytla, diskte ya da hiç tutulmadan izlenir; uzun işler kaldığı yerden sürdürülebilir.
- Web arayüzü Python'ın standart kütüphanesinden başka bir şeye ihtiyaç duymaz: derleme adımı yok, dışarıya istek yok. Yalnızca 127.0.0.1'i dinler, her açılışta üretilen bir anahtarı ve isteğin nereden geldiğini denetler, sıkı bir içerik güvenliği politikası gönderir.
- 250'den fazla Python testi ve 40 kadar Rust testi, Windows ve Linux'ta Python 3.9 ve 3.12 ile çalışır.

## Geliştirme

```bash
pip install -r requirements-dev.txt
pytest                                          # Python testleri
cargo test --manifest-path native/Cargo.toml    # Rust testleri
```

## Sorumlu kullanım ve lisans

Bu proje eğitim ve yetkili güvenlik testi içindir. Bir sistemi test etme izninin olduğundan emin olmak senin sorumluluğundadır. Yazar kötüye kullanımdan sorumlu değildir.

[MIT Lisansı](LICENSE) ile yayımlanır.

---

<div align="center">

[retgere5](https://github.com/retgere5) tarafından ❤️ ile yapıldı

</div>
