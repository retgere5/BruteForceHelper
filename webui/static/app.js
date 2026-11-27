/* BruteForce Helper web interface */
(() => {
  'use strict';

  const TOKEN = document.querySelector('meta[name="bfh-token"]').content;
  const BASE_TITLE = document.title;
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const motionOff = window.matchMedia('(prefers-reduced-motion: reduce)');
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const store = {
    get(key, fallback) {
      try {
        const raw = localStorage.getItem(`bfh.${key}`);
        return raw === null ? fallback : JSON.parse(raw);
      } catch (err) {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(`bfh.${key}`, JSON.stringify(value));
      } catch (err) {
        /* storage unavailable (private window): settings just aren't remembered */
      }
    },
  };

  /* ------------------------------------------------------------------ text */

  const STRINGS = {
    en: {
      'nav.label': 'Tools',
      'nav.generate': 'Generate',
      'nav.clean': 'Clean',
      'nav.analyze': 'Analyze',
      'nav.language': 'Language',
      'about.open': 'About',
      'common.more': 'More options',
      'common.fileName': 'File name',
      'common.cancel': 'Cancel',
      'common.close': 'Close',
      'num.down': 'Decrease',
      'num.up': 'Increase',
      'dock.copy': 'Copy',
      'dock.copied': 'Command copied',
      'dock.stop': 'Stop',
      'dock.stopping': 'Stopping…',
      'dock.rate': '{n} per second',
      'dock.left': '{t} left',
      'dock.days': '{n} days',
      'dock.years': '{n} years',
      'dock.elapsed': '{t} elapsed',
      'dock.counting': 'Counting lines…',
      'gen.words': 'Words',
      'gen.wordsHint': 'Names, years, symbols: anything you want combined. Press Enter after each one.',
      'gen.wordsPlaceholder': 'Type a word',
      'gen.wordsMore': 'Add another',
      'gen.wordCount': '{n} words',
      'gen.wordCountOne': '1 word',
      'gen.wordSample': 'word',
      'gen.removeWord': 'Remove {word}',
      'gen.tooMany': 'Up to {n} words',
      'gen.try': 'Try',
      'gen.length': 'Length',
      'gen.min': 'Shortest',
      'gen.max': 'Longest',
      'gen.affix': 'Before and after',
      'gen.prefix': 'Before',
      'gen.suffix': 'After',
      'gen.variations': 'Variations',
      'gen.variationsHint': 'Each one adds another version of every result.',
      'var.uppercase': 'UPPERCASE',
      'var.capitalize': 'Capitalized',
      'var.leet': 'Leet',
      'var.reverse': 'Reversed',
      'var.reverse_capitalize': 'Reversed, capitalized',
      'var.reverse_upper': 'Reversed, uppercase',
      'gen.limit': 'Stop after (results)',
      'gen.limitPlaceholder': 'No limit',
      'gen.dupes': 'Duplicates',
      'dupes.memory': 'Remove',
      'dupes.disk': 'Remove, low memory',
      'dupes.none': 'Keep',
      'dupes.memoryHint': 'Fastest. Memory use grows with the list.',
      'dupes.diskHint': 'Uses a temporary file on disk instead of memory. Slower.',
      'dupes.noneHint': 'Memory stays flat, but the same line can appear more than once.',
      'gen.maxMemory': 'Memory cap (MB)',
      'gen.gzip': 'Compress (.gz)',
      'gen.estimate': 'estimated results',
      'gen.estimateLimited': 'results, capped by your limit',
      'gen.firstLines': 'First {n} lines of your list',
      'gen.empty': 'Add a word and the first lines of your list show up here.',
      'gen.window': 'In the window',
      'gen.ringWords': 'words per line',
      'gen.freshKey': 'New since your last change',
      'gen.rules': 'Cleaning rules',
      'gen.rulesHint': 'A switched-on rule drops a line before it is written: the file gets smaller, the run gets slower.',
      'gen.estimateRules': 'results at most; the rules will drop some',
      'gen.largeRules': 'Large run: at most {size} on disk, less once the rules drop lines.',
      'gen.removedByRules': 'The rules dropped {n} lines.',
      'dock.removed': '{n} dropped by rules',
      'gen.large': 'Large run: roughly {size} on disk.',
      'gen.huge': 'This would practically never finish. Set a longest length or a result limit.',
      'gen.run': 'Generate',
      'gen.written': 'written so far',
      'gen.linesWritten': 'written',
      'gen.saved': 'results saved',
      'gen.stoppedLimit': 'Stopped at your result limit.',
      'gen.stoppedMemory': 'Stopped at the memory cap.',
      'gen.stoppedUser': 'Stopped. Everything written so far is saved.',
      'gen.needWords': 'Add at least one word',
      'gen.badRange': 'Shortest is longer than longest',
      'gen.tooLong': 'Lengths go up to {n}',
      'confirm.title': 'Start a large run?',
      'confirm.body': 'This could write about {count} lines ({size}). You can stop it at any time and keep what was written.',
      'confirm.bodyHuge': 'This run has no realistic end. It keeps writing until you stop it or the disk fills up.',
      'confirm.start': 'Start',
      'src.title': 'Wordlist',
      'src.drop': 'Drop a wordlist here',
      'src.types': 'Plain text or .gz, any size',
      'src.choose': 'Choose file',
      'src.path': 'Use a path on this computer',
      'src.pathPlaceholder': 'C:\\wordlists\\list.txt',
      'src.use': 'Use',
      'src.change': 'Change',
      'src.recent': 'From this session',
      'src.uploading': 'Copying {pct}%',
      'origin.output': 'made here',
      'origin.upload': 'copied in',
      'origin.local': 'on this computer',
      'clean.filters': 'What to remove',
      'clean.filtersHint': 'A line is removed when any switched-on rule matches it.',
      'clean.activeCount': '{n} on',
      'clean.all': 'All',
      'clean.none': 'None',
      'clean.example': 'e.g. {x}',
      'clean.suggest': 'Suggested for a file this size: {name}',
      'clean.apply': 'Apply',
      'clean.applied': 'Suggested rules switched on',
      'clean.length': 'Keep only these lengths',
      'clean.lengthHint': 'Optional. Lines outside the range are dropped before the rules run.',
      'clean.stats': 'Save a statistics report',
      'clean.run': 'Clean list',
      'clean.before': 'lines in',
      'clean.after': 'lines kept',
      'clean.removedBy': 'Removed by',
      'clean.idle': 'Pick a wordlist and switch on some rules. What each rule removes is counted here.',
      'clean.nothing': 'Nothing removed so far.',
      'clean.lengthRule': 'Outside the length range',
      'clean.reduced': '{pct} smaller',
      'clean.keptShare': 'kept',
      'clean.needFile': 'Choose a wordlist first',
      'clean.needRule': 'Switch on at least one rule',
      'clean.badRange': 'Shortest is longer than longest',
      'clean.copyConfig': 'Copy config',
      'clean.configCopied': 'Config copied. Save it as clean.json next to the tool.',
      'an.hint': 'Every line is counted: lengths, the character mix and how they spread.',
      'an.empty': 'Pick a wordlist to see what is inside: lengths, character mix and more.',
      'an.run': 'Analyze',
      'an.total': 'passwords',
      'an.totalPartial': 'passwords read before you stopped',
      'an.shortest': 'Shortest',
      'an.average': 'Average',
      'an.longest': 'Longest',
      'an.lengths': 'Length distribution',
      'an.lengthTip': '{len} characters: {count} ({pct})',
      'an.lengthTipOver': '{len}+ characters: {count} ({pct})',
      'an.mix': 'Character mix',
      'an.read': '{n} lines read',
      'an.lines': 'lines',
      'an.needFile': 'Choose a wordlist first',
      'mix.digit_only': 'Digits only',
      'mix.alpha_only': 'Letters only',
      'mix.has_upper': 'Has an uppercase letter',
      'mix.has_lower': 'Has a lowercase letter',
      'mix.has_digit': 'Has a digit',
      'mix.has_special': 'Has a symbol',
      'res.download': 'Download',
      'res.reveal': 'Show in folder',
      'res.clean': 'Clean it',
      'res.analyze': 'Analyze it',
      'res.stats': 'Statistics report',
      'res.meta': '{size}, {lines} lines',
      'toast.saved': 'Saved {name}',
      'toast.stopped': 'Stopped. {name} keeps what was written.',
      'toast.analyzed': 'Analysis ready',
      'toast.cleaned': 'Cleaned list saved as {name}',
      'about.body': 'Build wordlists from your own words, clean up existing lists and see what is inside them.',
      'about.local': 'Everything runs on this computer. The page is served from 127.0.0.1, only this machine can open it, and nothing is sent anywhere.',
      'about.output': 'Files are saved in',
      'about.shortcutTitle': 'Shortcut',
      'about.shortcut': 'Ctrl + Enter runs the open tool',
      'about.licenseTitle': 'License',
      'about.responsible': 'Use it for learning, and only on systems you own or have written permission to test.',
      'about.source': 'Source code',
      'consent.title': 'Before you start',
      'consent.body': 'BruteForce Helper is for learning about password security and for testing systems you own or have written permission to test.',
      'consent.check': 'I understand and will use it responsibly.',
      'consent.continue': 'Continue',
      'err.network': 'Lost touch with the local server. Is it still running in the terminal?',
      'err.busy': 'Three jobs are already running. Wait for one to finish or stop it.',
      'err.fileMissing': 'That file is no longer there.',
      'err.noSuchPath': 'There is no file at that path.',
      'err.notFound': 'Not found. Try choosing the file again.',
      'err.invalid': 'Check “{field}”.',
      'err.upload': 'Copying the file did not finish.',
      'err.reveal': 'Could not open the folder.',
      'err.jobFailed': 'The job stopped with an error: {msg}',
      'err.generic': 'Something went wrong: {msg}',
      'field.words': 'Words',
      'field.min_length': 'Shortest',
      'field.max_length': 'Longest',
      'field.limit': 'Stop after',
      'field.max_memory': 'Memory cap',
      'field.prefix': 'Before',
      'field.suffix': 'After',
      'field.dedup': 'Duplicates',
      'field.path': 'Path',
      'field.filters': 'Rules',
      'field.modifiers': 'Variations',
      'filter.min_length_filter': 'Shorter than 4 characters',
      'filter.repetitive_chars': 'Same character 4+ times in a row',
      'filter.pattern_repetition': 'A chunk repeated back to back',
      'filter.number_only': 'Digits only, 6+ long',
      'filter.letter_only': 'Letters only, 6+ long',
      'filter.single_char_type': 'Only one kind of character',
      'filter.sequential_chars': 'Runs like abcd or 4321',
      'filter.keyboard_patterns': 'Keyboard rows',
      'filter.special_patterns': 'Symbol runs',
      'filter.year_patterns': 'Contains a year (1900–2099)',
      'filter.date_patterns': 'Contains a date',
      'filter.phone_patterns': 'Phone numbers (Turkish format)',
      'filter.common_words': 'Common words',
      'filter.leet_speak': 'Half-leet words',
    },
    tr: {
      'nav.label': 'Araçlar',
      'nav.generate': 'Üret',
      'nav.clean': 'Temizle',
      'nav.analyze': 'Analiz et',
      'nav.language': 'Dil',
      'about.open': 'Hakkında',
      'common.more': 'Diğer seçenekler',
      'common.fileName': 'Dosya adı',
      'common.cancel': 'Vazgeç',
      'common.close': 'Kapat',
      'num.down': 'Azalt',
      'num.up': 'Artır',
      'dock.copy': 'Kopyala',
      'dock.copied': 'Komut kopyalandı',
      'dock.stop': 'Durdur',
      'dock.stopping': 'Durduruluyor…',
      'dock.rate': 'saniyede {n}',
      'dock.left': '{t} kaldı',
      'dock.days': '{n} gün',
      'dock.years': '{n} yıl',
      'dock.elapsed': '{t} geçti',
      'dock.counting': 'Satırlar sayılıyor…',
      'gen.words': 'Kelimeler',
      'gen.wordsHint': 'İsimler, yıllar, semboller: birleştirmek istediğin her şey. Her birinden sonra Enter\'a bas.',
      'gen.wordsPlaceholder': 'Bir kelime yaz',
      'gen.wordsMore': 'Bir tane daha ekle',
      'gen.wordCount': '{n} kelime',
      'gen.wordCountOne': '1 kelime',
      'gen.wordSample': 'kelime',
      'gen.removeWord': '{word} kelimesini kaldır',
      'gen.tooMany': 'En fazla {n} kelime',
      'gen.try': 'Dene',
      'gen.length': 'Uzunluk',
      'gen.min': 'En kısa',
      'gen.max': 'En uzun',
      'gen.affix': 'Başına ve sonuna',
      'gen.prefix': 'Başına',
      'gen.suffix': 'Sonuna',
      'gen.variations': 'Varyasyonlar',
      'gen.variationsHint': 'Her biri, her sonucun bir sürümünü daha ekler.',
      'var.uppercase': 'BÜYÜK HARF',
      'var.capitalize': 'Baş harfi büyük',
      'var.leet': 'Leet',
      'var.reverse': 'Ters',
      'var.reverse_capitalize': 'Ters, baş harfi büyük',
      'var.reverse_upper': 'Ters, büyük harf',
      'gen.limit': 'Şu kadar sonuçta dur',
      'gen.limitPlaceholder': 'Sınırsız',
      'gen.dupes': 'Tekrarlar',
      'dupes.memory': 'Kaldır',
      'dupes.disk': 'Kaldır, az bellekle',
      'dupes.none': 'Bırak',
      'dupes.memoryHint': 'En hızlısı. Bellek kullanımı listeyle birlikte büyür.',
      'dupes.diskHint': 'Bellek yerine diskte geçici bir dosya kullanır. Daha yavaş.',
      'dupes.noneHint': 'Bellek sabit kalır ama aynı satır birden fazla çıkabilir.',
      'gen.maxMemory': 'Bellek sınırı (MB)',
      'gen.gzip': 'Sıkıştır (.gz)',
      'gen.estimate': 'tahmini sonuç',
      'gen.estimateLimited': 'sonuç, sınırınla kısıtlı',
      'gen.firstLines': 'Listenin ilk {n} satırı',
      'gen.empty': 'Bir kelime ekle; listenin ilk satırları burada görünsün.',
      'gen.window': 'Pencerede',
      'gen.ringWords': 'kelimelik satır',
      'gen.freshKey': 'Son değişiklikle gelenler',
      'gen.rules': 'Temizleme kuralları',
      'gen.rulesHint': 'Açık bir kural, satırı diske yazmadan atar: dosya küçülür, üretim yavaşlar.',
      'gen.estimateRules': 'sonuç, en fazla; kurallar bir kısmını atacak',
      'gen.largeRules': 'Büyük iş: diskte en fazla {size}; kurallar satır attıkça daha az.',
      'gen.removedByRules': 'Kurallar {n} satırı attı.',
      'dock.removed': 'kurallarla {n} atıldı',
      'gen.large': 'Büyük iş: diskte yaklaşık {size}.',
      'gen.huge': 'Bu iş pratikte hiç bitmez. En uzun uzunluk ya da bir sonuç sınırı belirle.',
      'gen.run': 'Üret',
      'gen.written': 'şu ana kadar yazıldı',
      'gen.linesWritten': 'yazıldı',
      'gen.saved': 'sonuç kaydedildi',
      'gen.stoppedLimit': 'Sonuç sınırına ulaşınca durdu.',
      'gen.stoppedMemory': 'Bellek sınırında durdu.',
      'gen.stoppedUser': 'Durduruldu. O ana kadar yazılanların hepsi kaydedildi.',
      'gen.needWords': 'En az bir kelime ekle',
      'gen.badRange': 'En kısa, en uzundan büyük',
      'gen.tooLong': 'Uzunluk en fazla {n} olabilir',
      'confirm.title': 'Büyük bir iş başlatılsın mı?',
      'confirm.body': 'Bu iş yaklaşık {count} satır ({size}) yazabilir. İstediğin an durdurup o ana kadar yazılanı tutabilirsin.',
      'confirm.bodyHuge': 'Bu işin gerçekçi bir sonu yok. Sen durdurana ya da disk dolana kadar yazmaya devam eder.',
      'confirm.start': 'Başlat',
      'src.title': 'Kelime listesi',
      'src.drop': 'Bir kelime listesini buraya bırak',
      'src.types': 'Düz metin ya da .gz, her boyutta',
      'src.choose': 'Dosya seç',
      'src.path': 'Bu bilgisayardaki bir yolu kullan',
      'src.pathPlaceholder': 'C:\\listeler\\liste.txt',
      'src.use': 'Kullan',
      'src.change': 'Değiştir',
      'src.recent': 'Bu oturumdan',
      'src.uploading': 'Kopyalanıyor %{pct}',
      'origin.output': 'burada üretildi',
      'origin.upload': 'kopyalandı',
      'origin.local': 'bu bilgisayarda',
      'clean.filters': 'Neler atılsın',
      'clean.filtersHint': 'Açık kurallardan herhangi birine uyan satır atılır.',
      'clean.activeCount': '{n} açık',
      'clean.all': 'Tümü',
      'clean.none': 'Hiçbiri',
      'clean.example': 'örn. {x}',
      'clean.suggest': 'Bu boyuttaki bir dosya için öneri: {name}',
      'clean.apply': 'Uygula',
      'clean.applied': 'Önerilen kurallar açıldı',
      'clean.length': 'Yalnızca bu uzunlukları tut',
      'clean.lengthHint': 'İsteğe bağlı. Aralığın dışındaki satırlar kurallardan önce atılır.',
      'clean.stats': 'İstatistik raporu kaydet',
      'clean.run': 'Listeyi temizle',
      'clean.before': 'giren satır',
      'clean.after': 'kalan satır',
      'clean.removedBy': 'Atan kural',
      'clean.idle': 'Bir liste seç ve birkaç kural aç. Her kuralın neyi attığı burada sayılır.',
      'clean.nothing': 'Şimdilik hiçbir şey atılmadı.',
      'clean.lengthRule': 'Uzunluk aralığının dışında',
      'clean.reduced': '{pct} küçüldü',
      'clean.keptShare': 'kaldı',
      'clean.needFile': 'Önce bir liste seç',
      'clean.needRule': 'En az bir kural aç',
      'clean.badRange': 'En kısa, en uzundan büyük',
      'clean.copyConfig': 'Ayarları kopyala',
      'clean.configCopied': 'Ayarlar kopyalandı. Aracın yanına clean.json olarak kaydet.',
      'an.hint': 'Her satır sayılır: uzunluklar, karakter dağılımı ve nasıl yayıldıkları.',
      'an.empty': 'İçinde ne olduğunu görmek için bir liste seç: uzunluklar, karakter dağılımı ve fazlası.',
      'an.run': 'Analiz et',
      'an.total': 'şifre',
      'an.totalPartial': 'şifre, durdurmadan önce okunan',
      'an.shortest': 'En kısa',
      'an.average': 'Ortalama',
      'an.longest': 'En uzun',
      'an.lengths': 'Uzunluk dağılımı',
      'an.lengthTip': '{len} karakter: {count} ({pct})',
      'an.lengthTipOver': '{len}+ karakter: {count} ({pct})',
      'an.mix': 'Karakter dağılımı',
      'an.read': '{n} satır okundu',
      'an.lines': 'satır',
      'an.needFile': 'Önce bir liste seç',
      'mix.digit_only': 'Sadece rakam',
      'mix.alpha_only': 'Sadece harf',
      'mix.has_upper': 'Büyük harf içeriyor',
      'mix.has_lower': 'Küçük harf içeriyor',
      'mix.has_digit': 'Rakam içeriyor',
      'mix.has_special': 'Sembol içeriyor',
      'res.download': 'İndir',
      'res.reveal': 'Klasörde göster',
      'res.clean': 'Temizle',
      'res.analyze': 'Analiz et',
      'res.stats': 'İstatistik raporu',
      'res.meta': '{size}, {lines} satır',
      'toast.saved': '{name} kaydedildi',
      'toast.stopped': 'Durduruldu. {name} o ana kadar yazılanları tutuyor.',
      'toast.analyzed': 'Analiz hazır',
      'toast.cleaned': 'Temizlenen liste {name} olarak kaydedildi',
      'about.body': 'Kendi kelimelerinden liste üret, mevcut listeleri temizle ve içlerinde ne olduğunu gör.',
      'about.local': 'Her şey bu bilgisayarda çalışır. Sayfa 127.0.0.1 üzerinden sunulur; yalnızca bu makine açabilir ve hiçbir şey dışarı gönderilmez.',
      'about.output': 'Dosyaların kaydedildiği yer',
      'about.shortcutTitle': 'Kısayol',
      'about.shortcut': 'Ctrl + Enter açık olan aracı çalıştırır',
      'about.licenseTitle': 'Lisans',
      'about.responsible': 'Öğrenmek için ve yalnızca sana ait ya da yazılı test izni olan sistemlerde kullan.',
      'about.source': 'Kaynak kod',
      'consent.title': 'Başlamadan önce',
      'consent.body': 'BruteForce Helper, şifre güvenliğini öğrenmek ve sana ait ya da yazılı test izni olan sistemleri test etmek içindir.',
      'consent.check': 'Anladım, sorumlu şekilde kullanacağım.',
      'consent.continue': 'Devam et',
      'err.network': 'Yerel sunucuyla bağlantı koptu. Terminalde hâlâ çalışıyor mu?',
      'err.busy': 'Zaten üç iş çalışıyor. Birinin bitmesini bekle ya da birini durdur.',
      'err.fileMissing': 'Bu dosya artık yerinde değil.',
      'err.noSuchPath': 'Bu yolda bir dosya yok.',
      'err.notFound': 'Bulunamadı. Dosyayı yeniden seçmeyi dene.',
      'err.invalid': '“{field}” alanını kontrol et.',
      'err.upload': 'Dosyanın kopyalanması tamamlanamadı.',
      'err.reveal': 'Klasör açılamadı.',
      'err.jobFailed': 'İş bir hatayla durdu: {msg}',
      'err.generic': 'Bir sorun çıktı: {msg}',
      'field.words': 'Kelimeler',
      'field.min_length': 'En kısa',
      'field.max_length': 'En uzun',
      'field.limit': 'Şu kadar sonuçta dur',
      'field.max_memory': 'Bellek sınırı',
      'field.prefix': 'Başına',
      'field.suffix': 'Sonuna',
      'field.dedup': 'Tekrarlar',
      'field.path': 'Yol',
      'field.filters': 'Kurallar',
      'field.modifiers': 'Varyasyonlar',
      'filter.min_length_filter': '4 karakterden kısa',
      'filter.repetitive_chars': 'Aynı karakter art arda 4+ kez',
      'filter.pattern_repetition': 'Art arda tekrarlanan parça',
      'filter.number_only': 'Sadece rakam (6+ karakter)',
      'filter.letter_only': 'Sadece harf (6+ karakter)',
      'filter.single_char_type': 'Tek tür karakter',
      'filter.sequential_chars': 'abcd, 4321 gibi diziler',
      'filter.keyboard_patterns': 'Klavye sıraları',
      'filter.special_patterns': 'Sembol dizileri',
      'filter.year_patterns': 'Yıl içeriyor (1900–2099)',
      'filter.date_patterns': 'Tarih içeriyor',
      'filter.phone_patterns': 'Telefon numarası (TR biçimi)',
      'filter.common_words': 'Yaygın kelimeler',
      'filter.leet_speak': 'Yarım leet kelimeler',
    },
  };

  const FILTER_EXAMPLES = {
    min_length_filter: 'abc',
    repetitive_chars: 'aaaa1',
    pattern_repetition: 'abab, 123123',
    number_only: '123456',
    letter_only: 'dragon',
    single_char_type: 'hello, 2024',
    sequential_chars: 'abcd1, x4321',
    keyboard_patterns: 'qwerty1',
    special_patterns: 'pass!@#',
    year_patterns: 'ali1987',
    date_patterns: '01.02.2003',
    phone_patterns: '05321234567',
    common_words: 'password1',
    leet_speak: 's3cret',
  };
  const MODIFIERS = ['uppercase', 'capitalize', 'reverse', 'reverse_capitalize', 'reverse_upper', 'leet'];
  const MODIFIER_FLAGS = {
    uppercase: '-AB', capitalize: '-Ab', reverse: '-ba', reverse_capitalize: '-Ba', reverse_upper: '-BA', leet: '-L337',
  };
  const MIX_KEYS = ['digit_only', 'alpha_only', 'has_upper', 'has_lower', 'has_digit', 'has_special'];
  // FilterStats counts the "too short" rule under a different key than the option
  const STAT_TO_RULE = { min_length: 'min_length_filter' };
  const EXAMPLE_WORDS = ['admin', 'root', '2024', 'summer', '!'];
  const LEET = { a: '4', b: '8', e: '3', g: '6', i: '1', l: '1', o: '0', s: '5', t: '7', z: '2' };
  const BIG_RUN = 50000000;
  const HUGE_RUN = 1e12;
  const POLL_MS = 350;
  const HIST_CAP = 32;

  let lang = store.get('lang', null);
  if (lang !== 'tr' && lang !== 'en') lang = (navigator.language || '').toLowerCase().startsWith('tr') ? 'tr' : 'en';
  let meta = null;
  let limits = { words: 200, word_chars: 100, length: 128 };
  let activeView = 'generate';
  const views = {};

  function t(key, vars) {
    let text = STRINGS[lang][key];
    if (text === undefined) text = STRINGS.en[key];
    if (text === undefined) text = key;
    if (vars) text = text.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? String(vars[name]) : match));
    return text;
  }

  function applyI18n(root = document) {
    $$('[data-i18n]', root).forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $$('[data-i18n-placeholder]', root).forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
    $$('[data-i18n-label]', root).forEach((el) => { el.setAttribute('aria-label', t(el.dataset.i18nLabel)); });
    $$('[data-i18n-title]', root).forEach((el) => { el.title = t(el.dataset.i18nTitle); });
  }

  /* ------------------------------------------------------------ formatting */

  const locale = () => (lang === 'tr' ? 'tr-TR' : 'en-US');
  const fmt = (n) => new Intl.NumberFormat(locale()).format(n);
  const fmtCompact = (n) => new Intl.NumberFormat(locale(), { notation: 'compact', maximumFractionDigits: 1 }).format(n);
  const pct = (part, whole) => new Intl.NumberFormat(locale(), { style: 'percent', maximumFractionDigits: 1 }).format(whole ? part / whole : 0);
  const str = (value, fallback) => (typeof value === 'string' ? value : fallback);
  const toInt = (value) => {
    const n = Number.parseInt(value, 10);
    return Number.isFinite(n) && n > 0 ? n : null;
  };

  function fmtBytes(bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    const digits = unit && value < 10 ? 1 : 0;
    return `${new Intl.NumberFormat(locale(), { maximumFractionDigits: digits }).format(value)} ${units[unit]}`;
  }

  function fmtDuration(seconds) {
    const total = Math.max(0, Math.round(seconds));
    // past two days a clock reading stops meaning anything
    if (total >= 31557600) return t('dock.years', { n: fmtCompact(Math.round(total / 31557600)) });
    if (total >= 172800) return t('dock.days', { n: fmt(Math.round(total / 86400)) });
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    const pad = (x) => String(x).padStart(2, '0');
    return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
  }

  const encoder = new TextEncoder();
  const averageBytes = (lines) => (lines.length
    ? lines.reduce((sum, line) => sum + encoder.encode(line).length + 1, 0) / lines.length
    : 9);
  // The server works the size out exactly; the sample average is only a fallback
  const sizeOf = (data) => (typeof data.bytes === 'number' ? data.bytes : data.estimate * averageBytes(data.sample));

  // Display-only quoting for the "same thing on the command line" strip
  const shellQuote = (s) => (/^[\w@%+=:,./\\-]+$/.test(s) ? s : `"${s.replace(/(["\\$`])/g, '\\$1')}"`);

  const reverseText = (w) => Array.from(w).reverse().join('');
  const capitalize = (w) => (w ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : w);
  const leet = (w) => Array.from(w).map((c) => LEET[c.toLowerCase()] || c).join('');
  const VARIANT_SAMPLE = {
    uppercase: (w) => w.toUpperCase(),
    capitalize,
    leet,
    reverse: reverseText,
    reverse_capitalize: (w) => capitalize(reverseText(w)),
    reverse_upper: (w) => reverseText(w).toUpperCase(),
  };

  // A word's position in the list picks its ink everywhere: chip, ring and line
  const INK_COUNT = 6;
  const inkClass = (index) => `ink-${index % INK_COUNT}`;

  // Which words a line is made of. Case and leet variants fold onto one
  // canonical spelling; a reversed variant reads that spelling backwards.
  const canon = (s) => Array.from(s.toLowerCase()).map((c) => LEET[c] || c).join('');

  function splitLine(line, words, prefix, suffix) {
    const text = canon(line);
    if (!words.length || text.length !== line.length || Array.from(line).length !== line.length) return null;
    const forms = words.map(canon);
    if (forms.some((form, i) => !form || form.length !== words[i].length)) return null;
    const pre = canon(prefix || '');
    const suf = canon(suffix || '');
    const parse = (s) => {
      if (s.length <= pre.length + suf.length || !s.startsWith(pre) || !s.endsWith(suf)) return null;
      const core = s.slice(pre.length, s.length - suf.length);
      const steps = new Array(core.length + 1).fill(null);
      steps[0] = { from: -1, word: -1 };
      for (let i = 0; i < core.length; i += 1) {
        if (!steps[i]) continue;
        forms.forEach((form, word) => {
          const end = i + form.length;
          if (end <= core.length && !steps[end] && core.startsWith(form, i)) steps[end] = { from: i, word };
        });
      }
      if (!steps[core.length]) return null;
      const tokens = [];
      for (let at = core.length; at > 0; at = steps[at].from) tokens.unshift(steps[at].word);
      return tokens;
    };
    let reversed = false;
    let tokens = parse(text);
    if (!tokens) {
      tokens = parse(reverseText(text));
      reversed = true;
    }
    if (!tokens) return null;
    const pieces = [];
    if (pre) pieces.push({ length: pre.length, ink: 'ink-affix' });
    tokens.forEach((word) => pieces.push({ length: forms[word].length, ink: inkClass(word) }));
    if (suf) pieces.push({ length: suf.length, ink: 'ink-affix' });
    if (reversed) pieces.reverse();
    let at = 0;
    const segments = pieces.map((piece) => {
      const segment = { text: line.slice(at, at + piece.length), ink: piece.ink };
      at += piece.length;
      return segment;
    });
    return { segments, tokens };
  }

  /* ------------------------------------------------------------------- API */

  class ApiError extends Error {
    constructor(code, field, detail) {
      super(code);
      this.code = code;
      this.field = field;
      this.detail = detail;
    }
  }

  async function api(path, { method = 'GET', body, signal } = {}) {
    const headers = { 'X-Token': TOKEN };
    const init = { method, headers, signal };
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    let response;
    try {
      response = await fetch(path, init);
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      throw new ApiError('network');
    }
    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      /* empty body */
    }
    if (!response.ok) throw new ApiError((data && data.error) || 'server_error', data && data.field, data && data.message);
    return data;
  }

  function sendFile(file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload');
      xhr.setRequestHeader('X-Token', TOKEN);
      xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name));
      xhr.setRequestHeader('Content-Type', 'application/octet-stream');
      xhr.upload.addEventListener('progress', (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); });
      xhr.addEventListener('load', () => {
        let data = null;
        try { data = JSON.parse(xhr.responseText); } catch (err) { /* not JSON */ }
        if (xhr.status >= 200 && xhr.status < 300 && data) resolve(data.file);
        else reject(new ApiError((data && data.error) || 'upload', data && data.field, data && data.message));
      });
      xhr.addEventListener('error', () => reject(new ApiError('network')));
      xhr.send(file);
    });
  }

  function errorText(err) {
    if (!(err instanceof ApiError)) return t('err.generic', { msg: (err && err.message) || String(err) });
    switch (err.code) {
      case 'network': return t('err.network');
      case 'busy': return t('err.busy');
      case 'file_missing': return t('err.fileMissing');
      case 'not_found': return t('err.notFound');
      case 'invalid': return t('err.invalid', { field: t(`field.${err.field}`) });
      case 'upload':
      case 'incomplete_upload': return t('err.upload');
      case 'reveal_failed': return t('err.reveal');
      default: return t('err.generic', { msg: err.detail || err.code });
    }
  }

  /* ------------------------------------------------------------ components */

  function toast(message, kind = 'ok') {
    const el = document.createElement('div');
    el.className = kind === 'error' ? 'toast is-error' : 'toast';
    const text = document.createElement('span');
    text.textContent = message;
    el.append(text);
    $('#toasts').append(el);
    setTimeout(() => {
      el.classList.add('is-leaving');
      setTimeout(() => el.remove(), 400);
    }, kind === 'error' ? 6500 : 3400);
  }

  function icon(id) {
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('class', 'ico');
    const use = document.createElementNS(SVG_NS, 'use');
    use.setAttribute('href', `#${id}`);
    svg.append(use);
    return svg;
  }

  function showNotice(el, text, kind) {
    el.textContent = text;
    el.classList.toggle('is-danger', kind === 'danger');
    el.classList.toggle('is-info', kind === 'info');
    el.hidden = false;
  }

  function setNumber(el, value, { animate = true } = {}) {
    const to = Number(value) || 0;
    const from = Number(el.dataset.value || 0);
    el.dataset.value = String(to);
    el.classList.remove('is-placeholder');
    cancelAnimationFrame(el.rafId);
    if (!animate || motionOff.matches || from === to) {
      el.textContent = fmt(to);
      return;
    }
    const start = performance.now();
    const duration = 650;
    const step = (now) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - p) ** 3;
      el.textContent = fmt(Math.round(from + (to - from) * eased));
      if (p < 1) el.rafId = requestAnimationFrame(step);
    };
    el.rafId = requestAnimationFrame(step);
  }

  function setExponent(el, exponent) {
    cancelAnimationFrame(el.rafId);
    el.dataset.value = '0';
    el.classList.remove('is-placeholder');
    const sup = document.createElement('sup');
    sup.textContent = String(exponent);
    el.replaceChildren('≈ 10', sup);
  }

  function setDash(el) {
    cancelAnimationFrame(el.rafId);
    el.dataset.value = '0';
    el.textContent = '0';
    el.classList.add('is-placeholder');
  }

  // Lines "decode" into place: random glyphs settle into the real text
  const GLYPHS = 'abcdefghijklmnopqrstuvwxyz0123456789@#$%&*+=?';
  const decoding = new Map();
  let decodeFrame = 0;

  function decode(el, text, delay) {
    if (motionOff.matches) {
      el.textContent = text;
      return;
    }
    const chars = Array.from(text);
    decoding.set(el, { chars, start: performance.now() + delay, duration: 220 + Math.min(chars.length, 18) * 16 });
    if (!decodeFrame) decodeFrame = requestAnimationFrame(decodeStep);
  }

  function decodeStep(now) {
    decoding.forEach((item, el) => {
      const p = (now - item.start) / item.duration;
      if (p >= 1) {
        el.textContent = item.chars.join('');
        decoding.delete(el);
        return;
      }
      if (p < 0) {
        el.textContent = '';
        return;
      }
      const shown = Math.floor(item.chars.length * p);
      let out = item.chars.slice(0, shown).join('');
      for (let i = shown; i < item.chars.length; i += 1) out += GLYPHS[(Math.random() * GLYPHS.length) | 0];
      el.textContent = out;
    });
    decodeFrame = decoding.size ? requestAnimationFrame(decodeStep) : 0;
  }

  // Each line is split into its words' inks; lines that were not in the
  // previous list stay marked until the list changes again
  function renderLines(list, lines, previous, parts = []) {
    const before = new Set(previous);
    const items = lines.map((line, index) => {
      const li = document.createElement('li');
      const text = document.createElement('span');
      text.className = 'line-text';
      li.append(text);
      const split = parts[index];
      const segments = split ? split.segments : [{ text: line, ink: '' }];
      const same = line === previous[index];
      let delay = Math.min(index, 24) * 18;
      segments.forEach((segment) => {
        const span = document.createElement('span');
        span.className = segment.ink ? `seg ${segment.ink}` : 'seg';
        text.append(span);
        if (same) {
          span.textContent = segment.text;
        } else {
          decode(span, segment.text, delay);
          delay += Array.from(segment.text).length * 14;
        }
      });
      if (previous.length && !before.has(line)) li.classList.add('is-fresh');
      return li;
    });
    list.replaceChildren(...items);
    return items;
  }

  // Keyed bars: existing rows keep their element so widths animate between updates
  function renderBars(container, entries, { label, value, max, ink }) {
    const top = max || Math.max(0, ...entries.map((entry) => entry[1]));
    const existing = new Map($$('.bar', container).map((el) => [el.dataset.key, el]));
    entries.forEach(([key, amount], index) => {
      let bar = existing.get(key);
      if (bar) {
        existing.delete(key);
      } else {
        bar = document.createElement('div');
        bar.className = 'bar';
        bar.dataset.key = key;
        bar.innerHTML = '<span class="bar-label"></span><span class="bar-value"></span><span class="bar-track"><span class="bar-fill"></span></span>';
      }
      if (container.children[index] !== bar) container.insertBefore(bar, container.children[index] || null);
      bar.className = ink ? `bar ${ink(key)}` : 'bar';
      $('.bar-label', bar).textContent = label(key);
      $('.bar-value', bar).textContent = value(amount);
      const fill = $('.bar-fill', bar);
      void fill.offsetWidth;
      fill.style.transform = `scaleX(${top ? Math.min(1, amount / top) : 0})`;
    });
    existing.forEach((el) => el.remove());
  }

  const ruleLabel = (key) => {
    if (key === '__length') return t('clean.lengthRule');
    const name = STAT_TO_RULE[key] || key;
    return STRINGS[lang][`filter.${name}`] || (meta.filter_text[lang] || {})[name] || name;
  };

  // The cleaning rules as switch rows: Temizle's list, and Üret's optional rules
  function renderRuleGroups(host, filters, onToggle) {
    const sections = Object.entries(meta.groups).map(([group, names]) => {
      const section = document.createElement('section');
      section.className = 'filter-group';
      const head = document.createElement('div');
      head.className = 'group-head';
      const title = document.createElement('h3');
      title.className = 'group-title';
      title.textContent = (meta.group_text[lang] || {})[group] || group;
      const all = document.createElement('button');
      all.type = 'button';
      all.className = 'group-all';
      all.addEventListener('click', () => onToggle(names, !names.every((name) => filters[name])));
      head.append(title, all);
      section.append(head);
      names.forEach((name) => {
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'filter-row';
        row.setAttribute('role', 'switch');
        row.dataset.filter = name;
        const text = document.createElement('span');
        text.className = 'filter-text';
        const label = document.createElement('span');
        label.className = 'filter-name';
        label.textContent = ruleLabel(name);
        text.append(label);
        if (FILTER_EXAMPLES[name]) {
          const example = document.createElement('span');
          example.className = 'filter-example';
          example.textContent = t('clean.example', { x: FILTER_EXAMPLES[name] });
          text.append(example);
        }
        const knob = document.createElement('span');
        knob.className = 'switch';
        knob.setAttribute('aria-hidden', 'true');
        row.append(text, knob);
        row.addEventListener('click', () => onToggle([name], !filters[name]));
        section.append(row);
      });
      return section;
    });
    host.replaceChildren(...sections);
    syncRuleGroups(host, filters);
  }

  function syncRuleGroups(host, filters) {
    $$('.filter-row', host).forEach((row) => row.setAttribute('aria-checked', String(!!filters[row.dataset.filter])));
    $$('.filter-group', host).forEach((section) => {
      const names = $$('.filter-row', section).map((row) => row.dataset.filter);
      $('.group-all', section).textContent = names.every((name) => filters[name]) ? t('clean.none') : t('clean.all');
    });
  }

  function showResult(container, file, lineCount, actions) {
    const line = document.createElement('div');
    line.className = 'file-line';
    const text = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = file.name;
    name.title = file.path || file.name;
    const detail = document.createElement('span');
    detail.textContent = lineCount === null
      ? fmtBytes(file.size)
      : t('res.meta', { size: fmtBytes(file.size), lines: fmt(lineCount) });
    text.append(name, detail);
    line.append(icon('i-file'), text);
    const row = document.createElement('div');
    row.className = 'actions';
    actions.forEach(([key, iconId, handler], index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = index ? 'btn small ghost' : 'btn small';
      if (iconId) button.append(icon(iconId));
      const caption = document.createElement('span');
      caption.textContent = t(key);
      button.append(caption);
      button.addEventListener('click', handler);
      row.append(button);
    });
    container.replaceChildren(line, row);
    container.hidden = false;
  }

  function downloadFile(file) {
    const link = document.createElement('a');
    link.href = `/api/files/${file.id}/download?token=${encodeURIComponent(TOKEN)}`;
    link.download = file.name;
    document.body.append(link);
    link.click();
    link.remove();
  }

  async function revealFile(file) {
    try {
      await api(`/api/files/${file.id}/reveal`, { method: 'POST' });
    } catch (err) {
      toast(errorText(err), 'error');
    }
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.append(area);
      area.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      area.remove();
      return ok;
    }
  }

  function confirmDialog(body) {
    const dialog = $('#confirm');
    const ok = $('#confirm-ok');
    const cancel = $('#confirm-cancel');
    $('#confirm-body').textContent = body;
    return new Promise((resolve) => {
      let cleanup = () => {};
      const close = (answer) => {
        cleanup();
        if (dialog.open) dialog.close();
        resolve(answer);
      };
      const onOk = () => close(true);
      const onCancel = () => close(false);
      const onEscape = (e) => {
        e.preventDefault();
        close(false);
      };
      cleanup = () => {
        ok.removeEventListener('click', onOk);
        cancel.removeEventListener('click', onCancel);
        dialog.removeEventListener('cancel', onEscape);
      };
      ok.addEventListener('click', onOk);
      cancel.addEventListener('click', onCancel);
      dialog.addEventListener('cancel', onEscape);
      dialog.showModal();
      cancel.focus();
    });
  }

  function bindNumber(input, { min = 1, max = 999, allowEmpty = false, onInput }) {
    const box = input.closest('.num-box');
    const [down, up] = $$('.num-btn', box);
    const commit = (value) => {
      input.value = value === null ? '' : String(value);
      onInput(input.value);
    };
    const step = (delta) => {
      let value = toInt(input.value);
      if (value === null) value = delta > 0 ? min : null;
      else value += delta;
      if (value !== null && value < min) value = allowEmpty ? null : min;
      if (value !== null && value > max) value = max;
      commit(value);
    };
    input.addEventListener('input', () => {
      const cleaned = input.value.replace(/\D/g, '');
      if (cleaned !== input.value) input.value = cleaned;
      onInput(input.value);
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault();
        step(e.key === 'ArrowUp' ? 1 : -1);
      }
    });
    input.addEventListener('blur', () => {
      if (!allowEmpty && toInt(input.value) === null) commit(min);
    });
    down.addEventListener('click', () => step(-1));
    up.addEventListener('click', () => step(1));
  }

  function bindDigits(input, onInput) {
    input.addEventListener('input', () => {
      const cleaned = input.value.replace(/\D/g, '');
      if (cleaned !== input.value) input.value = cleaned;
      onInput(input.value);
    });
  }

  function bindSwitch(el, initial, onChange) {
    el.setAttribute('aria-checked', String(initial));
    el.addEventListener('click', () => {
      const on = el.getAttribute('aria-checked') !== 'true';
      el.setAttribute('aria-checked', String(on));
      onChange(on);
    });
  }

  function bindRadios(group, onChange) {
    const buttons = $$('[role="radio"]', group);
    buttons.forEach((button, index) => {
      button.addEventListener('click', () => onChange(button.dataset.value));
      button.addEventListener('keydown', (e) => {
        const keys = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
        if (!keys[e.key]) return;
        e.preventDefault();
        const next = buttons[(index + keys[e.key] + buttons.length) % buttons.length];
        next.focus();
        onChange(next.dataset.value);
      });
    });
    return (value) => buttons.forEach((button) => {
      const on = button.dataset.value === value;
      button.setAttribute('aria-checked', String(on));
      button.tabIndex = on ? 0 : -1;
    });
  }

  /* -------------------------------------------------------------- the wheel */

  // Every tool reads out on the same printed disc: a tick-marked rim, rings
  // of words or data, and a hub. Angles are radians from 12 o'clock, clockwise.
  const RIM = 200;
  const HUB = 58;
  let wheelCount = 0;
  let glyphRatio = 0;

  function svgNode(name, attrs, parent) {
    const node = document.createElementNS(SVG_NS, name);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (parent) parent.append(node);
    return node;
  }

  const polar = (r, a) => `${(r * Math.sin(a)).toFixed(2)} ${(-r * Math.cos(a)).toFixed(2)}`;

  function arcPath(inner, outer, from, to) {
    if (to - from >= Math.PI * 2 - 1e-6) {
      return `M${polar(outer, 0)}A${outer} ${outer} 0 1 1 ${polar(outer, Math.PI)}A${outer} ${outer} 0 1 1 ${polar(outer, 0)}`
        + `M${polar(inner, 0)}A${inner} ${inner} 0 1 0 ${polar(inner, Math.PI)}A${inner} ${inner} 0 1 0 ${polar(inner, 0)}Z`;
    }
    const large = to - from > Math.PI ? 1 : 0;
    return `M${polar(outer, from)}A${outer} ${outer} 0 ${large} 1 ${polar(outer, to)}`
      + `L${polar(inner, to)}A${inner} ${inner} 0 ${large} 0 ${polar(inner, from)}Z`;
  }

  // Width of one monospace glyph per pixel of font size
  function glyphWidth() {
    if (!glyphRatio) {
      const context = document.createElement('canvas').getContext('2d');
      const family = getComputedStyle(document.documentElement).getPropertyValue('--mono').trim() || 'monospace';
      context.font = `600 100px ${family}`;
      glyphRatio = context.measureText('0123456789').width / 1000 || 0.6;
    }
    return glyphRatio;
  }

  function createWheel(host, { withWindow = false } = {}) {
    wheelCount += 1;
    const svg = svgNode('svg', { viewBox: '-220 -220 440 440', focusable: 'false' }, host);
    svgNode('circle', { class: 'w-disc', r: RIM + 14 }, svg);
    const tick = RIM + 7;
    svgNode('circle', { class: 'w-ticks', r: tick, 'stroke-dasharray': `1.2 ${((2 * Math.PI * tick) / 72 - 1.2).toFixed(3)}` }, svg);
    const body = svgNode('g', {}, svg);
    const hubLayer = svgNode('g', {}, svg);
    svgNode('circle', { class: 'w-hub', r: HUB }, hubLayer);
    const main = svgNode('text', { class: 'w-hub-main' }, hubLayer);
    const sub = svgNode('text', { class: 'w-hub-sub', y: 21 }, hubLayer);
    if (withWindow) svgNode('rect', { class: 'w-window', x: -38, y: -(RIM + 16), width: 76, height: RIM + 16 - HUB - 2, rx: 12 }, svg);
    return {
      id: `wheel${wheelCount}`,
      svg,
      body,
      hub(value, caption) {
        const text = String(value);
        main.textContent = text;
        main.setAttribute('font-size', String(Math.max(17, Math.min(34, 40 - text.length * 3.2))));
        main.setAttribute('y', caption ? '-6' : '0');
        sub.textContent = caption || '';
      },
    };
  }

  // Üret: one ring per word position; the window reads the selected line
  function createWordWheel(host) {
    const base = createWheel(host, { withWindow: true });
    let rings = [];
    let shape = '';
    let frame = 0;

    function layout(words, count) {
      const next = JSON.stringify([words, count]);
      if (next === shape) return;
      shape = next;
      base.body.replaceChildren();
      rings = [];
      if (!words.length || !count) {
        [RIM - 30, RIM - 78, RIM - 118].forEach((r) => svgNode('circle', { class: 'w-empty', r }, base.body));
        return;
      }
      const band = (RIM - HUB - 6) / count;
      const ratio = glyphWidth();
      const chars = words.reduce((sum, word) => sum + Array.from(word).length, 0);
      for (let i = 0; i < count; i += 1) {
        const outer = RIM - i * band;
        const r = outer - band / 2;
        const length = 2 * Math.PI * r;
        if (i) svgNode('circle', { class: 'w-sep', r: outer.toFixed(2) }, base.body);
        let size = Math.min(16, band * 0.44);
        while (size > 9 && chars * ratio * size + words.length * size * 1.4 > length) size -= 0.5;
        const gap = size * 1.4;
        const widths = words.map((word) => Array.from(word).length * ratio * size);
        const order = [];
        let used = 0;
        for (let k = 0; k < 400; k += 1) {
          const word = k % words.length;
          if (used + widths[word] + gap > length) break;
          order.push(word);
          used += widths[word] + gap;
        }
        const extra = order.length ? (length - used) / order.length : 0;
        const ring = svgNode('g', { class: 'w-ring' }, base.body);
        const turn = svgNode('g', { class: 'w-turn' }, ring);
        const pathId = `${base.id}-r${i}`;
        const rr = r.toFixed(2);
        svgNode('path', { id: pathId, d: `M0 ${rr}A${rr} ${rr} 0 1 1 0 -${rr}A${rr} ${rr} 0 1 1 0 ${rr}`, fill: 'none' }, turn);
        const instances = [];
        let offset = (gap + extra) / 2;
        order.forEach((word) => {
          const center = offset + widths[word] / 2;
          const text = svgNode('text', { class: `w-word ${inkClass(word)}`, 'font-size': size.toFixed(1), 'dominant-baseline': 'central' }, turn);
          const along = svgNode('textPath', { href: `#${pathId}`, startOffset: center.toFixed(2), 'text-anchor': 'middle' }, text);
          along.textContent = words[word];
          // the path starts at 6 o'clock
          instances.push({ word, angle: (180 + (center / length) * 360) % 360 });
          offset += widths[word] + gap + extra;
        });
        rings.push({ ring, turn, instances, rotation: 0 });
      }
    }

    // Turn each ring the shortest way until its word sits in the window
    function show(tokens) {
      rings.forEach((entry, i) => {
        const word = tokens ? tokens[i] : undefined;
        const choices = word === undefined ? [] : entry.instances.filter((item) => item.word === word);
        entry.ring.classList.toggle('is-idle', !choices.length);
        if (!choices.length) return;
        let best = null;
        choices.forEach((item) => {
          const target = -item.angle;
          const candidate = target + Math.round((entry.rotation - target) / 360) * 360;
          if (best === null || Math.abs(candidate - entry.rotation) < Math.abs(best - entry.rotation)) best = candidate;
        });
        entry.rotation = best;
        entry.turn.style.transform = `rotate(${best.toFixed(2)}deg)`;
      });
    }

    // While a run writes, the rings keep turning; inner positions change fastest
    function spin(on) {
      const spinning = !!frame;
      if (!!on === spinning) return;
      cancelAnimationFrame(frame);
      frame = 0;
      base.svg.classList.toggle('is-spinning', !!on);
      if (!on || motionOff.matches) return;
      let last = performance.now();
      const step = (now) => {
        const seconds = Math.min(64, now - last) / 1000;
        last = now;
        rings.forEach((entry, i) => {
          entry.rotation += seconds * (36 + i * 52);
          entry.turn.style.transform = `rotate(${entry.rotation.toFixed(2)}deg)`;
        });
        frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    }

    return { layout, show, spin, hub: base.hub };
  }

  // Temizle: what was kept and what each rule removed, as exact shares
  function createArcWheel(host) {
    const base = createWheel(host);
    const outer = RIM - 4;
    const inner = RIM - 58;
    const layer = svgNode('g', {}, base.body);

    function clear() {
      layer.replaceChildren();
      svgNode('circle', { class: 'w-empty', r: (outer + inner) / 2 }, layer);
      base.hub('–');
    }

    function draw(parts, total) {
      layer.replaceChildren();
      if (!total) {
        clear();
        return;
      }
      let angle = 0;
      parts.forEach((part) => {
        const sweep = (part.value / total) * Math.PI * 2;
        if (sweep <= 0) return;
        const gap = sweep > 0.05 && sweep < Math.PI * 2 - 1e-6 ? 0.006 : 0;
        svgNode('path', { class: `w-arc ${part.ink}`, d: arcPath(inner, outer, angle + gap, angle + sweep - gap), 'fill-rule': 'evenodd' }, layer);
        angle += sweep;
      });
    }

    clear();
    return { draw, clear, hub: base.hub };
  }

  // Analiz et: a spoke per length (exact to its count) and the character mix
  function createStatsWheel(host) {
    const base = createWheel(host);
    const layer = svgNode('g', {}, base.body);

    function clear() {
      layer.replaceChildren();
      [RIM - 40, RIM - 108].forEach((r) => svgNode('circle', { class: 'w-empty', r }, layer));
      base.hub('–');
    }

    function draw(stats, buckets) {
      layer.replaceChildren();
      const keys = [...buckets.keys()].sort((a, b) => a - b);
      if (keys.length) {
        const first = keys[0];
        const span = keys[keys.length - 1] - first + 1;
        const slot = (Math.PI * 2) / span;
        const peak = Math.max(...buckets.values());
        const top = [...buckets.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map((entry) => entry[0]);
        const r0 = RIM - 78;
        const half = Math.min(slot * 0.36, 0.09);
        buckets.forEach((n, key) => {
          if (!n) return;
          const middle = (key - first + 0.5) * slot;
          const reach = r0 + Math.max(2, (n / peak) * (RIM - 4 - r0));
          svgNode('path', { class: top.includes(key) ? 'w-bar is-top' : 'w-bar', d: arcPath(r0, reach, middle - half, middle + half) }, layer);
        });
        top.forEach((key) => {
          const a = (key - first + 0.5) * slot;
          const label = svgNode('text', { class: 'w-label', x: (110 * Math.sin(a)).toFixed(2), y: (-110 * Math.cos(a)).toFixed(2) }, layer);
          label.textContent = key > HIST_CAP ? `${HIST_CAP + 1}+` : String(key);
        });
      }
      const total = stats.total || 0;
      const inner = RIM - 120;
      const outer = RIM - 96;
      let angle = 0;
      [['digit_only', 'ink-1'], ['alpha_only', 'ink-0']].forEach(([key, ink]) => {
        const sweep = total ? ((stats[key] || 0) / total) * Math.PI * 2 : 0;
        if (sweep > 0) svgNode('path', { class: `w-arc ${ink}`, d: arcPath(inner, outer, angle, angle + sweep), 'fill-rule': 'evenodd' }, layer);
        angle += sweep;
      });
      if (angle < Math.PI * 2 - 1e-6) svgNode('path', { class: 'w-arc is-rest', d: arcPath(inner, outer, angle, Math.PI * 2), 'fill-rule': 'evenodd' }, layer);
    }

    clear();
    return { draw, clear, hub: base.hub };
  }

  /* ------------------------------------------------------- command dock */

  function makeDock(el, runKey) {
    const code = $('.dock-code', el);
    const cmd = $('.dock-cmd', el);
    const status = $('.dock-status', el);
    const reason = $('.dock-reason', el);
    const run = $('.run', el);
    // While a job runs, a real progress bar with its percentage sits before the Stop button
    const meter = document.createElement('div');
    meter.className = 'dock-meter';
    meter.hidden = true;
    meter.setAttribute('role', 'progressbar');
    meter.setAttribute('aria-valuemin', '0');
    meter.setAttribute('aria-valuemax', '100');
    meter.innerHTML = '<span class="dock-track"><span class="dock-bar"></span></span><span class="dock-pct"></span>';
    el.insertBefore(meter, run);
    const bar = $('.dock-bar', meter);
    const percent = $('.dock-pct', meter);
    const show = (fraction) => {
      const value = Math.max(0, Math.min(1, fraction));
      bar.style.transform = `scaleX(${value})`;
      percent.textContent = pct(value, 1);
      meter.setAttribute('aria-valuenow', String(Math.round(value * 100)));
    };
    run.textContent = t(runKey);
    return {
      run,
      copy: $('.dock-copy', el),
      setCommand(text, placeholder) {
        code.textContent = text;
        code.title = placeholder ? '' : text;
        code.classList.toggle('is-placeholder', !!placeholder);
      },
      setReason(text) { reason.textContent = text || ''; },
      setRunning(running, stopping) {
        el.classList.toggle('is-running', running);
        cmd.hidden = running;
        status.hidden = !running;
        meter.hidden = !running;
        reason.hidden = running;
        run.classList.toggle('is-stop', running);
        run.textContent = t(running ? (stopping ? 'dock.stopping' : 'dock.stop') : runKey);
        run.disabled = running && !!stopping;
        if (!running) el.classList.remove('is-indeterminate');
      },
      setProgress(fraction) {
        if (fraction === null || fraction === undefined) {
          el.classList.add('is-indeterminate');
          percent.textContent = '…';
          meter.removeAttribute('aria-valuenow');
          return;
        }
        el.classList.remove('is-indeterminate');
        show(fraction);
      },
      setStatus(main, parts) {
        const strong = document.createElement('strong');
        strong.textContent = main;
        const extra = parts.filter(Boolean).map((part) => {
          const span = document.createElement('span');
          span.textContent = part;
          return span;
        });
        status.replaceChildren(strong, ...extra);
      },
      complete() { show(1); },
      reset() { show(0); },
    };
  }

  function timing(job, done, total) {
    const elapsed = job.elapsed || 0;
    const rate = elapsed > 0.5 ? done / elapsed : 0;
    const parts = [];
    if (rate) parts.push(t('dock.rate', { n: fmt(Math.round(rate)) }));
    if (rate && total && total > done) parts.push(t('dock.left', { t: fmtDuration((total - done) / rate) }));
    else parts.push(t('dock.elapsed', { t: fmtDuration(elapsed) }));
    return parts;
  }

  function titleProgress(fraction) {
    document.title = fraction === null ? BASE_TITLE : `${Math.round(fraction * 100)}% – ${BASE_TITLE}`;
  }

  // A view's job: start, poll, stop
  function watchJob(slot, job, { onProgress, onDone, onFailed }) {
    slot.id = job.id;
    slot.active = true;
    slot.stopping = false;
    slot.dock.reset();
    slot.dock.setRunning(true, false);
    slot.panel.classList.add('is-running');
    let failures = 0;
    const finish = () => {
      slot.active = false;
      slot.dock.setRunning(false);
      slot.panel.classList.remove('is-running');
      titleProgress(null);
    };
    const poll = async () => {
      let current;
      try {
        current = await api(`/api/jobs/${slot.id}`);
        failures = 0;
      } catch (err) {
        failures += 1;
        if (failures === 3) toast(errorText(err), 'error');
        slot.timer = setTimeout(poll, Math.min(5000, 600 * failures));
        return;
      }
      if (current.state === 'running') {
        onProgress(current);
        slot.timer = setTimeout(poll, POLL_MS);
        return;
      }
      finish();
      if (current.state === 'error') {
        slot.dock.reset();
        toast(t('err.jobFailed', { msg: current.error }), 'error');
        if (onFailed) onFailed(current);
      } else {
        slot.dock.complete();
        onDone(current);
      }
      slot.refresh();
    };
    onProgress(job);
    slot.timer = setTimeout(poll, 200);
  }

  async function stopJob(slot) {
    if (!slot.active || slot.stopping) return;
    slot.stopping = true;
    slot.dock.setRunning(true, true);
    try {
      await api(`/api/jobs/${slot.id}/stop`, { method: 'POST' });
    } catch (err) {
      slot.stopping = false;
      slot.dock.setRunning(true, false);
      toast(errorText(err), 'error');
    }
  }

  /* --------------------------------------------------- choosing a wordlist */

  const recentFiles = [];
  const pickers = [];

  function addRecent(file) {
    const index = recentFiles.findIndex((f) => f.id === file.id);
    if (index >= 0) recentFiles.splice(index, 1);
    recentFiles.unshift(file);
    recentFiles.length = Math.min(recentFiles.length, 6);
    pickers.forEach((picker) => picker.renderRecent());
  }

  function createPicker(host, onChange) {
    host.append($('#tpl-source').content.cloneNode(true));
    applyI18n(host);
    const part = (name) => $(`[data-part="${name}"]`, host);
    const drop = part('drop');
    const fileInput = part('file');
    const pathForm = part('path-form');
    const pathInput = part('path');
    const upload = part('upload');
    const card = part('card');
    const recent = part('recent');
    let current = null;
    let busy = false;
    let dragDepth = 0;

    function showCard() {
      drop.hidden = !!current;
      card.hidden = !current;
      upload.hidden = true;
      if (!current) return;
      pathForm.hidden = true;
      part('name').textContent = current.name;
      part('name').title = current.path || current.name;
      part('meta').textContent = `${fmtBytes(current.size)}, ${t(`origin.${current.origin}`)}`;
    }

    function renderRecent() {
      const items = recentFiles.filter((f) => !current || f.id !== current.id);
      recent.hidden = !items.length;
      part('recent-list').replaceChildren(...items.map((f) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'recent-item';
        button.textContent = f.name;
        button.title = f.path || f.name;
        button.addEventListener('click', () => set(f));
        return button;
      }));
    }

    function set(file) {
      current = file || null;
      showCard();
      renderRecent();
      onChange(current);
    }

    async function uploadFile(file) {
      if (busy || !file) return;
      busy = true;
      drop.hidden = true;
      pathForm.hidden = true;
      card.hidden = true;
      upload.hidden = false;
      const fill = part('upload-fill');
      const text = part('upload-text');
      const update = (p) => {
        fill.style.transform = `scaleX(${p})`;
        text.textContent = t('src.uploading', { pct: Math.round(p * 100) });
      };
      update(0);
      try {
        const info = await sendFile(file, update);
        addRecent(info);
        set(info);
      } catch (err) {
        toast(errorText(err), 'error');
        showCard();
      } finally {
        busy = false;
        upload.hidden = true;
      }
    }

    drop.addEventListener('click', (e) => { if (!e.target.closest('button')) fileInput.click(); });
    drop.addEventListener('dragenter', () => {
      dragDepth += 1;
      drop.classList.add('is-over');
    });
    drop.addEventListener('dragleave', () => {
      dragDepth = Math.max(0, dragDepth - 1);
      if (!dragDepth) drop.classList.remove('is-over');
    });
    drop.addEventListener('drop', () => {
      dragDepth = 0;
      drop.classList.remove('is-over');
    });
    part('choose').addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
      uploadFile(fileInput.files[0]);
      fileInput.value = '';
    });
    part('path-toggle').addEventListener('click', () => {
      pathForm.hidden = false;
      pathInput.focus();
    });
    part('path-cancel').addEventListener('click', () => { pathForm.hidden = true; });
    pathForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const value = pathInput.value.trim();
      if (!value) return;
      try {
        const data = await api('/api/files/local', { method: 'POST', body: { path: value } });
        pathInput.value = '';
        addRecent(data.file);
        set(data.file);
      } catch (err) {
        toast(err.code === 'file_missing' ? t('err.noSuchPath') : errorText(err), 'error');
      }
    });
    part('change').addEventListener('click', () => set(null));

    const picker = {
      set,
      get: () => current,
      upload: uploadFile,
      renderRecent,
      renderTexts() {
        showCard();
        renderRecent();
      },
    };
    pickers.push(picker);
    return picker;
  }

  /* -------------------------------------------------------------- generate */

  function initGenerate() {
    const saved = store.get('generate', {}) || {};
    const state = {
      words: Array.isArray(saved.words)
        ? saved.words.filter((w) => typeof w === 'string' && w && !/[\s,;]/.test(w)).slice(0, limits.words)
        : [],
      min: str(saved.min, '1') || '1',
      max: str(saved.max, ''),
      prefix: str(saved.prefix, ''),
      suffix: str(saved.suffix, ''),
      mods: {},
      output: str(saved.output, '') || 'combinations.txt',
      gzip: saved.gzip === true,
      limit: str(saved.limit, ''),
      dedup: ['memory', 'disk', 'none'].includes(saved.dedup) ? saved.dedup : 'memory',
      maxMemory: str(saved.maxMemory, ''),
    };
    MODIFIERS.forEach((mod) => { state.mods[mod] = !!(saved.mods && saved.mods[mod]); });
    const ruleNames = Object.values(meta.groups).flat();
    state.filters = {};
    ruleNames.forEach((name) => { state.filters[name] = !!(saved.filters && saved.filters[name]); });
    const activeRules = () => ruleNames.filter((name) => state.filters[name]);

    const chips = $('#word-chips');
    const input = $('#word-input');
    const count = $('#word-count');
    const core = $('#affix-core');
    const panel = $('#gen-panel');
    const bigCount = $('#gen-count');
    const caption = $('#gen-caption');
    const notice = $('#gen-notice');
    const listTitle = $('#gen-list-title');
    const lines = $('#gen-lines');
    const empty = $('#gen-empty');
    const result = $('#gen-result');
    const reading = $('#gen-reading');
    const freshKey = $('#gen-fresh-key');
    const wheel = createWordWheel($('#gen-wheel'));
    const dock = makeDock($('#gen-dock'), 'gen.run');
    const slot = { dock, panel, refresh: () => refresh() };
    let preview = null;
    let shown = [];
    let parts = [];
    let current = 0;
    let finished = null;
    let previewTimer = 0;
    let previewRequest = null;
    let saveTimer = 0;

    const problem = () => {
      if (!state.words.length) return t('gen.needWords');
      const min = toInt(state.min) || 1;
      const max = toInt(state.max);
      if (min > limits.length || (max && max > limits.length)) return t('gen.tooLong', { n: limits.length });
      if (max && min > max) return t('gen.badRange');
      return '';
    };

    const params = () => ({
      words: state.words,
      min_length: toInt(state.min) || 1,
      max_length: toInt(state.max),
      modifiers: state.mods,
      prefix: state.prefix || null,
      suffix: state.suffix || null,
      limit: toInt(state.limit),
      max_memory: state.dedup === 'memory' ? toInt(state.maxMemory) : null,
      dedup: state.dedup,
      gzip: state.gzip,
      output: state.output,
      filters: activeRules(),
    });

    function command() {
      if (!state.words.length) return { text: 'python PassGenerator.py -w …', placeholder: true };
      const p = params();
      const parts = ['python', 'PassGenerator.py', '-w', ...p.words.map(shellQuote)];
      if (p.min_length > 1) parts.push('-m', String(p.min_length));
      if (p.max_length) parts.push('-M', String(p.max_length));
      MODIFIERS.forEach((mod) => { if (p.modifiers[mod]) parts.push(MODIFIER_FLAGS[mod]); });
      if (p.prefix) parts.push('-ws', shellQuote(p.prefix));
      if (p.suffix) parts.push('-we', shellQuote(p.suffix));
      const name = state.output.trim();
      if (name && name !== 'combinations.txt') parts.push('-o', shellQuote(name));
      if (p.gzip) parts.push('-z');
      if (p.limit) parts.push('--limit', String(p.limit));
      if (p.dedup === 'none') parts.push('--no-dedup');
      if (p.dedup === 'disk') parts.push('--disk-dedup');
      if (p.max_memory) parts.push('--max-memory', String(p.max_memory));
      if (p.filters.length) parts.push('--filters', p.filters.length === ruleNames.length ? 'all' : p.filters.join(','));
      return { text: parts.join(' ') };
    }

    function renderRules() {
      renderRuleGroups($('#gen-groups'), state.filters, (names, on) => {
        names.forEach((name) => { state.filters[name] = on; });
        syncRules();
        changed();
      });
      syncRules();
    }

    function syncRules() {
      syncRuleGroups($('#gen-groups'), state.filters);
      const n = activeRules().length;
      $('#gen-rules-count').textContent = n ? t('clean.activeCount', { n }) : '';
    }

    function makeChip(word) {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.dataset.word = word;
      const text = document.createElement('span');
      text.className = 'chip-text';
      text.textContent = word;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'chip-remove';
      remove.setAttribute('aria-label', t('gen.removeWord', { word }));
      remove.innerHTML = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 3l6 6M9 3l-6 6"/></svg>';
      remove.addEventListener('click', (e) => {
        e.stopPropagation();
        removeWord(word);
        input.focus();
      });
      chip.append(text, remove);
      return chip;
    }

    function renderChips() {
      const existing = new Map($$('.chip:not(.is-leaving)', chips).map((el) => [el.dataset.word, el]));
      state.words.forEach((word, index) => {
        let chip = existing.get(word);
        if (chip) {
          existing.delete(word);
        } else {
          chip = makeChip(word);
          chips.insertBefore(chip, input);
        }
        chip.className = `chip ${inkClass(index)}`;
      });
      existing.forEach((chip) => {
        if (motionOff.matches) {
          chip.remove();
          return;
        }
        chip.classList.add('is-leaving');
        chip.addEventListener('animationend', () => chip.remove(), { once: true });
      });
    }

    function addWords(raw) {
      const parts = String(raw).split(/[\s,;]+/).filter(Boolean);
      let added = false;
      for (const part of parts) {
        if (state.words.length >= limits.words) {
          toast(t('gen.tooMany', { n: limits.words }), 'error');
          break;
        }
        const word = part.slice(0, limits.word_chars);
        if (!state.words.includes(word)) {
          state.words.push(word);
          added = true;
        }
      }
      if (added) {
        renderChips();
        changed();
      }
    }

    function removeWord(word) {
      state.words = state.words.filter((w) => w !== word);
      renderChips();
      changed();
    }

    function renderVariants() {
      const sample = state.words[0] || 'password';
      $$('.variant').forEach((button) => {
        const mod = button.dataset.mod;
        button.setAttribute('aria-pressed', String(state.mods[mod]));
        $('.variant-sample', button).textContent = VARIANT_SAMPLE[mod](sample);
      });
      core.textContent = state.words[0] || t('gen.wordSample');
    }

    const setDedup = bindRadios($('#gen-dedup'), (value) => {
      state.dedup = value;
      renderDedup();
      changed();
    });

    function renderDedup() {
      setDedup(state.dedup);
      $('#dedup-hint').textContent = t(`dupes.${state.dedup}Hint`);
      $('#gen-memory-field').hidden = state.dedup !== 'memory';
    }

    // How many words a line can hold, the same bounds the generator uses
    function tokenBounds() {
      if (!state.words.length) return null;
      const lengths = state.words.map((word) => Array.from(word).length);
      const max = toInt(state.max);
      const most = max ? Math.floor(max / Math.min(...lengths)) : state.words.length;
      const fewest = Math.max(1, Math.ceil((toInt(state.min) || 1) / Math.max(...lengths)));
      return { fewest, most };
    }

    function showRange() {
      const bounds = tokenBounds();
      if (!bounds || bounds.most < bounds.fewest) {
        wheel.hub('–');
        return;
      }
      const range = bounds.most > bounds.fewest ? `${fmt(bounds.fewest)}–${fmt(bounds.most)}` : fmt(bounds.most);
      wheel.hub(range, t('gen.ringWords'));
    }

    function selectLine(index) {
      const items = lines.children;
      if (!items.length) {
        reading.replaceChildren();
        wheel.show(null);
        return;
      }
      current = Math.max(0, Math.min(items.length - 1, index));
      Array.from(items).forEach((li, i) => li.classList.toggle('is-current', i === current));
      const split = parts[current];
      const segments = split ? split.segments : [{ text: shown[current] || '', ink: '' }];
      reading.replaceChildren(...segments.map((segment) => {
        const span = document.createElement('span');
        span.className = segment.ink ? `seg ${segment.ink}` : 'seg';
        span.textContent = segment.text;
        return span;
      }));
      wheel.show(split ? split.tokens : null);
    }

    function refresh() {
      renderVariants();
      const bounds = tokenBounds();
      wheel.layout(state.words, bounds ? Math.max(1, Math.min(4, bounds.most)) : 0);
      if (!slot.active) showRange();
      const cmd = command();
      dock.setCommand(cmd.text, cmd.placeholder);
      const issue = problem();
      if (!slot.active) {
        dock.run.disabled = !!issue;
        dock.setReason(issue);
      }
      const n = state.words.length;
      count.textContent = n ? (n === 1 ? t('gen.wordCountOne') : t('gen.wordCount', { n: fmt(n) })) : '';
      input.placeholder = n ? t('gen.wordsMore') : t('gen.wordsPlaceholder');
    }

    function changed() {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => store.set('generate', state), 300);
      if (finished && !slot.active) clearResult();
      refresh();
      schedulePreview();
    }

    function schedulePreview() {
      clearTimeout(previewTimer);
      previewTimer = setTimeout(runPreview, 200);
    }

    function showEmpty() {
      preview = null;
      setNumber(bigCount, 0);
      caption.textContent = t('gen.estimate');
      notice.hidden = true;
      listTitle.textContent = '';
      lines.replaceChildren();
      shown = [];
      parts = [];
      freshKey.hidden = true;
      empty.hidden = false;
      selectLine(0);
    }

    function renderPreview(data, animate = true) {
      empty.hidden = true;
      const limit = toInt(state.limit);
      if (data.estimate === null) setExponent(bigCount, data.exponent);
      else setNumber(bigCount, data.estimate, { animate });
      let key = limit && data.estimate === limit ? 'gen.estimateLimited' : 'gen.estimate';
      if (data.filtered) key = 'gen.estimateRules';
      caption.textContent = t(key);
      if (data.estimate === null || data.estimate > HUGE_RUN) {
        showNotice(notice, t('gen.huge'), 'danger');
      } else if (data.estimate > meta.large_threshold) {
        const size = fmtBytes(sizeOf(data));
        showNotice(notice, t(data.filtered ? 'gen.largeRules' : 'gen.large', { size }), 'warn');
      } else {
        notice.hidden = true;
      }
      listTitle.textContent = t('gen.firstLines', { n: fmt(data.sample.length) });
      parts = data.sample.map((line) => splitLine(line, state.words, state.prefix, state.suffix));
      if (animate) {
        renderLines(lines, data.sample, shown, parts);
        freshKey.hidden = !lines.querySelector('.is-fresh');
      }
      shown = data.sample;
      selectLine(animate ? 0 : current);
    }

    async function runPreview() {
      if (slot.active || finished) return;
      if (!state.words.length) {
        showEmpty();
        return;
      }
      if (problem()) return;
      if (previewRequest) previewRequest.abort();
      previewRequest = new AbortController();
      try {
        preview = await api('/api/generate/preview', { method: 'POST', body: params(), signal: previewRequest.signal });
        renderPreview(preview);
      } catch (err) {
        if (err.name === 'AbortError') return;
        if (err.code === 'invalid') dock.setReason(errorText(err));
        else toast(errorText(err), 'error');
      }
    }

    function clearResult() {
      finished = null;
      result.hidden = true;
      result.replaceChildren();
    }

    function renderDone(r) {
      setNumber(bigCount, r.written, { animate: false });
      caption.textContent = t('gen.saved');
      const reason = { limit: 'gen.stoppedLimit', memory: 'gen.stoppedMemory', user: 'gen.stoppedUser' }[r.stopped_by];
      const notes = [];
      if (reason) notes.push(t(reason));
      if (r.filtered_total) notes.push(t('gen.removedByRules', { n: fmt(r.filtered_total) }));
      if (notes.length) showNotice(notice, notes.join(' '), 'info');
      else notice.hidden = true;
      listTitle.textContent = r.head.length ? t('gen.firstLines', { n: fmt(r.head.length) }) : '';
      empty.hidden = true;
      showResult(result, r.file, r.written, [
        ['res.download', 'i-download', () => downloadFile(r.file)],
        ['res.reveal', 'i-folder', () => revealFile(r.file)],
        ['res.clean', null, () => {
          views.clean.useFile(r.file);
          selectView('clean');
        }],
        ['res.analyze', null, () => {
          views.analyze.useFile(r.file, true);
          selectView('analyze');
        }],
      ]);
    }

    function progress(job) {
      const p = job.progress || {};
      const done = p.done || 0;
      const total = p.total || null;
      // progress and speed follow the lines considered (the estimate counts those), not the lines kept
      const seen = p.processed || done;
      setNumber(bigCount, done);
      const fraction = total ? Math.min(0.99, seen / total) : 0;
      dock.setProgress(fraction);
      dock.setStatus(`${fmt(done)} ${t('gen.linesWritten')}`, [
        ...timing(job, seen, total),
        p.filtered ? t('dock.removed', { n: fmt(p.filtered) }) : '',
      ]);
      titleProgress(fraction);
      wheel.spin(true);
      if (total) wheel.hub(pct(fraction, 1), `${fmtCompact(done)} ${t('gen.linesWritten')}`);
      else wheel.hub(fmtCompact(done), t('gen.linesWritten'));
    }

    function done(job) {
      const r = job.result;
      finished = r;
      wheel.spin(false);
      showRange();
      lines.classList.remove('is-dim');
      parts = r.head.map((line) => splitLine(line, state.words, state.prefix, state.suffix));
      renderLines(lines, r.head, [], parts);
      shown = r.head;
      freshKey.hidden = true;
      selectLine(0);
      renderDone(r);
      addRecent(r.file);
      toast(t(job.state === 'stopped' ? 'toast.stopped' : 'toast.saved', { name: r.file.name }));
    }

    async function run() {
      if (slot.active) {
        stopJob(slot);
        return;
      }
      const issue = problem();
      if (issue) {
        toast(issue, 'error');
        return;
      }
      if (!toInt(state.limit) && preview && (preview.estimate === null || preview.estimate > BIG_RUN)) {
        const huge = preview.estimate === null || preview.estimate > HUGE_RUN;
        const body = huge
          ? t('confirm.bodyHuge')
          : t('confirm.body', { count: fmt(preview.estimate), size: fmtBytes(sizeOf(preview)) });
        if (!(await confirmDialog(body))) return;
      }
      try {
        const job = await api('/api/generate', { method: 'POST', body: params() });
        clearResult();
        lines.classList.add('is-dim');
        freshKey.hidden = true;
        caption.textContent = t('gen.written');
        notice.hidden = true;
        setNumber(bigCount, 0, { animate: false });
        watchJob(slot, job, {
          onProgress: progress,
          onDone: done,
          onFailed: () => {
            wheel.spin(false);
            showRange();
            lines.classList.remove('is-dim');
            schedulePreview();
          },
        });
      } catch (err) {
        toast(errorText(err), 'error');
      }
    }

    // wiring
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || (e.key === 'Tab' && input.value.trim())) {
        if (input.value.trim()) {
          e.preventDefault();
          addWords(input.value);
          input.value = '';
        }
      } else if (e.key === 'Backspace' && !input.value && state.words.length) {
        removeWord(state.words[state.words.length - 1]);
      }
    });
    // Separators are handled on input (not keydown) so phone keyboards, which
    // report every key as "Unidentified", split words the same way
    input.addEventListener('input', () => {
      if (!/[\s,;]/.test(input.value)) return;
      const parts = input.value.split(/[\s,;]/);
      const rest = parts.pop();
      addWords(parts.join(' '));
      input.value = rest;
    });
    input.addEventListener('paste', (e) => {
      const text = e.clipboardData && e.clipboardData.getData('text');
      if (text && /[\s,;]/.test(text.trim())) {
        e.preventDefault();
        addWords(text);
      }
    });
    input.addEventListener('blur', () => {
      if (input.value.trim()) {
        addWords(input.value);
        input.value = '';
      }
    });
    chips.addEventListener('click', (e) => { if (e.target === chips) input.focus(); });

    // Pointing at a line (or moving through the list with the arrow keys) turns the wheel to it
    lines.addEventListener('pointerover', (e) => {
      const li = e.target.closest('li');
      if (li && li.parentElement === lines) selectLine(Array.prototype.indexOf.call(lines.children, li));
    });
    lines.addEventListener('keydown', (e) => {
      const keys = { ArrowDown: 1, ArrowUp: -1, Home: 'first', End: 'last' };
      const key = keys[e.key];
      if (!key || !lines.children.length) return;
      e.preventDefault();
      if (key === 'first') selectLine(0);
      else if (key === 'last') selectLine(lines.children.length - 1);
      else selectLine(current + key);
      lines.children[current].scrollIntoView({ block: 'nearest' });
    });

    EXAMPLE_WORDS.forEach((word) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'example';
      button.textContent = word;
      button.addEventListener('click', () => addWords(word));
      $('#word-examples').append(button);
    });

    const minInput = $('#gen-min');
    const maxInput = $('#gen-max');
    minInput.value = state.min;
    maxInput.value = state.max;
    bindNumber(minInput, { min: 1, max: limits.length, onInput: (v) => { state.min = v; changed(); } });
    bindNumber(maxInput, { min: 1, max: limits.length, allowEmpty: true, onInput: (v) => { state.max = v; changed(); } });

    [['#gen-prefix', 'prefix'], ['#gen-suffix', 'suffix']].forEach(([selector, key]) => {
      const el = $(selector);
      el.value = state[key];
      el.addEventListener('input', () => {
        state[key] = el.value.replace(/[\r\n]/g, '');
        changed();
      });
    });

    $$('.variant').forEach((button) => {
      button.addEventListener('click', () => {
        state.mods[button.dataset.mod] = !state.mods[button.dataset.mod];
        changed();
      });
    });

    const outputInput = $('#gen-output');
    outputInput.value = state.output;
    outputInput.addEventListener('input', () => {
      state.output = outputInput.value;
      changed();
    });
    outputInput.addEventListener('blur', () => {
      if (!outputInput.value.trim()) {
        outputInput.value = 'combinations.txt';
        state.output = outputInput.value;
        changed();
      }
    });
    const limitInput = $('#gen-limit');
    limitInput.value = state.limit;
    bindDigits(limitInput, (v) => { state.limit = v; changed(); });
    const memoryInput = $('#gen-memory');
    memoryInput.value = state.maxMemory;
    bindDigits(memoryInput, (v) => { state.maxMemory = v; changed(); });
    bindSwitch($('#gen-gzip'), state.gzip, (on) => { state.gzip = on; changed(); });

    dock.run.addEventListener('click', run);
    dock.copy.addEventListener('click', async () => {
      if (!state.words.length) return;
      if (await copyText(command().text)) toast(t('dock.copied'));
    });

    renderChips();
    renderDedup();
    renderRules();
    refresh();
    if (state.words.length) schedulePreview();
    else showEmpty();

    return {
      run,
      busy: () => slot.active,
      renderTexts() {
        $$('.chip-remove', chips).forEach((button) => {
          button.setAttribute('aria-label', t('gen.removeWord', { word: button.parentElement.dataset.word }));
        });
        renderDedup();
        renderRules();
        if (slot.active) {
          dock.setRunning(true, slot.stopping);
          caption.textContent = t('gen.written');
        } else {
          dock.setRunning(false);
        }
        refresh();
        if (finished) renderDone(finished);
        else if (!slot.active && preview) renderPreview(preview, false);
        else if (!slot.active) showEmpty();
      },
    };
  }

  /* ----------------------------------------------------------------- clean */

  function initClean() {
    const saved = store.get('clean', {}) || {};
    const ruleNames = Object.values(meta.groups).flat();
    const state = {
      filters: {},
      min: str(saved.min, ''),
      max: str(saved.max, ''),
      output: str(saved.output, '') || 'optimized.txt',
      stats: saved.stats === true,
    };
    ruleNames.forEach((name) => { state.filters[name] = !!(saved.filters && saved.filters[name]); });

    const panel = $('#clean-panel');
    const inCount = $('#clean-in');
    const outCount = $('#clean-out');
    const bars = $('#clean-bars');
    const idle = $('#clean-empty');
    const reduced = $('#clean-reduced');
    const result = $('#clean-result');
    const suggest = $('#clean-suggest');
    const wheel = createArcWheel($('#clean-wheel'));
    const dock = makeDock($('#clean-dock'), 'clean.run');
    const slot = { dock, panel, refresh: () => refresh() };
    let finished = null;
    let lastEntries = [];
    let lastTotal = 0;
    let lastWheel = null;
    // Kept lines are cobalt. A rule gets the next free ink the first time it
    // removes something (so colours never shuffle mid-run); past five, grey.
    const REMOVAL_INKS = ['ink-1', 'ink-2', 'ink-4', 'ink-3', 'ink-5'];
    let inkByKey = new Map();
    const ruleInk = (key) => {
      if (!inkByKey.has(key)) inkByKey.set(key, REMOVAL_INKS[inkByKey.size] || 'ink-n');
      return inkByKey.get(key);
    };
    let saveTimer = 0;
    const picker = createPicker($('#clean-source'), (file) => {
      renderSuggest(file);
      changed();
    });

    const activeRules = () => ruleNames.filter((name) => state.filters[name]);

    const problem = () => {
      if (!picker.get()) return t('clean.needFile');
      const min = toInt(state.min);
      const max = toInt(state.max);
      if (min && max && min > max) return t('clean.badRange');
      if (!activeRules().length && !min && !max) return t('clean.needRule');
      return '';
    };

    function config() {
      const file = picker.get();
      const cfg = { input: file ? (file.path || file.name) : 'wordlist.txt', output: state.output.trim() || 'optimized.txt' };
      if (toInt(state.min)) cfg.min_length = toInt(state.min);
      if (toInt(state.max)) cfg.max_length = toInt(state.max);
      if (state.stats) cfg.keep_stats = true;
      activeRules().forEach((name) => { cfg[name] = true; });
      return cfg;
    }

    function renderGroups() {
      renderRuleGroups($('#clean-groups'), state.filters, (names, on) => {
        names.forEach((name) => { state.filters[name] = on; });
        syncRules();
        changed();
      });
      syncRules();
    }

    function syncRules() {
      syncRuleGroups($('#clean-groups'), state.filters);
      const n = activeRules().length;
      $('#clean-count').textContent = n ? t('clean.activeCount', { n }) : '';
    }

    function renderSuggest(file) {
      const tip = file && file.suggest && file.suggest[0];
      suggest.hidden = !tip;
      if (!tip) return;
      suggest.dataset.key = tip.key;
      $('#clean-suggest-text').textContent = t('clean.suggest', { name: (meta.suggest_text[lang] || {})[tip.key] || tip.key });
    }

    function ruleEntries(filters, removed) {
      const entries = Object.entries(filters || {}).filter((entry) => entry[1] > 0);
      const byRules = entries.reduce((sum, entry) => sum + entry[1], 0);
      if (removed > byRules) entries.push(['__length', removed - byRules]);
      return entries.sort((a, b) => b[1] - a[1]);
    }

    function drawBars(entries, total) {
      lastEntries = entries;
      lastTotal = total;
      renderBars(bars, entries, {
        label: ruleLabel,
        value: (n) => `${fmt(n)} (${pct(n, total)})`,
        ink: ruleInk,
      });
    }

    function drawWheel(total, processed, kept, entries) {
      lastWheel = [total, processed, kept, entries];
      wheel.draw([{ value: kept, ink: 'is-kept' }, ...entries.map(([key, n]) => ({ value: n, ink: ruleInk(key) }))], total);
      if (processed) wheel.hub(pct(kept, processed), t('clean.keptShare'));
      else wheel.hub('–');
    }

    function resetFunnel() {
      setDash(inCount);
      setDash(outCount);
      bars.replaceChildren();
      wheel.clear();
      lastWheel = null;
      inkByKey = new Map();
      lastEntries = [];
      reduced.hidden = true;
      idle.textContent = t('clean.idle');
      idle.hidden = false;
    }

    function clearResult() {
      finished = null;
      result.hidden = true;
      result.replaceChildren();
      resetFunnel();
    }

    function refresh() {
      dock.setCommand('python WordlistFixer.py --config clean.json', !picker.get());
      const issue = problem();
      if (!slot.active) {
        dock.run.disabled = !!issue;
        dock.setReason(issue);
      }
    }

    function changed() {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => store.set('clean', { filters: state.filters, min: state.min, max: state.max, output: state.output, stats: state.stats }), 300);
      if (finished && !slot.active) clearResult();
      refresh();
    }

    function renderDone(r) {
      setNumber(inCount, r.total, { animate: false });
      setNumber(outCount, r.remaining, { animate: false });
      const entries = ruleEntries(r.filters, r.removed);
      drawBars(entries, r.total);
      drawWheel(r.total, r.total, r.remaining, entries);
      idle.textContent = t('clean.nothing');
      idle.hidden = entries.length > 0;
      reduced.textContent = t('clean.reduced', { pct: pct(r.removed, r.total) });
      reduced.hidden = !r.removed;
      const actions = [
        ['res.download', 'i-download', () => downloadFile(r.file)],
        ['res.reveal', 'i-folder', () => revealFile(r.file)],
        ['res.analyze', null, () => {
          views.analyze.useFile(r.file, true);
          selectView('analyze');
        }],
      ];
      if (r.stats_file) actions.splice(1, 0, ['res.stats', 'i-file', () => downloadFile(r.stats_file)]);
      showResult(result, r.file, r.remaining, actions);
    }

    function progress(job) {
      const p = job.progress || {};
      const total = p.total;
      if (total === null || total === undefined) {
        dock.setProgress(null);
        dock.setStatus(t('dock.counting'), [t('dock.elapsed', { t: fmtDuration(job.elapsed || 0) })]);
        return;
      }
      const done = p.done || 0;
      const removed = p.removed || 0;
      setNumber(inCount, total);
      setNumber(outCount, done - removed);
      const entries = ruleEntries(p.filters, removed);
      drawBars(entries, total);
      drawWheel(total, done, done - removed, entries);
      idle.textContent = t('clean.nothing');
      idle.hidden = entries.length > 0;
      const fraction = total ? done / total : 0;
      dock.setProgress(fraction);
      dock.setStatus(`${fmt(done)} / ${fmt(total)}`, timing(job, done, total));
      titleProgress(fraction);
    }

    function done(job) {
      finished = job.result;
      renderDone(finished);
      addRecent(finished.file);
      toast(job.state === 'stopped'
        ? t('toast.stopped', { name: finished.file.name })
        : t('toast.cleaned', { name: finished.file.name }));
    }

    async function run() {
      if (slot.active) {
        stopJob(slot);
        return;
      }
      const issue = problem();
      if (issue) {
        toast(issue, 'error');
        return;
      }
      const body = {
        file_id: picker.get().id,
        filters: state.filters,
        min_length: toInt(state.min),
        max_length: toInt(state.max),
        output: state.output,
        stats: state.stats,
      };
      try {
        const job = await api('/api/clean', { method: 'POST', body });
        clearResult();
        setNumber(inCount, 0, { animate: false });
        setNumber(outCount, 0, { animate: false });
        watchJob(slot, job, { onProgress: progress, onDone: done, onFailed: resetFunnel });
      } catch (err) {
        toast(errorText(err), 'error');
      }
    }

    // wiring
    const minInput = $('#clean-min');
    const maxInput = $('#clean-max');
    minInput.value = state.min;
    maxInput.value = state.max;
    bindNumber(minInput, { min: 1, max: 9999, allowEmpty: true, onInput: (v) => { state.min = v; changed(); } });
    bindNumber(maxInput, { min: 1, max: 9999, allowEmpty: true, onInput: (v) => { state.max = v; changed(); } });
    const outputInput = $('#clean-output');
    outputInput.value = state.output;
    outputInput.addEventListener('input', () => {
      state.output = outputInput.value;
      changed();
    });
    outputInput.addEventListener('blur', () => {
      if (!outputInput.value.trim()) {
        outputInput.value = 'optimized.txt';
        state.output = outputInput.value;
        changed();
      }
    });
    bindSwitch($('#clean-stats'), state.stats, (on) => { state.stats = on; changed(); });
    $('#clean-suggest-apply').addEventListener('click', () => {
      const file = picker.get();
      const tip = file && file.suggest && file.suggest.find((s) => s.key === suggest.dataset.key);
      if (!tip) return;
      ruleNames.forEach((name) => { state.filters[name] = tip.filters.includes(name); });
      syncRules();
      changed();
      toast(t('clean.applied'));
    });
    dock.run.addEventListener('click', run);
    dock.copy.addEventListener('click', async () => {
      if (await copyText(JSON.stringify(config(), null, 2))) toast(t('clean.configCopied'));
    });

    renderGroups();
    resetFunnel();
    refresh();

    return {
      run,
      picker,
      busy: () => slot.active,
      useFile(file) { picker.set(file); },
      renderTexts() {
        renderGroups();
        renderSuggest(picker.get());
        picker.renderTexts();
        if (slot.active) dock.setRunning(true, slot.stopping);
        else dock.setRunning(false);
        refresh();
        if (finished) {
          renderDone(finished);
        } else if (slot.active) {
          drawBars(lastEntries, lastTotal);
          if (lastWheel) drawWheel(...lastWheel);
        } else {
          idle.textContent = t('clean.idle');
        }
        [inCount, outCount].forEach((el) => {
          if (!el.classList.contains('is-placeholder')) setNumber(el, el.dataset.value, { animate: false });
        });
      },
    };
  }

  /* --------------------------------------------------------------- analyze */

  function initAnalyze() {
    const panel = $('#an-panel');
    const wheel = createStatsWheel($('#an-wheel'));
    const dock = makeDock($('#an-dock'), 'an.run');
    const slot = { dock, panel, refresh: () => refresh() };
    let finished = null;
    const picker = createPicker($('#analyze-source'), () => refresh());

    const problem = () => (picker.get() ? '' : t('an.needFile'));

    function command() {
      const file = picker.get();
      return file
        ? { text: `python WordlistFixer.py --analyze ${shellQuote(file.path || file.name)}` }
        : { text: 'python WordlistFixer.py --analyze …', placeholder: true };
    }

    function refresh() {
      const cmd = command();
      dock.setCommand(cmd.text, cmd.placeholder);
      const issue = problem();
      if (!slot.active) {
        dock.run.disabled = !!issue;
        dock.setReason(issue);
      }
    }

    // Lengths past HIST_CAP share one "32+" bucket
    function lengthBuckets(counts) {
      const buckets = new Map();
      Object.entries(counts || {}).forEach(([length, n]) => {
        const key = Number(length) > HIST_CAP ? HIST_CAP + 1 : Number(length);
        buckets.set(key, (buckets.get(key) || 0) + n);
      });
      return buckets;
    }

    function renderHistogram(host, buckets, total) {
      if (!buckets.size) {
        host.replaceChildren();
        return;
      }
      const keys = [...buckets.keys()];
      const first = Math.min(...keys);
      const last = Math.max(...keys);
      const peak = Math.max(...buckets.values());
      const top = [...buckets.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map((entry) => entry[0]);
      const span = last - first + 1;
      const every = span > 24 ? 4 : span > 12 ? 2 : 1;
      const columns = document.createElement('div');
      columns.className = 'hist-cols';
      const axis = document.createElement('div');
      axis.className = 'hist-axis';
      const tip = document.createElement('div');
      tip.className = 'tooltip';
      tip.hidden = true;
      const tipText = (key, n) => t(key > HIST_CAP ? 'an.lengthTipOver' : 'an.lengthTip', {
        len: key > HIST_CAP ? HIST_CAP + 1 : key, count: fmt(n), pct: pct(n, total),
      });
      for (let key = first; key <= last; key += 1) {
        const n = buckets.get(key) || 0;
        const column = document.createElement('div');
        column.className = top.includes(key) && n ? 'hist-col is-top' : 'hist-col';
        const bar = document.createElement('span');
        bar.className = 'hist-bar';
        bar.style.height = n ? `${Math.max(1.5, (n / peak) * 100)}%` : '0';
        bar.style.animationDelay = `${Math.min(key - first, 30) * 16}ms`;
        column.append(bar);
        column.addEventListener('pointerenter', () => {
          tip.textContent = tipText(key, n);
          tip.hidden = false;
          tip.style.left = `${column.offsetLeft + column.offsetWidth / 2}px`;
          tip.style.top = `${columns.offsetHeight * (1 - n / peak)}px`;
        });
        column.addEventListener('pointerleave', () => { tip.hidden = true; });
        columns.append(column);
        const tick = document.createElement('span');
        tick.textContent = key > HIST_CAP ? `${HIST_CAP + 1}+` : ((key - first) % every === 0 ? String(key) : '');
        axis.append(tick);
      }
      host.replaceChildren(columns, axis, tip);
      host.setAttribute('role', 'img');
      host.setAttribute('aria-label', tipText(top[0], buckets.get(top[0])));
    }

    function renderInsights(stats) {
      $('#an-empty').hidden = true;
      $('#an-body').hidden = false;
      setNumber($('#an-total'), stats.total);
      $('#an-caption').textContent = t(stats.stopped ? 'an.totalPartial' : 'an.total');
      setNumber($('#an-min'), stats.min_length);
      setNumber($('#an-max'), stats.max_length);
      $('#an-avg').textContent = new Intl.NumberFormat(locale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 })
        .format(stats.avg_length);
      const buckets = lengthBuckets(stats.length_counts);
      renderHistogram($('#an-hist'), buckets, stats.total);
      renderBars($('#an-mix'), MIX_KEYS.map((key) => [key, stats[key] || 0]), {
        label: (key) => t(`mix.${key}`),
        value: (n) => `${pct(n, stats.total)}  (${fmt(n)})`,
        max: stats.total,
        ink: (key) => ({ digit_only: 'ink-1', alpha_only: 'ink-0' }[key] || 'ink-n'),
      });
      wheel.draw(stats, buckets);
      wheel.hub(fmtCompact(stats.total), t('an.lines'));
    }

    function progress(job) {
      const p = job.progress || {};
      dock.setProgress(p.fraction === undefined ? null : p.fraction);
      dock.setStatus(t('an.read', { n: fmt(p.done || 0) }), [t('dock.elapsed', { t: fmtDuration(job.elapsed || 0) })]);
      titleProgress(typeof p.fraction === 'number' ? p.fraction : null);
    }

    function done(job) {
      finished = job.result;
      renderInsights(finished.stats);
      toast(t('toast.analyzed'));
    }

    async function run() {
      if (slot.active) {
        stopJob(slot);
        return;
      }
      const issue = problem();
      if (issue) {
        toast(issue, 'error');
        return;
      }
      try {
        const job = await api('/api/analyze', { method: 'POST', body: { file_id: picker.get().id } });
        watchJob(slot, job, { onProgress: progress, onDone: done });
      } catch (err) {
        toast(errorText(err), 'error');
      }
    }

    dock.run.addEventListener('click', run);
    dock.copy.addEventListener('click', async () => {
      if (!picker.get()) return;
      if (await copyText(command().text)) toast(t('dock.copied'));
    });
    refresh();

    return {
      run,
      picker,
      busy: () => slot.active,
      useFile(file, autoRun) {
        picker.set(file);
        if (autoRun && !slot.active) run();
      },
      renderTexts() {
        picker.renderTexts();
        if (slot.active) dock.setRunning(true, slot.stopping);
        else dock.setRunning(false);
        refresh();
        if (finished) renderInsights(finished.stats);
      },
    };
  }

  /* ------------------------------------------------------- page-level bits */

  const VIEW_NAMES = ['generate', 'clean', 'analyze'];

  function positionThumb(animate = true) {
    const tab = $(`.switcher [data-view="${activeView}"]`);
    const thumb = $('.switcher-thumb');
    if (!animate) thumb.style.transition = 'none';
    thumb.style.width = `${tab.offsetWidth}px`;
    thumb.style.transform = `translateX(${tab.offsetLeft}px)`;
    if (!animate) {
      void thumb.offsetWidth;
      thumb.style.transition = '';
    }
  }

  function selectView(name, { focus = false } = {}) {
    const next = VIEW_NAMES.includes(name) ? name : 'generate';
    const changedView = next !== activeView;
    activeView = next;
    $$('.switcher [role="tab"]').forEach((tab) => {
      const on = tab.dataset.view === next;
      tab.setAttribute('aria-selected', String(on));
      tab.tabIndex = on ? 0 : -1;
      if (on && focus) tab.focus();
    });
    VIEW_NAMES.forEach((view) => { $(`#view-${view}`).hidden = view !== next; });
    positionThumb(changedView);
    if (location.hash !== `#${next}`) history.replaceState(null, '', `#${next}`);
  }

  function setLanguage(next) {
    lang = next;
    store.set('lang', lang);
    document.documentElement.lang = lang;
    $$('.lang button').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.lang === lang)));
    applyI18n();
    Object.values(views).forEach((view) => view.renderTexts());
    positionThumb(false);
  }

  function bindTabs() {
    const tabs = $$('.switcher [role="tab"]');
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => selectView(tab.dataset.view));
      tab.addEventListener('keydown', (e) => {
        const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
        if (!step) return;
        e.preventDefault();
        selectView(tabs[(index + step + tabs.length) % tabs.length].dataset.view, { focus: true });
      });
    });
    window.addEventListener('hashchange', () => selectView(location.hash.slice(1)));
    window.addEventListener('resize', () => positionThumb(false));
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => positionThumb(false));
  }

  function bindDialogs() {
    const about = $('#about');
    $('#about-open').addEventListener('click', () => about.showModal());
    $('#about-close').addEventListener('click', () => about.close());
    about.addEventListener('click', (e) => { if (e.target === about) about.close(); });
  }

  function askConsent() {
    if (store.get('consent', false) === true) return;
    const dialog = $('#consent');
    const check = $('#consent-check');
    const proceed = $('#consent-continue');
    dialog.addEventListener('cancel', (e) => e.preventDefault());
    check.addEventListener('change', () => { proceed.disabled = !check.checked; });
    proceed.addEventListener('click', () => {
      store.set('consent', true);
      dialog.close();
    });
    dialog.showModal();
  }

  function bindPageWide() {
    // Dropping a file anywhere on Clean / Analyze picks it; elsewhere the browser must not navigate to it
    window.addEventListener('dragover', (e) => e.preventDefault());
    window.addEventListener('drop', (e) => {
      e.preventDefault();
      const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      const view = views[activeView];
      if (file && view && view.picker && !view.busy()) view.picker.upload(file);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !$('dialog[open]')) {
        e.preventDefault();
        const view = views[activeView];
        if (view) view.run();
      }
    });
    window.addEventListener('beforeunload', (e) => {
      if (Object.values(views).some((view) => view.busy())) {
        e.preventDefault();
        e.returnValue = '';
      }
    });
    $$('.lang button').forEach((button) => button.addEventListener('click', () => setLanguage(button.dataset.lang)));
  }

  async function init() {
    document.documentElement.lang = lang;
    $$('.lang button').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.lang === lang)));
    applyI18n();
    bindTabs();
    bindDialogs();
    bindPageWide();
    selectView(location.hash.slice(1));
    askConsent();
    try {
      meta = await api('/api/meta');
    } catch (err) {
      toast(errorText(err), 'error');
      return;
    }
    limits = meta.limits;
    $('#about-output').textContent = meta.output_dir;
    views.generate = initGenerate();
    views.clean = initClean();
    views.analyze = initAnalyze();
  }

  init();
})();
