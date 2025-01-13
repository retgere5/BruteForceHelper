import json
import os

class Settings:
    def __init__(self):
        self.settings_file = "wordlist_optimizer_settings.json"
        self.filter_groups = {
            'Temel Güvenlik': [
                'min_length_filter',
                'repetitive_chars',
                'pattern_repetition'
            ],
            'Karakter Bazlı': [
                'number_only',
                'letter_only',
                'single_char_type'
            ],
            'Kalıp Bazlı': [
                'sequential_chars',
                'keyboard_patterns',
                'special_patterns'
            ],
            'Format Bazlı': [
                'year_patterns',
                'date_patterns',
                'phone_patterns'
            ],
            'Kelime Bazlı': [
                'common_words',
                'leet_speak'
            ]
        }
        self.filter_descriptions = {
            'min_length_filter': 'Çok kısa şifreleri filtreler (4 karakterden az)',
            'repetitive_chars': 'Aynı karakterin art arda çok tekrar ettiği şifreleri filtreler (örn: aaaa)',
            'pattern_repetition': 'Tekrar eden kalıpları filtreler (örn: abcabc)',
            'number_only': 'Sadece sayılardan oluşan uzun şifreleri filtreler (örn: 123456)',
            'letter_only': 'Sadece harflerden oluşan uzun şifreleri filtreler (örn: abcdef)',
            'sequential_chars': 'Sıralı karakterleri filtreler (örn: 12345, abcde)',
            'keyboard_patterns': 'Klavye düzenindeki sıralı karakterleri filtreler (örn: qwerty)',
            'special_patterns': 'Yaygın özel karakter kalıplarını filtreler (örn: !@#$)',
            'year_patterns': 'Yıl formatındaki şifreleri filtreler (örn: 1990, 2023)',
            'single_char_type': 'Tek tür karakterden oluşan şifreleri filtreler',
            'common_words': 'Yaygın kelime ve isimleri filtreler (örn: password, admin)',
            'date_patterns': 'Tarih formatındaki şifreleri filtreler (örn: 01012023)',
            'phone_patterns': 'Telefon numarası formatındaki şifreleri filtreler',
            'leet_speak': 'Basit karakter değişimli şifreleri filtreler (örn: p@ssw0rd)'
        }
        self.group_descriptions = {
            'Temel Güvenlik': 'Çok kısa (örn: abc), tekrar eden (örn: aaaa) ve basit kalıplı (örn: abcabc) şifreleri siler',
            'Karakter Bazlı': 'Tek tip karakterden oluşan şifreleri siler (örn: 123456, abcdef)',
            'Kalıp Bazlı': 'Sıralı (örn: 12345, abcde) ve klavye düzenine göre (örn: qwerty, asdfgh) oluşturulmuş şifreleri siler',
            'Format Bazlı': 'Tarih (örn: 01012023), yıl (örn: 1990) ve telefon numarası (örn: 5551234567) formatındaki şifreleri siler',
            'Kelime Bazlı': 'Yaygın kelimeler (örn: password, admin) ve basit karakter değişimli (örn: p@ssw0rd) şifreleri siler'
        }
    
    def save_settings(self, options):
        """Son kullanılan ayarları kaydeder."""
        settings = {k: v for k, v in vars(options).items()}
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            return True
        except Exception as e:
            print(f"[!] Ayarlar kaydedilemedi: {e}")
            return False
    
    def load_settings(self):
        """Son kullanılan ayarları yükler."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[!] Ayarlar yüklenemedi: {e}")
        return None
    
    def get_filter_groups(self):
        """Filtre gruplarını döndürür."""
        return self.filter_groups
    
    def get_filter_description(self, filter_name):
        """Filtre açıklamasını döndürür."""
        return self.filter_descriptions.get(filter_name, '')
    
    def get_group_description(self, group_name):
        """Grup açıklamasını döndürür."""
        return self.group_descriptions.get(group_name, '')

class FilterRecommender:
    def __init__(self):
        self.common_combinations = {
            'Maksimum Güvenlik': [
                'min_length_filter',
                'repetitive_chars',
                'pattern_repetition',
                'sequential_chars',
                'keyboard_patterns',
                'common_words',
                'leet_speak'
            ],
            'Hızlı Filtreleme': [
                'min_length_filter',
                'repetitive_chars',
                'number_only',
                'letter_only'
            ],
            'Akıllı Filtreleme': [
                'pattern_repetition',
                'keyboard_patterns',
                'year_patterns',
                'common_words'
            ],
            'Format Kontrolü': [
                'date_patterns',
                'phone_patterns',
                'year_patterns',
                'special_patterns'
            ]
        }
        
        self.filter_weights = {
            'min_length_filter': 5,
            'repetitive_chars': 4,
            'pattern_repetition': 4,
            'number_only': 3,
            'letter_only': 3,
            'sequential_chars': 4,
            'keyboard_patterns': 5,
            'special_patterns': 2,
            'year_patterns': 2,
            'single_char_type': 3,
            'common_words': 5,
            'date_patterns': 2,
            'phone_patterns': 2,
            'leet_speak': 4
        }
    
    def get_recommendations(self, wordlist_size, processing_power='normal'):
        """Wordlist boyutuna göre öneriler sunar."""
        recommendations = []
        
        if wordlist_size < 1000000:  # 1M'den küçük listeler
            recommendations.append(('Maksimum Güvenlik', 'En kapsamlı filtreleme için idealdir.'))
        elif wordlist_size < 10000000:  # 10M'den küçük listeler
            recommendations.append(('Akıllı Filtreleme', 'Hız ve güvenlik dengesi için optimaldır.'))
        else:  # Büyük listeler
            recommendations.append(('Hızlı Filtreleme', 'Büyük listeler için performans odaklıdır.'))
        
        return recommendations
    
    def get_filter_score(self, filters):
        """Seçilen filtrelerin etkinlik skorunu hesaplar."""
        score = 0
        max_score = 0
        
        for filter_name, weight in self.filter_weights.items():
            max_score += weight
            if filter_name in filters:
                score += weight
        
        return (score / max_score) * 100 