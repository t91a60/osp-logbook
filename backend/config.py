import os
from datetime import timedelta


class Config:
    SECRET_KEY: str | None = os.environ.get('SECRET_KEY')
    DATABASE_URL: str | None = os.environ.get('DATABASE_URL')

    USE_HTTPS: bool = os.environ.get('OSP_USE_HTTPS', '0') == '1'
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    SESSION_COOKIE_SECURE: bool = USE_HTTPS
    TEMPLATES_AUTO_RELOAD: bool = True
    SEND_FILE_MAX_AGE_DEFAULT: int = 0

    if USE_HTTPS:
        PREFERRED_URL_SCHEME: str = 'https'


class DevelopmentConfig(Config):
    DEBUG: bool = True


class ProductionConfig(Config):
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)


def get_config() -> type[Config]:
    match os.environ.get('FLASK_ENV', 'development'):
        case 'production':
            return ProductionConfig
        case _:
            return DevelopmentConfig
