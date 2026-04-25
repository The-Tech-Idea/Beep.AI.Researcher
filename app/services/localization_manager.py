"""Localization manager for Flask templates."""
import csv
import json
import re
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional, TextIO, Tuple

LOCALE_LABELS = {
    'en': 'English',
    'ar': 'العربية',
    'fr': 'Français',
    'es': 'Español',
}
_LOCALE_PATTERN = re.compile(r'^[a-z0-9_-]+$')


class LocalizationManager:
    def __init__(self, locales_dir: Optional[Path] = None):
        self.locales_dir = Path(locales_dir) if locales_dir else Path(__file__).resolve().parents[2] / 'locales'
        self._translations: Dict[str, Dict[str, str]] = {}
        self._lock = RLock()
        self.reload()

    def reload(self) -> None:
        with self._lock:
            self._translations = {}
            if not self.locales_dir.exists():
                return
            for path in sorted(self.locales_dir.glob('*.json')):
                try:
                    data = json.loads(path.read_text(encoding='utf-8-sig'))
                except Exception:
                    data = {}
                lang = path.stem
                if isinstance(data, dict):
                    self._translations[lang] = data

    def normalize_locale(self, locale: str) -> str:
        return (locale or '').strip().lower()

    def is_valid_locale(self, locale: str) -> bool:
        return bool(_LOCALE_PATTERN.match(locale))

    def get_supported_locales(self) -> List[str]:
        with self._lock:
            return sorted(self._translations.keys())

    def get_all_translations(self) -> Dict[str, Dict[str, str]]:
        with self._lock:
            return {lang: dict(values) for lang, values in self._translations.items()}

    def translate(self, key: str, lang: Optional[str] = None, fallback: str = 'en') -> str:
        with self._lock:
            preferred = lang or fallback
            translation = self._translations.get(preferred, {})
            value = translation.get(key)
            if value:
                return value
            if preferred != fallback:
                return self._translations.get(fallback, {}).get(key, key)
            return key

    def get_locale_label(self, locale: str) -> str:
        return LOCALE_LABELS.get(locale, locale)

    def update_translation(self, lang: str, updates: Dict[str, str]) -> None:
        with self._lock:
            lang = self.normalize_locale(lang)
            if not self.is_valid_locale(lang):
                raise ValueError('Invalid locale code')
            data = self._translations.setdefault(lang, {})
            data.update(updates)
            path = self.locales_dir / f"{lang}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def import_from_csv(self, stream: TextIO) -> Tuple[int, int]:
        reader = csv.DictReader(stream)
        updates: Dict[str, Dict[str, str]] = {}
        applied = skipped = 0
        for row in reader:
            key = (row.get('key') or '').strip()
            lang = self.normalize_locale(row.get('lang') or '')
            value = (row.get('value') or '').strip()
            if not key or not lang or not value or not self.is_valid_locale(lang):
                skipped += 1
                continue
            updates.setdefault(lang, {})[key] = value
            applied += 1
        for lang, data in updates.items():
            self.update_translation(lang, data)
        return applied, skipped


localization_manager = LocalizationManager()
