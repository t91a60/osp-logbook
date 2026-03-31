import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'osp-logbook-secret-zmien-to')
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    USE_HTTPS = os.environ.get('OSP_USE_HTTPS', '0') == '1'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = USE_HTTPS
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0

    if USE_HTTPS:
        PREFERRED_URL_SCHEME = 'https'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

def get_config():
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig
    return DevelopmentConfig