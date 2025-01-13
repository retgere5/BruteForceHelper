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
from modules.language_manager import LanguageManager

def check_keyboard_input():
    """Klavye girişini kontrol eder."""
    if msvcrt.kbhit():
        key = msvcrt.getch().decode('utf-8').lower()
        return key
    return None

class WordlistOptimizer:
    def __init__(self, options, language_manager):
        self.ui = UIManager()
        self.settings = Settings()
        self.password_filter = PasswordFilter()
        self.recommender = FilterRecommender()
        self.language_manager = language_manager
    
    def optimize(self):
        """Wordlist'i optimize eder."""
        try:
            # Checkpoint dosyası adı
            checkpoint_file = f"{self.options.output}.checkpoint"
            checkpoint = CheckpointManager(checkpoint_file)
            
            # Toplam satır sayısı
            total_lines = sum(1 for _ in open(self.options.input, 'r', encoding='utf-8'))
            
            # İşlemci sayısı ve chunk boyutu
            cpu_count = max(1, mp.cpu_count() - 1)
            chunk_size = max(1000, math.ceil(total_lines / (cpu_count * 10)))
            
            total_passwords = checkpoint.processed_count
            removed_passwords = checkpoint.removed_count
            
            self.ui.print_header(self.language_manager.get_text("wordlist_optimization"))
            if checkpoint.last_position > 0:
                self.ui.print_info(f"{self.language_manager.get_text('checkpoint_found')} {checkpoint.last_position:,} {self.language_manager.get_text('passwords_processed')}")
            self.ui.print_info(f"{cpu_count} {self.language_manager.get_text('processors_used')}")
            self.ui.print_info(f"{self.language_manager.get_text('chunk_size')} {chunk_size:,} {self.language_manager.get_text('passwords')}")
            self.ui.print_info(f"{self.language_manager.get_text('press_q_to_stop')} {self.language_manager.get_text('press_c_to_checkpoint')}")
            
            # Process pool
            pool = mp.Pool(processes=cpu_count)
            
            # İstatistik yöneticisi
            filter_stats = FilterStats()
            
            try:
                with open(self.options.input, 'r', encoding='utf-8') as infile, \
                     open(self.options.output, 'a' if checkpoint.last_position > 0 else 'w', encoding='utf-8') as outfile:
                    
                    # Checkpoint konumuna git
                    if checkpoint.last_position > 0:
                        for _ in range(checkpoint.last_position):
                            next(infile)
                    
                    progress_bar = tqdm(total=total_lines,
                                      initial=checkpoint.last_position,
                                      desc=f"{self.language_manager.get_text('total')} {checkpoint.last_position:,}",
                                      unit=self.language_manager.get_text('password'),
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
                                self.ui.print_success(f"{self.language_manager.get_text('checkpoint_saved')} {checkpoint_file}")
                                if 'pool' in locals():
                                    pool.terminate()
                                return
                            
                            chunk = list(islice(infile, chunk_size))
                            if not chunk:
                                break
                            
                            current_position = progress_bar.n
                            chunk_size_actual = len(chunk)
                            
                            # İşleme için veri hazırla
                            chunk_data = (chunk, self.options, self.options.min_length, self.options.max_length, filter_stats)
                            
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
            self.ui.print_info(f"{self.language_manager.get_text('total_passwords')} {total_passwords:,}")
            self.ui.print_info(f"{self.language_manager.get_text('removed_passwords')} {removed_passwords:,}")
            self.ui.print_info(f"{self.language_manager.get_text('remaining_passwords')} {total_passwords - removed_passwords:,}")
            self.ui.print_info(f"{self.language_manager.get_text('reduction_rate')} %{(removed_passwords/total_passwords*100):.2f}")
            
            if self.options.keep_stats:
                self.save_stats(self.options.output, total_passwords, removed_passwords, self.options, filter_stats)
        
        except FileNotFoundError:
            self.ui.print_error(f"{self.language_manager.get_text('error')} '{self.options.input}' {self.language_manager.get_text('file_not_found')}")
        except Exception as e:
            self.ui.print_error(f"{self.language_manager.get_text('unexpected_error')} {e}")
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
        
        self.ui.print_success(f"{self.language_manager.get_text('stats_saved')} {stats_file}")

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
    # Initialize managers
    ui_manager = UIManager()
    settings = Settings()
    language_manager = LanguageManager()
    
    # Language selection
    selected_lang = language_manager.prompt_language_selection()
    language_manager.set_language(selected_lang)
    
    # Welcome message
    ui_manager.print_header(language_manager.get_text("welcome"))
    
    # Get filter options with translated text
    options = settings.get_filter_options(language_manager)
    
    # Process the wordlist with selected options
    try:
        wordlist_optimizer = WordlistOptimizer(options, language_manager)
        wordlist_optimizer.optimize()
    except Exception as e:
        ui_manager.print_error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 