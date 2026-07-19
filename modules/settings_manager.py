import json
import os
from typing import Dict, List, Tuple
from .ui_manager import UIManager

class Settings:
    def __init__(self):
        self.settings_file = "wordlist_optimizer_settings.json"
        self.ui = UIManager()
        self.recommender = FilterRecommender()

    def _show_recommendations(self, input_file, language_manager) -> None:
        """Wordlist dosya boyutuna göre önerilen filtre setlerini gösterir."""
        try:
            if not input_file or not os.path.exists(input_file):
                return
            recommendations = self.recommender.get_recommendations(os.path.getsize(input_file))
            if not recommendations:
                return
            self.ui.print_header(language_manager.get_text('recommended_filters'))
            for key, _description in recommendations:
                self.ui.print_info(f"  - {language_manager.get_text(key, 'filter_recommendations')}")
        except Exception:
            pass  # Öneriler bilgilendirme amaçlıdır; hata ana akışı bozmamalı

    def get_filter_options(self, language_manager) -> Dict:
        """Get filter options from user with translations."""
        last_settings = self.load_settings()
        options = {}
        
        # Set default values for all filters
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
        options.update(default_filters)
        
        if last_settings:
            self.ui.print_info(language_manager.get_text('use_last_settings'))
            if self.ui.get_user_input("(e/h)", ['e', 'h'], 'h') == 'e':
                options.update(last_settings)
                return options
        
        # Get file information
        self.ui.print_header(language_manager.get_text('file_info'))
        options['input'] = self.ui.get_user_input(language_manager.get_text('input_file'))
        options['output'] = self.ui.get_user_input(
            f"{language_manager.get_text('output_file')} [optimized.txt]",
            default="optimized.txt"
        )

        # Wordlist boyutuna göre filtre önerileri göster
        self._show_recommendations(options['input'], language_manager)

        # Get length filters
        self.ui.print_header(language_manager.get_text('length_filters'))
        min_length = self.ui.get_user_input(language_manager.get_text('min_length'))
        max_length = self.ui.get_user_input(language_manager.get_text('max_length'))
        options['min_length'] = int(min_length) if min_length.isdigit() else None
        options['max_length'] = int(max_length) if max_length.isdigit() else None
        
        # Get filter groups
        self.ui.print_header(language_manager.get_text('filter_groups'))
        groups = self.get_filter_groups()
        
        for group_name, filters in groups.items():
            group_text = language_manager.get_text(group_name, 'filter_groups')
            self.ui.print_filter_group(group_text, "")
            
            choice = self.ui.get_user_input(
                f"{language_manager.get_text('group_selection')} (t/s/h)",
                ['t', 's', 'h'],
                'h'
            )
            
            if choice == 't':
                for filter_name in filters:
                    options[filter_name] = True
            elif choice == 's':
                for filter_name in filters:
                    desc = language_manager.get_text(filter_name, 'filter_descriptions')
                    if self.ui.get_user_input(f"  {desc} (e/h)", ['e', 'h'], 'h') == 'e':
                        options[filter_name] = True
        
        # Get statistics option
        self.ui.print_header(language_manager.get_text('statistics_settings'))
        options['keep_stats'] = self.ui.get_user_input(
            f"{language_manager.get_text('save_stats')} (e/h)",
            ['e', 'h'],
            'e'
        ) == 'e'
        
        # Save settings
        self.save_settings(options)
        return options
    
    def get_filter_groups(self) -> Dict[str, List[str]]:
        """Get filter groups."""
        return {
            "basic_security": [
                "min_length_filter",
                "repetitive_chars",
                "pattern_repetition"
            ],
            "character_based": [
                "number_only",
                "letter_only",
                "single_char_type"
            ],
            "pattern_based": [
                "sequential_chars",
                "keyboard_patterns",
                "special_patterns"
            ],
            "format_based": [
                "year_patterns",
                "date_patterns",
                "phone_patterns"
            ],
            "word_based": [
                "common_words",
                "leet_speak"
            ]
        }
    
    def save_settings(self, settings: Dict) -> None:
        """Save settings to file."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.ui.print_error(f"Error saving settings: {e}")
    
    def load_settings(self) -> Dict:
        """Load settings from file."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.ui.print_error(f"Error loading settings: {e}")
        return None

class FilterRecommender:
    def __init__(self):
        self.common_combinations = {
            "maximum_security": [
                "min_length_filter", "repetitive_chars", "pattern_repetition",
                "number_only", "letter_only", "sequential_chars", "keyboard_patterns",
                "special_patterns", "year_patterns", "single_char_type"
            ],
            "fast_filtering": [
                "min_length_filter", "repetitive_chars", "sequential_chars",
                "keyboard_patterns"
            ],
            "smart_filtering": [
                "min_length_filter", "pattern_repetition", "special_patterns",
                "year_patterns", "single_char_type"
            ],
            "format_control": [
                "year_patterns", "date_patterns", "phone_patterns",
                "common_words", "leet_speak"
            ]
        }
        
        self.filter_weights = {
            "min_length_filter": 5,
            "repetitive_chars": 8,
            "pattern_repetition": 7,
            "number_only": 6,
            "letter_only": 6,
            "sequential_chars": 8,
            "keyboard_patterns": 7,
            "special_patterns": 5,
            "year_patterns": 4,
            "single_char_type": 6,
            "date_patterns": 4,
            "phone_patterns": 4,
            "common_words": 7,
            "leet_speak": 5
        }
    
    def get_recommendations(self, wordlist_size: int) -> List[Tuple[str, str]]:
        """Get filter recommendations based on wordlist size."""
        recommendations = []
        
        # Add recommendations based on wordlist size
        if wordlist_size < 1_000_000:  # < 1MB
            recommendations.append(("fast_filtering", "Hızlı filtreleme, küçük wordlist'ler için ideal"))
        elif wordlist_size < 100_000_000:  # < 100MB
            recommendations.append(("smart_filtering", "Akıllı filtreleme, orta boy wordlist'ler için"))
            recommendations.append(("format_control", "Format kontrolü, yaygın kalıpları temizler"))
        else:  # >= 100MB
            recommendations.append(("maximum_security", "Maksimum güvenlik, büyük wordlist'ler için"))
            recommendations.append(("smart_filtering", "Akıllı filtreleme, alternatif seçenek"))
        
        return recommendations
    
    def get_filter_score(self, selected_filters: List[str]) -> float:
        """Calculate effectiveness score for selected filters."""
        if not selected_filters:
            return 0.0
        
        total_weight = sum(self.filter_weights.values())
        selected_weight = sum(self.filter_weights.get(f, 0) for f in selected_filters)
        
        return (selected_weight / total_weight) * 100 