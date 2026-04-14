"""Tests for backend/config.py — configuration classes and get_config()."""

import os
import pytest


class TestConfig:
    def test_development_config_has_debug(self):
        from backend.config import DevelopmentConfig
        assert DevelopmentConfig.DEBUG is True

    def test_production_config_no_debug(self):
        from backend.config import ProductionConfig
        assert ProductionConfig.DEBUG is False

    def test_production_config_session_cookie_secure(self):
        from backend.config import ProductionConfig
        assert ProductionConfig.SESSION_COOKIE_SECURE is True

    def test_base_config_httponly_cookie(self):
        from backend.config import Config
        assert Config.SESSION_COOKIE_HTTPONLY is True

    def test_base_config_samesite_lax(self):
        from backend.config import Config
        assert Config.SESSION_COOKIE_SAMESITE == 'Lax'


class TestGetConfig:
    def test_default_returns_development(self, monkeypatch):
        monkeypatch.delenv('FLASK_ENV', raising=False)
        from backend.config import get_config
        config = get_config()
        assert config.DEBUG is True

    def test_production_env(self, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        from backend.config import get_config
        config = get_config()
        assert config.DEBUG is False

    def test_development_env(self, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'development')
        from backend.config import get_config
        config = get_config()
        assert config.DEBUG is True

    def test_unknown_env_returns_development(self, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'staging')
        from backend.config import get_config
        config = get_config()
        # Non-production falls through to DevelopmentConfig
        assert config.DEBUG is True
