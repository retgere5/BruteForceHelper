import multiprocessing as mp
from itertools import islice
import os
import math
import time
import gzip
import traceback
from tqdm import tqdm
import json
import sys
from types import SimpleNamespace

try:
    import msvcrt  # Windows için klavye kontrolü; Linux/macOS'ta yoktur
except ImportError:  # pragma: no cover - platforma bağlı
    msvcrt = None

# Çalışma dizinini ayarla
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
# Çoklu-işlem (spawn) alt süreçleri modules/ paketini bulabilsin diye dizini yola ekle
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from modules.filters import FilterStats, PasswordFilter
from modules.ui_manager import UIManager
from modules.settings_manager import Settings, FilterRecommender
from modules.language_manager import LanguageManager

def check_keyboard_input():
    """Basılan tuşu (küçük harf) döndürür, yoksa None. Windows dışında etkisizdir."""
    if msvcrt is None:
        return None
    try:
        if msvcrt.kbhit():
            return msvcrt.getch().decode('utf-8', errors='ignore').lower()
    except Exception:
        return None
    return None

def open_text(path, mode):
    """Metin dosyasını açar; uzantı .gz ise şeffaf biçimde gzip kullanır.

    mode: 'r' / 'w' / 'a' (metin kipi). gzip için otomatik olarak 't' eklenir.
    """
    path = str(path)
    if path.endswith('.gz'):
        return gzip.open(path, mode + 't', encoding='utf-8')
    return open(path, mode, encoding='utf-8')

def _filter_chunk_worker(args):
    """Tek bir parçayı (chunk) filtreler. Çoklu-işlem havuzunda çalışacak şekilde
    modül seviyesindedir (picklable) ve yalnızca picklable veri alır/döndürür.

    Döner: (geçerli_şifreler, filtre_sayaçları, parça_uzunluğu)
    """
    lines, options, min_length, max_length = args
    password_filter = PasswordFilter()
    stats = FilterStats()
    valid_passwords = []
    for password in lines:
        password = password.strip()
        if (not min_length or len(password) >= min_length) and \
           (not max_length or len(password) <= max_length):
            if password_filter.is_valid_password(password, options, stats):
                valid_passwords.append(password)
    return valid_passwords, stats.stats, len(lines)

class WordlistOptimizer:
    def __init__(self, options, language_manager):
        self.ui = UIManager()
        self.settings = Settings()
        self.password_filter = PasswordFilter()
        self.recommender = FilterRecommender()
        self.language_manager = language_manager
        # Settings.get_filter_options() bir dict döndürür; sınıfın geri kalanı
        # seçeneklere öznitelik (self.options.output vb.) olarak eriştiği için
        # dict'i bir namespace'e normalize ediyoruz.
        self.options = options if isinstance(options, SimpleNamespace) else SimpleNamespace(**options)
    
    def optimize(self):
        """Wordlist'i optimize eder."""
        try:
            # Checkpoint dosyası adı
            checkpoint_file = f"{self.options.output}.checkpoint"
            checkpoint = CheckpointManager(checkpoint_file)
            
            # Toplam satır sayısı
            with open_text(self.options.input, 'r') as _f:
                total_lines = sum(1 for _ in _f)

            # Chunk boyutu (bellek dostu parça okuma) ve işçi sayısı
            cpu_count = max(1, mp.cpu_count() - 1)
            chunk_size = max(1000, math.ceil(total_lines / (cpu_count * 10))) if total_lines else 1000
            num_chunks = math.ceil(total_lines / chunk_size) if total_lines else 0
            # Parça sayısından fazla işçi açma; tek parça/az veride ana süreçte çalış
            worker_count = max(1, min(cpu_count, num_chunks))

            total_passwords = checkpoint.processed_count
            removed_passwords = checkpoint.removed_count

            self.ui.print_header(self.language_manager.get_text("wordlist_optimization"))
            if checkpoint.last_position > 0:
                self.ui.print_info(f"{self.language_manager.get_text('checkpoint_found')} {checkpoint.last_position:,} {self.language_manager.get_text('passwords_processed')}")
            self.ui.print_info(f"{self.language_manager.get_text('chunk_size')} {chunk_size:,} {self.language_manager.get_text('passwords')}")
            if msvcrt is not None:
                self.ui.print_info(f"{self.language_manager.get_text('press_q_to_stop')} {self.language_manager.get_text('press_c_to_checkpoint')}")

            # İstatistik yöneticisi (görüntüleme dile göre çevrilir)
            filter_stats = FilterStats(self.language_manager)

            # worker_count > 1 ise gerçek çoklu-işlem (imap sırayı korur, çıktı
            # girdi sırasıyla aynı kalır); aksi halde ana süreçte (map) çalış.
            pool = mp.Pool(processes=worker_count) if worker_count > 1 else None
            try:
                with open_text(self.options.input, 'r') as infile, \
                     open_text(self.options.output, 'a' if checkpoint.last_position > 0 else 'w') as outfile:

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

                    def _chunk_args():
                        while True:
                            lines = list(islice(infile, chunk_size))
                            if not lines:
                                break
                            yield (lines, self.options, self.options.min_length, self.options.max_length)

                    if pool is not None:
                        results = pool.imap(_filter_chunk_worker, _chunk_args())
                    else:
                        results = map(_filter_chunk_worker, _chunk_args())

                    try:
                        for valid_passwords, stat_counts, chunk_len in results:
                            # Klavye kontrolü (q: durdur, c: checkpoint alıp durdur)
                            key = check_keyboard_input()
                            if key == 'q':
                                progress_bar.clear()
                                self.ui.print_warning(f"\n{self.language_manager.get_text('stopping')}")
                                return
                            elif key == 'c':
                                progress_bar.clear()
                                self.ui.print_warning(f"\n{self.language_manager.get_text('taking_checkpoint')}")
                                checkpoint.save_checkpoint(
                                    progress_bar.n,
                                    total_passwords,
                                    removed_passwords
                                )
                                self.ui.print_success(f"{self.language_manager.get_text('checkpoint_saved')} {checkpoint_file}")
                                return

                            # Alt süreçten dönen filtre sayaçlarını ana süreçte birleştir
                            for name, count in stat_counts.items():
                                if count:
                                    filter_stats.stats[name] = filter_stats.stats.get(name, 0) + count

                            # Geçerli şifreleri yaz
                            for password in valid_passwords:
                                outfile.write(password + '\n')

                            # İstatistikleri güncelle
                            total_passwords += chunk_len
                            removed_passwords += chunk_len - len(valid_passwords)

                            if filter_stats.should_display():
                                filter_stats.display(total_passwords, progress_bar)

                            progress_bar.update(chunk_len)

                    except KeyboardInterrupt:
                        progress_bar.clear()
                        self.ui.print_warning(f"\n{self.language_manager.get_text('paused_last_stats')}")
                        filter_stats.display(total_passwords)
                        self.ui.print_warning(f"\n{self.language_manager.get_text('saving_checkpoint')}")
                        checkpoint.save_checkpoint(
                            progress_bar.n,
                            total_passwords,
                            removed_passwords
                        )
                        self.ui.print_success(f"{self.language_manager.get_text('checkpoint_saved')} {checkpoint_file}")
                        return

                    progress_bar.close()

                    # Final istatistiklerini göster
                    self.ui.print_header(self.language_manager.get_text('final_filter_stats'))
                    filter_stats.display(total_passwords)

            finally:
                if pool is not None:
                    pool.terminate()
                    pool.join()

            # İşlem tamamlandığında checkpoint'i sil
            if os.path.exists(checkpoint_file):
                os.remove(checkpoint_file)

            reduction_rate = (removed_passwords / total_passwords * 100) if total_passwords else 0
            self.ui.print_success(f"\n{self.language_manager.get_text('optimization_complete')}")
            self.ui.print_info(f"{self.language_manager.get_text('total_passwords')} {total_passwords:,}")
            self.ui.print_info(f"{self.language_manager.get_text('removed_passwords')} {removed_passwords:,}")
            self.ui.print_info(f"{self.language_manager.get_text('remaining_passwords')} {total_passwords - removed_passwords:,}")
            self.ui.print_info(f"{self.language_manager.get_text('reduction_rate')} %{reduction_rate:.2f}")
            
            if self.options.keep_stats:
                self.save_stats(self.options.output, total_passwords, removed_passwords, self.options, filter_stats)
        
        except FileNotFoundError:
            self.ui.print_error(f"{self.language_manager.get_text('error')} '{self.options.input}' {self.language_manager.get_text('file_not_found')}")
        except Exception as e:
            self.ui.print_error(f"{self.language_manager.get_text('unexpected_error')} {e}")
            traceback.print_exc()

    def save_stats(self, output_file, total_passwords, removed_passwords, options, filter_stats):
        """İstatistikleri dosyaya kaydeder."""
        stats_file = f"{os.path.splitext(output_file)[0]}_stats.txt"
        with open(stats_file, 'w', encoding='utf-8') as f:
            reduction_rate = (removed_passwords / total_passwords * 100) if total_passwords else 0
            f.write("=== Wordlist Optimizasyon İstatistikleri ===\n\n")
            f.write(f"Sistem işlemci sayısı: {mp.cpu_count()}\n")
            f.write(f"\nToplam şifre sayısı: {total_passwords:,}\n")
            f.write(f"Kaldırılan şifre sayısı: {removed_passwords:,}\n")
            f.write(f"Kalan şifre sayısı: {total_passwords - removed_passwords:,}\n")
            f.write(f"Azalma oranı: %{reduction_rate:.2f}\n\n")

            f.write("Aktif filtreler:\n")
            for option, value in vars(options).items():
                if value and not option.startswith('input') and not option.startswith('output'):
                    f.write(f"  - {option}\n")

            f.write("\nFiltre Bazlı İstatistikler:\n")
            for filter_name, count in sorted(filter_stats.stats.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    percentage = (count / total_passwords) * 100 if total_passwords else 0
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

def _make_output_encoding_safe():
    """Konsol/pipe UI glifini (✓/✗) kodlayamadığında çökmek yerine değiştir."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

def main():
    # stdout/stderr'i UnicodeEncodeError'a karşı dayanıklı yap (colorama'dan önce)
    _make_output_encoding_safe()

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