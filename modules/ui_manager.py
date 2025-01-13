from colorama import init, Fore, Back, Style

# Renkli çıktı için colorama'yı başlat
init()

class ColorTheme:
    def __init__(self, theme='default'):
        self.themes = {
            'default': {
                'header': f"{Back.BLUE}{Fore.WHITE}",
                'info': Fore.CYAN,
                'success': Fore.GREEN,
                'warning': Fore.YELLOW,
                'error': Fore.RED,
                'progress': Fore.BLUE,
                'highlight': Fore.MAGENTA,
                'input': Fore.WHITE,
                'reset': Style.RESET_ALL
            },
            'dark': {
                'header': f"{Back.WHITE}{Fore.BLACK}",
                'info': Fore.BLUE,
                'success': Fore.GREEN,
                'warning': Fore.YELLOW,
                'error': Fore.RED,
                'progress': Fore.CYAN,
                'highlight': Fore.MAGENTA,
                'input': Fore.WHITE,
                'reset': Style.RESET_ALL
            },
            'light': {
                'header': f"{Back.BLACK}{Fore.WHITE}",
                'info': Fore.BLUE,
                'success': Fore.GREEN,
                'warning': Fore.YELLOW,
                'error': Fore.RED,
                'progress': Fore.MAGENTA,
                'highlight': Fore.CYAN,
                'input': Fore.BLACK,
                'reset': Style.RESET_ALL
            }
        }
        self.current_theme = self.themes.get(theme, self.themes['default'])
    
    def get_color(self, color_type):
        return self.current_theme.get(color_type, '')

class UIManager:
    def __init__(self, theme='default'):
        self.theme = ColorTheme(theme)
    
    def print_header(self, text):
        """Renkli başlık yazdırır."""
        print(f"\n{self.theme.get_color('header')} {text} {self.theme.get_color('reset')}")
    
    def print_info(self, text):
        """Bilgi mesajı yazdırır."""
        print(f"{self.theme.get_color('info')}{text}{self.theme.get_color('reset')}")
    
    def print_success(self, text):
        """Başarı mesajı yazdırır."""
        print(f"{self.theme.get_color('success')}{text}{self.theme.get_color('reset')}")
    
    def print_warning(self, text):
        """Uyarı mesajı yazdırır."""
        print(f"{self.theme.get_color('warning')}{text}{self.theme.get_color('reset')}")
    
    def print_error(self, text):
        """Hata mesajı yazdırır."""
        print(f"{self.theme.get_color('error')}{text}{self.theme.get_color('reset')}")
    
    def get_user_input(self, prompt, valid_inputs=None, default=None, description=None):
        """Gelişmiş kullanıcı girdi fonksiyonu."""
        if description:
            self.print_info(f"\n{description}")
        
        while True:
            if default is not None:
                user_input = input(
                    f"{self.theme.get_color('info')}{prompt} "
                    f"{self.theme.get_color('warning')}[{default}]"
                    f"{self.theme.get_color('reset')}: "
                ).strip()
                if not user_input:
                    return default
            else:
                user_input = input(
                    f"{self.theme.get_color('info')}{prompt}"
                    f"{self.theme.get_color('reset')}: "
                ).strip()
            
            if valid_inputs is None:
                return user_input
            
            if user_input.lower() in valid_inputs:
                return user_input.lower()
            
            self.print_error(f"Lütfen geçerli bir değer girin: {', '.join(valid_inputs)}")
    
    def print_filter_group(self, group_name, description):
        """Filtre grubunu yazdırır."""
        self.print_info(f"\n{group_name}:")
        self.print_info(f"  {description}")
    
    def print_filter_description(self, filter_name, description):
        """Filtre açıklamasını yazdırır."""
        self.print_info(f"  - {filter_name}: {description}")
    
    def print_stats(self, stats_data):
        """İstatistikleri yazdırır."""
        self.print_header("İstatistikler")
        for key, value in stats_data.items():
            self.print_info(f"{key}: {value}")
    
    def print_progress(self, current, total, prefix='', suffix=''):
        """İlerleme durumunu yazdırır."""
        bar_length = 50
        filled_length = int(round(bar_length * current / float(total)))
        percents = round(100.0 * current / float(total), 1)
        bar = '=' * filled_length + '-' * (bar_length - filled_length)
        
        print(f'\r{prefix} [{bar}] {percents}% {suffix}', end='') 