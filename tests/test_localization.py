import io
import json
from pathlib import Path

import pytest

from app.services.localization_manager import LocalizationManager


def _seed(tmp_path):
    for lang in ('en', 'es', 'fr', 'ar'):
        (tmp_path / f"{lang}.json").write_text(json.dumps({lang: lang}, ensure_ascii=False), encoding='utf-8')


def test_translate_fallback(tmp_path):
    _seed(tmp_path)
    manager = LocalizationManager(locales_dir=tmp_path)
    manager.update_translation('en', {'welcome': 'Welcome'})
    assert manager.translate('welcome', lang='es') == 'Welcome'
    assert manager.translate('unknown', lang='es') == 'unknown'


def test_import_from_csv(tmp_path):
    _seed(tmp_path)
    manager = LocalizationManager(locales_dir=tmp_path)
    csv_data = io.StringIO('key,lang,value\nhello,es,Hola\nnew,xx,Value\n')
    applied, skipped = manager.import_from_csv(csv_data)
    assert applied == 2
    assert skipped == 0
    assert manager.translate('hello', lang='es') == 'Hola'
    assert manager.translate('new', lang='xx') == 'Value'
