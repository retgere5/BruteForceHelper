from colorama import init, Fore, Back, Style

class UIManager:
    def __init__(self):
        init()  # Initialize colorama
        self.colors = {
            'header': Fore.CYAN,
            'info': Fore.WHITE,
            'success': Fore.GREEN,
            'warning': Fore.YELLOW,
            'error': Fore.RED
        }
    
    def print_header(self, message: str) -> None:
        """Print a header message."""
        print(f"\n{self.colors['header']}{Style.BRIGHT}=== {message} ==={Style.RESET_ALL}")
    
    def print_info(self, message: str) -> None:
        """Print an info message."""
        print(f"{self.colors['info']}{message}{Style.RESET_ALL}")
    
    def print_success(self, message: str) -> None:
        """Print a success message."""
        print(f"{self.colors['success']}✓ {message}{Style.RESET_ALL}")
    
    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        print(f"{self.colors['warning']}! {message}{Style.RESET_ALL}")
    
    def print_error(self, message: str) -> None:
        """Print an error message."""
        print(f"{self.colors['error']}✗ {message}{Style.RESET_ALL}")
    
    def print_filter_group(self, group_name: str, description: str) -> None:
        """Print a filter group with its description."""
        print(f"\n{self.colors['header']}{Style.BRIGHT}{group_name}{Style.RESET_ALL}")
        print(f"{self.colors['info']}{description}{Style.RESET_ALL}")
    
    def get_user_input(self, prompt: str, valid_inputs: list = None, default: str = None) -> str:
        """Get user input with validation."""
        while True:
            if default:
                user_input = input(f"{prompt} [{default}]: ").strip() or default
            else:
                user_input = input(f"{prompt}: ").strip()
            
            if not valid_inputs or user_input.lower() in valid_inputs:
                return user_input.lower()
            
            self.print_error(f"Geçersiz giriş. Lütfen tekrar deneyin.") 