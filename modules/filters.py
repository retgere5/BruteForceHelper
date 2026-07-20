import re
import time

class FilterStats:
    def __init__(self, language_manager=None):
        self.language_manager = language_manager
        self.stats = {
            'min_length': 0,
            'max_length': 0,
            'repetitive_chars': 0,
            'pattern_repetition': 0,
            'number_only': 0,
            'letter_only': 0,
            'sequential_chars': 0,
            'keyboard_patterns': 0,
            'special_patterns': 0,
            'year_patterns': 0,
            'single_char_type': 0,
            'common_words': 0,
            'date_patterns': 0,
            'phone_patterns': 0,
            'leet_speak': 0
        }
        self.last_update = time.time()
        self.update_interval = 1.0  # 1 saniye
    
    def _text(self, key, fallback):
        """Çeviri varsa onu, yoksa yedek metni döndürür."""
        if self.language_manager is not None:
            try:
                return self.language_manager.get_text(key)
            except Exception:
                return fallback
        return fallback

    def update(self, filter_name):
        """Filtre istatistiğini günceller."""
        self.stats[filter_name] += 1
    
    def should_display(self):
        """İstatistiklerin gösterilip gösterilmeyeceğini kontrol eder."""
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            self.last_update = current_time
            return True
        return False
    
    def display(self, total_passwords, progress_bar=None):
        """İstatistikleri gösterir."""
        # En etkili filtreleri bul (ilk 3)
        active_filters = [(k, v) for k, v in self.stats.items() if v > 0]
        sorted_filters = sorted(active_filters, key=lambda x: x[1], reverse=True)[:3]
        
        # İstatistik metnini hazırla
        stats_text = f"{self._text('total', 'Toplam')}: {total_passwords:,}"
        if sorted_filters:
            stats_text += f" | {self._text('most_effective_filters', 'En etkili filtreler')}: "
            filter_texts = []
            for filter_name, count in sorted_filters:
                percentage = (count / total_passwords) * 100 if total_passwords else 0
                filter_texts.append(f"{filter_name}(%{percentage:.1f})")
            stats_text += ", ".join(filter_texts)
        
        if progress_bar:
            # Progress bar'ın açıklamasını güncelle
            progress_bar.set_description(stats_text)
        else:
            print("\n" + stats_text)
        
        # İstatistik sayacını sıfırla
        self.display_counter = 0

class PasswordFilter:
    def __init__(self):
        self.keyboard_patterns = [
            'qwerty', 'asdfgh', 'zxcvbn', 'qwertz', 'azerty'
        ]
        self.common_words = [
            'password', 'admin', '123456', 'qwerty', 'letmein',
            'welcome', 'monkey', 'dragon', 'master', 'football'
        ]
        self.leet_replacements = {
            'a': ['4', '@'],
            'e': ['3'],
            'i': ['1', '!'],
            'o': ['0'],
            's': ['5', '$'],
            't': ['7'],
            'l': ['1'],
            'z': ['2']
        }
        # Precompiled patterns (compiled once, reused per password)
        self._re_repetitive = re.compile(r'(.)\1{3,}')
        self._re_year = re.compile(r'19\d{2}|20\d{2}')
        self._re_dates = [re.compile(p) for p in (
            r'\d{2}[.-/]\d{2}[.-/]\d{4}',  # DD.MM.YYYY
            r'\d{4}[.-/]\d{2}[.-/]\d{2}',  # YYYY.MM.DD
            r'\d{8}',                      # DDMMYYYY
        )]
        self._re_phones = [re.compile(p) for p in (
            r'05\d{9}',    # Türk GSM
            r'5\d{9}',     # Başında 0 olmayan GSM
            r'\+905\d{9}',  # Uluslararası format
        )]

    def is_valid_password(self, password, options, stats):
        """Şifrenin geçerli olup olmadığını kontrol eder."""
        # Minimum uzunluk kontrolü
        if options.min_length_filter and len(password) < 4:
            stats.update('min_length')
            return False
        
        # Tekrar eden karakterler
        if options.repetitive_chars and self._re_repetitive.search(password):
            stats.update('repetitive_chars')
            return False
        
        # Tekrar eden kalıplar
        if options.pattern_repetition and self._has_pattern_repetition(password):
            stats.update('pattern_repetition')
            return False
        
        # Sadece sayı kontrolü
        if options.number_only and len(password) >= 6 and password.isdigit():
            stats.update('number_only')
            return False
        
        # Sadece harf kontrolü
        if options.letter_only and len(password) >= 6 and password.isalpha():
            stats.update('letter_only')
            return False
        
        # Sıralı karakterler
        if options.sequential_chars and self._is_sequential(password):
            stats.update('sequential_chars')
            return False
        
        # Klavye düzeni
        if options.keyboard_patterns and self._is_keyboard_pattern(password):
            stats.update('keyboard_patterns')
            return False
        
        # Özel karakter kalıpları
        if options.special_patterns and self._is_special_pattern(password):
            stats.update('special_patterns')
            return False
        
        # Yıl formatı
        if options.year_patterns and self._is_year_pattern(password):
            stats.update('year_patterns')
            return False
        
        # Tek tip karakter
        if options.single_char_type and self._is_single_char_type(password):
            stats.update('single_char_type')
            return False
        
        # Yaygın kelimeler
        if options.common_words and self._is_common_word(password):
            stats.update('common_words')
            return False
        
        # Tarih formatı
        if options.date_patterns and self._is_date_pattern(password):
            stats.update('date_patterns')
            return False
        
        # Telefon numarası formatı
        if options.phone_patterns and self._is_phone_pattern(password):
            stats.update('phone_patterns')
            return False
        
        # Leet speak
        if options.leet_speak and self._is_leet_speak(password):
            stats.update('leet_speak')
            return False
        
        return True
    
    def _has_pattern_repetition(self, password):
        """Tekrar eden kalıpları kontrol eder."""
        for i in range(2, len(password) // 2 + 1):
            for j in range(len(password) - i * 2 + 1):
                pattern = password[j:j + i]
                if pattern == password[j + i:j + i * 2]:
                    return True
        return False
    
    def _is_sequential(self, password):
        """Sıralı karakterleri kontrol eder."""
        sequences = ['0123456789', 'abcdefghijklmnopqrstuvwxyz']
        lower_pass = password.lower()
        
        for seq in sequences:
            for i in range(len(seq) - 3):
                if seq[i:i + 4] in lower_pass:
                    return True
                if seq[i:i + 4][::-1] in lower_pass:  # Ters sıra kontrolü
                    return True
        return False
    
    def _is_keyboard_pattern(self, password):
        """Klavye düzenindeki kalıpları kontrol eder."""
        lower_pass = password.lower()
        for pattern in self.keyboard_patterns:
            if pattern in lower_pass:
                return True
        return False
    
    def _is_special_pattern(self, password):
        """Özel karakter kalıplarını kontrol eder."""
        special_patterns = ['!@#$', '!@#', '123!@#']
        for pattern in special_patterns:
            if pattern in password:
                return True
        return False
    
    def _is_year_pattern(self, password):
        """Yıl formatını kontrol eder."""
        return bool(self._re_year.search(password))
    
    def _is_single_char_type(self, password):
        """Şifre tek bir karakter kategorisinden mi oluşuyor (hepsi rakam / hepsi
        harf / hepsi diğer)?

        Eski sürüm isupper()/islower() kullanıyordu; bunlar 'PASS123' gibi karma
        harf+rakam şifreler için de True döndürdüğünden karma şifreler yanlışlıkla
        eleniyordu. Artık yalnızca gerçekten tek kategoriden oluşanlar elenir.
        """
        if not password:
            return False
        has_digit = any(c.isdigit() for c in password)
        has_alpha = any(c.isalpha() for c in password)
        has_other = any(not c.isalnum() for c in password)
        return (has_digit + has_alpha + has_other) == 1
    
    def _is_common_word(self, password):
        """Yaygın kelimeleri kontrol eder."""
        lower_pass = password.lower()
        for word in self.common_words:
            if word in lower_pass:
                return True
        return False
    
    def _is_date_pattern(self, password):
        """Tarih formatını kontrol eder."""
        return any(pattern.search(password) for pattern in self._re_dates)

    def _is_phone_pattern(self, password):
        """Telefon numarası formatını kontrol eder."""
        return any(pattern.search(password) for pattern in self._re_phones)
    
    def _is_leet_speak(self, password):
        """Leet speak kontrolü yapar."""
        lower_pass = password.lower()
        for char, replacements in self.leet_replacements.items():
            for replacement in replacements:
                if replacement in password and char in lower_pass:
                    return True
        return False 