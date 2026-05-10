"""Template context processors — registered in create_app().

Injects the i18n translation function `t()`, locale info, feature flags,
and package availability into every template context.
"""

from __future__ import annotations

from flask import Flask, request

from app.config_manager import config_manager, is_feature_enabled
from app.services.localization_manager import localization_manager
from app.services.package_availability import get_feature_status


def register_context_processors(app: Flask) -> None:
    """Register the locale context processor."""

    @app.context_processor
    def inject_locale():
        """Make i18n translation function and locale info available in templates."""
        supported_locales = localization_manager.get_supported_locales() or ["en"]
        cookie_locale = request.cookies.get("preferred_locale")
        locale = cookie_locale if cookie_locale in supported_locales else None
        if not locale:
            locale = request.accept_languages.best_match(supported_locales) or "en"

        def t(key: str, default: str | None = None) -> str:
            result = localization_manager.translate(key, lang=locale)
            if result == key and default is not None:
                return default
            return result

        # Build feature flags dict for template convenience
        ui_features = {}
        try:
            ui_features = config_manager.get("ui_features", {})
        except Exception:
            pass

        # Package availability — which features are available based on installed packages
        package_status = get_feature_status()

        return {
            "t": t,
            "current_locale": locale,
            "supported_locales": supported_locales,
            "locale_label": LOCALE_LABELS.get(locale, locale),
            "locale_names": LOCALE_LABELS,
            "ui_features": ui_features,
            "packages": package_status,
        }


def is_feature_enabled_templating(feature_name: str, default: bool = False) -> bool:
    """Template-friendly feature flag check (exposed as ui_features dict above)."""
    return is_feature_enabled(feature_name, default)


# Display names for locale selector dropdown
LOCALE_LABELS = {
    "en": "English",
    "ar": "\u0627\u0644\u0639\u0631\u0628\u064a\u0629",
    "fr": "Fran\u00e7ais",
    "es": "Espa\u00f1ol",
}
