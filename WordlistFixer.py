import argparse
import multiprocessing as mp
from itertools import islice
import os
import math
import time
from tqdm import tqdm
import json
import sys
import msvcrt  # Windows için klavye kontrolü

# Çalışma dizinini ayarla
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

from modules.filters import FilterStats, PasswordFilter
from modules.ui_manager import UIManager
from modules.settings_manager import Settings, FilterRecommender

def check_keyboard_input():
    """Klavye girişini kontrol eder."""
    if msvcrt.kbhit():
        key = msvcrt.getch().decode('utf-8').lower()
        return key
    return None

class WordlistOptimizer:
    def __init__(self):
        self.ui = UIManager()
        self.settings = Settings()
        self.password_filter = PasswordFilter()
        self.recommender = FilterRecommender()
    
    def optimize(self, input_file, output_file, options):
        """Wordlist'i optimize eder."""
        try:
            # Checkpoint dosyası adı
            checkpoint_file = f"{output_file}.checkpoint"
            checkpoint = CheckpointManager(checkpoint_file)
            
            # Toplam satır sayısı
            total_lines = sum(1 for _ in open(input_file, 'r', encoding='utf-8'))
            
            # İşlemci sayısı ve chunk boyutu
            cpu_count = max(1, mp.cpu_count() - 1)
            chunk_size = max(1000, math.ceil(total_lines / (cpu_count * 10)))
            
            total_passwords = checkpoint.processed_count
            removed_passwords = checkpoint.removed_count
            
            self.ui.print_header("Wordlist Optimizasyonu")
            if checkpoint.last_position > 0:
                self.ui.print_info(f"Checkpoint bulundu: {checkpoint.last_position:,} şifre işlenmiş")
            self.ui.print_info(f"{cpu_count} işlemci kullanılıyor")
            self.ui.print_info(f"Chunk boyutu: {chunk_size:,} şifre")
            self.ui.print_info("İşlemi durdurmak için 'q', checkpoint alıp durdurmak için 'c' tuşuna basın")
            
            # Process pool
            pool = mp.Pool(processes=cpu_count)
            
            # İstatistik yöneticisi
            filter_stats = FilterStats()
            
            try:
                with open(input_file, 'r', encoding='utf-8') as infile, \
                     open(output_file, 'a' if checkpoint.last_position > 0 else 'w', encoding='utf-8') as outfile:
                    
                    # Checkpoint konumuna git
                    if checkpoint.last_position > 0:
                        for _ in range(checkpoint.last_position):
                            next(infile)
                    
                    progress_bar = tqdm(total=total_lines,
                                      initial=checkpoint.last_position,
                                      desc=f"Toplam: {checkpoint.last_position:,}",
                                      unit=' şifre',
                                      dynamic_ncols=True,
                                      position=0,
                                      leave=True,
                                      ncols=150,
                                      bar_format='{desc}: {percentage:.2f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}] {percentage:.2f}%',
                                      miniters=1,
                                      mininterval=0.1,
                                      smoothing=0.3)
                    
                    while True:
                        try:
                            # Klavye kontrolü
                            key = check_keyboard_input()
                            if key == 'q':
                                progress_bar.clear()
                                self.ui.print_warning("\nProgram durduruluyor...")
                                if 'pool' in locals():
                                    pool.terminate()
                                return
                            elif key == 'c':
                                progress_bar.clear()
                                self.ui.print_warning("\nCheckpoint alınıyor...")
                                checkpoint.save_checkpoint(
                                    progress_bar.n,
                                    total_passwords,
                                    removed_passwords
                                )
                                self.ui.print_success(f"Checkpoint kaydedildi: {checkpoint_file}")
                                if 'pool' in locals():
                                    pool.terminate()
                                return
                            
                            chunk = list(islice(infile, chunk_size))
                            if not chunk:
                                break
                            
                            current_position = progress_bar.n
                            chunk_size_actual = len(chunk)
                            
                            # İşleme için veri hazırla
                            chunk_data = (chunk, options, options.min_length, options.max_length, filter_stats)
                            
                            # Chunk'ı işle
                            valid_passwords = pool.apply(self.process_chunk, (chunk_data,))
                            
                            # Sonuçları yaz ve progress bar'ı güncelle
                            update_interval = max(1, len(valid_passwords) // 100)  # Her %1'lik ilerleme için güncelle
                            for i, password in enumerate(valid_passwords):
                                outfile.write(password + '\n')
                                if i % update_interval == 0:
                                    progress_bar.update(update_interval)
                            
                            # Kalan kısmı güncelle
                            remaining_update = len(valid_passwords) % update_interval
                            if remaining_update > 0:
                                progress_bar.update(remaining_update)
                            
                            # İstatistikleri güncelle ve göster
                            total_passwords += chunk_size_actual
                            removed_passwords += chunk_size_actual - len(valid_passwords)
                            
                            if filter_stats.should_display():
                                filter_stats.display(total_passwords, progress_bar)
                            
                            progress_bar.update(chunk_size_actual)
                            
                        except KeyboardInterrupt:
                            progress_bar.clear()
                            self.ui.print_warning("\nİşlem duraklatıldı. Son istatistikler:")
                            filter_stats.display(total_passwords)
                            self.ui.print_warning("\nCheckpoint kaydediliyor...")
                            checkpoint.save_checkpoint(
                                progress_bar.n,
                                total_passwords,
                                removed_passwords
                            )
                            self.ui.print_success(f"Checkpoint kaydedildi: {checkpoint_file}")
                            return
                    
                    progress_bar.close()
                    
                    # Final istatistiklerini göster
                    self.ui.print_header("Final Filtreleme İstatistikleri")
                    filter_stats.display(total_passwords)
            
            finally:
                if 'pool' in locals():
                    pool.close()
                    pool.join()
            
            # İşlem tamamlandığında checkpoint'i sil
            if os.path.exists(checkpoint_file):
                os.remove(checkpoint_file)
            
            self.ui.print_success("\nOptimizasyon tamamlandı!")
            self.ui.print_info(f"Toplam şifre sayısı: {total_passwords:,}")
            self.ui.print_info(f"Kaldırılan şifre sayısı: {removed_passwords:,}")
            self.ui.print_info(f"Kalan şifre sayısı: {total_passwords - removed_passwords:,}")
            self.ui.print_info(f"Azalma oranı: %{(removed_passwords/total_passwords*100):.2f}")
            
            if options.keep_stats:
                self.save_stats(output_file, total_passwords, removed_passwords, options, filter_stats)
        
        except FileNotFoundError:
            self.ui.print_error(f"Hata: '{input_file}' dosyası bulunamadı.")
        except Exception as e:
            self.ui.print_error(f"Beklenmeyen bir hata oluştu: {e}")
            if 'pool' in locals():
                pool.terminate()
    
    def process_chunk(self, chunk_data):
        """Bir parça veriyi işler."""
        chunk, options, min_length, max_length, stats = chunk_data
        
        # İlk filtreleme (uzunluk)
        valid_passwords = []
        for password in chunk:
            password = password.strip()
            if (not min_length or len(password) >= min_length) and \
               (not max_length or len(password) <= max_length):
                if self.password_filter.is_valid_password(password, options, stats):
                    valid_passwords.append(password)
        
        return valid_passwords
    
    def save_stats(self, output_file, total_passwords, removed_passwords, options, filter_stats):
        """İstatistikleri dosyaya kaydeder."""
        stats_file = f"{os.path.splitext(output_file)[0]}_stats.txt"
        with open(stats_file, 'w', encoding='utf-8') as f:
            f.write("=== Wordlist Optimizasyon İstatistikleri ===\n\n")
            f.write(f"Kullanılan işlemci sayısı: {mp.cpu_count() - 1}\n")
            f.write(f"\nToplam şifre sayısı: {total_passwords:,}\n")
            f.write(f"Kaldırılan şifre sayısı: {removed_passwords:,}\n")
            f.write(f"Kalan şifre sayısı: {total_passwords - removed_passwords:,}\n")
            f.write(f"Azalma oranı: %{(removed_passwords/total_passwords*100):.2f}\n\n")
            
            f.write("Aktif filtreler:\n")
            for option, value in vars(options).items():
                if value and not option.startswith('input') and not option.startswith('output'):
                    f.write(f"  - {option}\n")
            
            f.write("\nFiltre Bazlı İstatistikler:\n")
            for filter_name, count in sorted(filter_stats.stats.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    percentage = (count / total_passwords) * 100
                    f.write(f"  - {filter_name}: {count:,} şifre (%{percentage:.2f})\n")
        
        self.ui.print_success(f"İstatistikler kaydedildi: {stats_file}")

class CheckpointManager:
    def __init__(self, checkpoint_file):
        self.checkpoint_file = checkpoint_file
        self.last_position = 0
        self.processed_count = 0
        self.removed_count = 0
        self.load_checkpoint()
    
    def save_checkpoint(self, position, processed, removed):
        """İşlem durumunu kaydeder."""
        checkpoint_data = {
            'position': position,
            'processed_count': processed,
            'removed_count': removed,
            'timestamp': time.time()
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)
        
        self.last_position = position
        self.processed_count = processed
        self.removed_count = removed
    
    def load_checkpoint(self):
        """Son kayıtlı durumu yükler."""
        try:
            with open(self.checkpoint_file, 'r') as f:
                data = json.load(f)
                self.last_position = data['position']
                self.processed_count = data['processed_count']
                self.removed_count = data['removed_count']
                return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False

def main():
    try:
        optimizer = WordlistOptimizer()
        
        # Kullanıcıdan seçenekleri al
        options = get_filter_options(optimizer)
        
        # Optimizasyonu başlat
        optimizer.optimize(options.input, options.output, options)
        
    except KeyboardInterrupt:
        optimizer.ui.print_warning("\n\nProgram kullanıcı tarafından durduruldu.")
    except Exception as e:
        optimizer.ui.print_error(f"\nHata: {e}")

def get_filter_options(optimizer):
    """Kullanıcıdan filtre seçeneklerini alır."""
    last_settings = optimizer.settings.load_settings()
    options = argparse.Namespace()
    
    # Tüm olası filtreleri başlangıçta False olarak ayarla
    default_filters = {
        'min_length_filter': False,
        'repetitive_chars': False,
        'pattern_repetition': False,
        'sequential_chars': False,
        'keyboard_patterns': False,
        'number_only': False,
        'letter_only': False,
        'special_patterns': False,
        'single_char_type': False,
        'year_patterns': False,
        'date_patterns': False,
        'phone_patterns': False,
        'common_words': False,
        'leet_speak': False
    }
    
    for filter_name, value in default_filters.items():
        setattr(options, filter_name, value)
    
    optimizer.ui.print_header("Wordlist Optimize Edici")
    optimizer.ui.print_info("Bu program, wordlist dosyanızı optimize ederek daha etkili hale getirir.")
    
    if last_settings:
        use_last = optimizer.ui.get_user_input(
            "Son kullanılan ayarları kullanmak ister misiniz?",
            ['e', 'h'],
            'h',
            "Son kullanılan ayarlar bulundu."
        )
        if use_last == 'e':
            for key, value in last_settings.items():
                setattr(options, key, value)
            return options
    
    # Dosya bilgileri
    optimizer.ui.print_header("Dosya Bilgileri")
    options.input = optimizer.ui.get_user_input(
        "Wordlist dosyası adı",
        description="Optimize edilecek wordlist dosyasının adını girin."
    )
    options.output = optimizer.ui.get_user_input(
        "Çıktı dosyası adı",
        default="optimized.txt",
        description="Optimize edilmiş wordlist'in kaydedileceği dosya adını girin."
    )
    
    # Uzunluk filtreleri
    optimizer.ui.print_header("Uzunluk Filtreleri")
    min_length = optimizer.ui.get_user_input(
        "Minimum şifre uzunluğu",
        default="",
        description="Minimum şifre uzunluğunu belirtin (boş bırakabilirsiniz)."
    )
    max_length = optimizer.ui.get_user_input(
        "Maksimum şifre uzunluğu",
        default="",
        description="Maksimum şifre uzunluğunu belirtin (boş bırakabilirsiniz)."
    )
    options.min_length = int(min_length) if min_length.isdigit() else None
    options.max_length = int(max_length) if max_length.isdigit() else None
    
    # Filtre grupları
    optimizer.ui.print_header("Filtre Grupları")
    optimizer.ui.print_info("Filtre gruplarını toplu olarak veya tek tek seçebilirsiniz.")
    
    groups = optimizer.settings.get_filter_groups()
    selected_groups = []
    
    for group_name, filters in groups.items():
        optimizer.ui.print_filter_group(
            group_name,
            optimizer.settings.get_group_description(group_name)
        )
        
        group_choice = optimizer.ui.get_user_input(
            f"Bu grup için seçiminiz (t: tümü, s: seç, h: hiçbiri)",
            ['t', 's', 'h'],
            'h'
        )
        
        if group_choice == 't':
            selected_groups.extend(filters)
        elif group_choice == 's':
            optimizer.ui.print_info("\nGrup içindeki filtreleri tek tek seçin:")
            for filter_name in filters:
                if optimizer.ui.get_user_input(
                    f"  {filter_name} ({optimizer.settings.get_filter_description(filter_name)})",
                    ['e', 'h'],
                    'h'
                ) == 'e':
                    selected_groups.append(filter_name)
    
    # Seçilen grupları options'a ekle
    for filter_name in set(selected_groups):
        setattr(options, filter_name, True)
    
    # İstatistik kaydı
    optimizer.ui.print_header("İstatistik Ayarları")
    options.keep_stats = optimizer.ui.get_user_input(
        "İstatistikleri kaydet?",
        ['e', 'h'],
        'e',
        "İşlem sonunda detaylı istatistikler kaydedilsin mi?"
    ) == 'e'
    
    # Filtre önerileri
    try:
        wordlist_size = os.path.getsize(options.input)
        
        optimizer.ui.print_header("Filtre Önerileri")
        optimizer.ui.print_info("Wordlist boyutunuza göre öneriler:")
        
        recommendations = optimizer.recommender.get_recommendations(wordlist_size)
        
        # Önerileri numaralandırarak göster
        for i, (preset_name, description) in enumerate(recommendations, 1):
            optimizer.ui.print_info(f"\n{i}) {preset_name}")
            optimizer.ui.print_info(f"  {description}")
            optimizer.ui.print_info("  İçerdiği filtreler:")
            for filter_name in optimizer.recommender.common_combinations[preset_name]:
                optimizer.ui.print_info(
                    f"    - {filter_name}: {optimizer.settings.get_filter_description(filter_name)}"
                )
        
        use_recommendation = optimizer.ui.get_user_input(
            "\nÖnerilen filtrelerden birini kullanmak ister misiniz?",
            ['e', 'h'],
            'h'
        )
        
        if use_recommendation == 'e':
            valid_choices = [str(i) for i in range(1, len(recommendations) + 1)]
            choice = optimizer.ui.get_user_input(
                "Hangi öneriyi kullanmak istersiniz? (numara girin)",
                valid_choices,
                '1'
            )
            
            # Seçilen filtreleri options'a ekle ve varsayılan False değerlerini ayarla
            selected_preset = recommendations[int(choice) - 1][0]
            for filter_name in optimizer.recommender.common_combinations[selected_preset]:
                setattr(options, filter_name, True)
            
            # Tüm olası filtreleri False olarak ayarla
            all_filters = set()
            for filters in optimizer.recommender.common_combinations.values():
                all_filters.update(filters)
            for filter_name in all_filters:
                if not hasattr(options, filter_name):
                    setattr(options, filter_name, False)
    except Exception as e:
        optimizer.ui.print_warning(f"Filtre önerileri yüklenirken hata oluştu: {e}")
        pass
    
    # Filtre skoru göster
    score = optimizer.recommender.get_filter_score(selected_groups)
    optimizer.ui.print_info(f"\nSeçilen filtrelerin etkinlik skoru: %{score:.1f}")
    if score < 50:
        optimizer.ui.print_warning("Düşük filtreleme skoru. Daha fazla filtre eklemeyi düşünebilirsiniz.")
    elif score > 80:
        optimizer.ui.print_success("Yüksek filtreleme skoru. İyi bir seçim!")
    
    # Onay
    while True:
        confirm = optimizer.ui.get_user_input(
            "\nSeçimlerinizi onaylıyor musunuz?",
            ['e', 'h'],
            'e'
        )
        if confirm == 'e':
            # Ayarları kaydet
            optimizer.settings.save_settings(options)
            return options
        else:
            optimizer.ui.print_warning("\nFiltreleri tekrar seçmek için programı yeniden başlatın.")
            sys.exit(0)

if __name__ == '__main__':
    main() 