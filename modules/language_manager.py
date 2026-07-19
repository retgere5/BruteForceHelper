from typing import Dict, List

class LanguageManager:
    def __init__(self):
        self.current_language = "tr"  # Default language
        self.translations = {
            "tr": {
                "welcome": "BruteForce Helper'a Hoş Geldiniz!",
                "select_language": "Lütfen bir dil seçin / Please select a language:",
                "language_options": "1. Türkçe\n2. English",
                "invalid_selection": "Geçersiz seçim! Lütfen tekrar deneyin.",
                "file_info": "Dosya Bilgileri",
                "input_file": "Wordlist dosyası adı",
                "output_file": "Çıktı dosyası adı",
                "length_filters": "Uzunluk Filtreleri",
                "min_length": "Minimum şifre uzunluğu",
                "max_length": "Maksimum şifre uzunluğu",
                "use_last_settings": "Son kullanılan ayarları kullanmak ister misiniz?",
                "group_selection": "Bu grup için seçiminiz",
                "statistics_settings": "İstatistik Ayarları",
                "save_stats": "İstatistikleri kaydet?",
                "wordlist_optimization": "Wordlist Optimizasyonu",
                "checkpoint_found": "Checkpoint bulundu:",
                "passwords_processed": "şifre işlenmiş",
                "processors_used": "işlemci kullanılıyor",
                "chunk_size": "Chunk boyutu:",
                "passwords": "şifre",
                "password": "şifre",
                "press_q_to_stop": "İşlemi durdurmak için 'q',",
                "press_c_to_checkpoint": "checkpoint alıp durdurmak için 'c' tuşuna basın",
                "total": "Toplam",
                "checkpoint_saved": "Checkpoint kaydedildi:",
                "total_passwords": "Toplam şifre sayısı:",
                "removed_passwords": "Kaldırılan şifre sayısı:",
                "remaining_passwords": "Kalan şifre sayısı:",
                "reduction_rate": "Azalma oranı:",
                "error": "Hata:",
                "file_not_found": "dosyası bulunamadı.",
                "unexpected_error": "Beklenmeyen bir hata oluştu:",
                "stats_saved": "İstatistikler kaydedildi:",
                "stopping": "Program durduruluyor...",
                "taking_checkpoint": "Checkpoint alınıyor...",
                "paused_last_stats": "İşlem duraklatıldı. Son istatistikler:",
                "saving_checkpoint": "Checkpoint kaydediliyor...",
                "final_filter_stats": "Final Filtreleme İstatistikleri",
                "optimization_complete": "Optimizasyon tamamlandı!",
                "most_effective_filters": "En etkili filtreler",
                "recommended_filters": "Önerilen filtreler (wordlist boyutuna göre)",
                "filter_groups": {
                    "basic_security": "Temel Güvenlik",
                    "character_based": "Karakter Bazlı",
                    "pattern_based": "Kalıp Bazlı",
                    "format_based": "Format Bazlı",
                    "word_based": "Kelime Bazlı"
                },
                "filter_descriptions": {
                    "min_length_filter": "Çok kısa şifreleri sil",
                    "repetitive_chars": "Tekrar eden karakterli şifreleri sil",
                    "pattern_repetition": "Basit kalıplı şifreleri sil",
                    "number_only": "Sadece sayılardan oluşan şifreleri sil",
                    "letter_only": "Sadece harflerden oluşan şifreleri sil",
                    "sequential_chars": "Sıralı karakterli şifreleri sil",
                    "keyboard_patterns": "Klavye düzenine göre oluşturulmuş şifreleri sil",
                    "special_patterns": "Özel karakter kalıplı şifreleri sil",
                    "year_patterns": "Yıl formatındaki şifreleri sil",
                    "single_char_type": "Tek tip karakterli şifreleri sil",
                    "date_patterns": "Tarih formatındaki şifreleri sil",
                    "phone_patterns": "Telefon numarası formatındaki şifreleri sil",
                    "common_words": "Yaygın kelime içeren şifreleri sil",
                    "leet_speak": "Leet speak (1337) şifreleri sil"
                },
                "filter_recommendations": {
                    "fast_filtering": "Hızlı filtreleme (küçük wordlist'ler)",
                    "smart_filtering": "Akıllı filtreleme (orta boy)",
                    "format_control": "Format kontrolü (yaygın kalıplar)",
                    "maximum_security": "Maksimum güvenlik (büyük wordlist'ler)"
                }
            },
            "en": {
                "welcome": "Welcome to BruteForce Helper!",
                "select_language": "Please select a language / Lütfen bir dil seçin:",
                "language_options": "1. Turkish\n2. English",
                "invalid_selection": "Invalid selection! Please try again.",
                "file_info": "File Information",
                "input_file": "Wordlist file name",
                "output_file": "Output file name",
                "length_filters": "Length Filters",
                "min_length": "Minimum password length",
                "max_length": "Maximum password length",
                "use_last_settings": "Do you want to use last used settings?",
                "group_selection": "Your choice for this group",
                "statistics_settings": "Statistics Settings",
                "save_stats": "Save statistics?",
                "wordlist_optimization": "Wordlist Optimization",
                "checkpoint_found": "Checkpoint found:",
                "passwords_processed": "passwords processed",
                "processors_used": "processors being used",
                "chunk_size": "Chunk size:",
                "passwords": "passwords",
                "password": "password",
                "press_q_to_stop": "Press 'q' to stop,",
                "press_c_to_checkpoint": "press 'c' to save checkpoint and stop",
                "total": "Total",
                "checkpoint_saved": "Checkpoint saved:",
                "total_passwords": "Total passwords:",
                "removed_passwords": "Removed passwords:",
                "remaining_passwords": "Remaining passwords:",
                "reduction_rate": "Reduction rate:",
                "error": "Error:",
                "file_not_found": "file not found.",
                "unexpected_error": "An unexpected error occurred:",
                "stats_saved": "Statistics saved:",
                "stopping": "Stopping...",
                "taking_checkpoint": "Saving checkpoint...",
                "paused_last_stats": "Paused. Last statistics:",
                "saving_checkpoint": "Saving checkpoint...",
                "final_filter_stats": "Final Filtering Statistics",
                "optimization_complete": "Optimization complete!",
                "most_effective_filters": "Most effective filters",
                "recommended_filters": "Recommended filters (by wordlist size)",
                "filter_groups": {
                    "basic_security": "Basic Security",
                    "character_based": "Character Based",
                    "pattern_based": "Pattern Based",
                    "format_based": "Format Based",
                    "word_based": "Word Based"
                },
                "filter_descriptions": {
                    "min_length_filter": "Remove very short passwords",
                    "repetitive_chars": "Remove passwords with repetitive characters",
                    "pattern_repetition": "Remove passwords with simple patterns",
                    "number_only": "Remove passwords containing only numbers",
                    "letter_only": "Remove passwords containing only letters",
                    "sequential_chars": "Remove passwords with sequential characters",
                    "keyboard_patterns": "Remove passwords based on keyboard layout",
                    "special_patterns": "Remove passwords with special character patterns",
                    "year_patterns": "Remove passwords in year format",
                    "single_char_type": "Remove passwords with single character type",
                    "date_patterns": "Remove passwords in date format",
                    "phone_patterns": "Remove passwords in phone-number format",
                    "common_words": "Remove passwords containing common words",
                    "leet_speak": "Remove leet-speak (1337) passwords"
                },
                "filter_recommendations": {
                    "fast_filtering": "Fast filtering (small wordlists)",
                    "smart_filtering": "Smart filtering (medium)",
                    "format_control": "Format control (common patterns)",
                    "maximum_security": "Maximum security (large wordlists)"
                }
            }
        }
        
        # Language-specific common words
        self.common_words = {
            "tr": [
                "sifre", "parola", "admin", "yonetici", "kullanici", "test",
                "deneme", "merhaba", "turkiye", "istanbul", "ankara", "izmir",
                "ocak", "subat", "mart", "nisan", "mayis", "haziran",
                "temmuz", "agustos", "eylul", "ekim", "kasim", "aralik"
            ],
            "en": [
                "password", "admin", "user", "test", "hello", "welcome",
                "january", "february", "march", "april", "may", "june",
                "july", "august", "september", "october", "november", "december",
                "monday", "tuesday", "wednesday", "thursday", "friday",
                "saturday", "sunday"
            ]
        }
    
    def set_language(self, lang_code: str) -> None:
        """Set the current language."""
        if lang_code in self.translations:
            self.current_language = lang_code
    
    def get_text(self, key: str, section: str = None) -> str:
        """Get translated text for a given key."""
        if section:
            return self.translations[self.current_language][section][key]
        return self.translations[self.current_language][key]
    
    def get_common_words(self) -> List[str]:
        """Get common words for the current language."""
        return self.common_words[self.current_language]

    def prompt_language_selection(self) -> str:
        """Prompt user to select a language."""
        print("\n" + self.get_text("select_language"))
        print(self.get_text("language_options"))
        
        while True:
            try:
                choice = input(">>> ").strip()
                if choice == "1":
                    return "tr"
                elif choice == "2":
                    return "en"
                else:
                    print(self.get_text("invalid_selection"))
            except Exception:
                print(self.get_text("invalid_selection")) 