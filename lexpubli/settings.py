"""Settings do LexPubli — tudo vem de variáveis de ambiente (ver .env.example).

Os defaults servem ao desenvolvimento local (SQLite, DEBUG ligado). Em
qualquer outro ambiente, defina ao menos LEXPUBLI_SECRET_KEY, DATABASE_URL
e LEXPUBLI_DEBUG=0.
"""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nome: str, padrao: bool = False) -> bool:
    return os.environ.get(nome, str(int(padrao))).strip().lower() in ("1", "true", "yes", "on")


def env_list(nome: str, padrao: str = "") -> list[str]:
    return [v.strip() for v in os.environ.get(nome, padrao).split(",") if v.strip()]


DEBUG = env_bool("LEXPUBLI_DEBUG", True)

SECRET_KEY = os.environ.get("LEXPUBLI_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("LEXPUBLI_SECRET_KEY é obrigatória com LEXPUBLI_DEBUG=0")
    SECRET_KEY = "dev-inseguro-nao-use-em-producao"

ALLOWED_HOSTS = env_list("LEXPUBLI_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("LEXPUBLI_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "concursos",
    "wagtail.contrib.sitemaps",
    "wagtail.contrib.redirects",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "concursos.middleware.CabecalhosSegurancaMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "lexpubli.urls"
WSGI_APPLICATION = "lexpubli.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "concursos.contexto.ecossistema",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("LEXPUBLI_STATIC_ROOT", BASE_DIR / "staticfiles"))
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("LEXPUBLI_MEDIA_ROOT", BASE_DIR / "media"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# --- Wagtail -----------------------------------------------------------------
WAGTAIL_SITE_NAME = "LexPubli"
WAGTAILADMIN_BASE_URL = os.environ.get("LEXPUBLI_BASE_URL", "http://localhost:8000")
WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.database"}}
WAGTAILDOCS_EXTENSIONS = ["pdf"]

# Admin fora da URL padrão (/admin/ é o primeiro alvo de varredura automática).
LEXPUBLI_ADMIN_PATH = os.environ.get("LEXPUBLI_ADMIN_PATH", "painel/").strip("/") + "/"

# --- Integração --------------------------------------------------------------
# Broker: o RabbitMQ PRÓPRIO do LexPubli (ADR-0005 §2a), nunca o do LexLearn.
# Vazio = o worker não publica.
LEXPUBLI_RABBITMQ_URL = os.environ.get("LEXPUBLI_RABBITMQ_URL", "")
LEXPUBLI_EXCHANGE = os.environ.get("LEXPUBLI_EXCHANGE", "lexpubli.events")
# Token compartilhado do webhook do changedetection.io. Vazio = webhook desligado.
LEXPUBLI_WEBHOOK_TOKEN = os.environ.get("LEXPUBLI_WEBHOOK_TOKEN", "")
# changedetection.io (ADR-0007 §1): o cadastro Fonte é a fonte da verdade e
# `sincronizar_changedetection` o aplica pela API. A chave fica em Settings > API
# da UI dele. O webhook é chamado DE DENTRO da rede do compose (host `web`).
LEXPUBLI_CHANGEDETECTION_URL = os.environ.get("LEXPUBLI_CHANGEDETECTION_URL",
                                              "http://changedetection:5000")
LEXPUBLI_CHANGEDETECTION_API_KEY = os.environ.get("LEXPUBLI_CHANGEDETECTION_API_KEY", "")
LEXPUBLI_WEBHOOK_INTERNO = os.environ.get("LEXPUBLI_WEBHOOK_INTERNO",
                                          "json://web:8000/webhooks/changedetection/")

# LexLearn, o produto principal do ecossistema: o portal sempre o anuncia.
# Só um LINK (marketing); o LexPubli não fala com o LexLearn (ADR-0005).
LEXPUBLI_LEXLEARN_URL = os.environ.get("LEXPUBLI_LEXLEARN_URL", "")

# --- Segurança ---------------------------------------------------------------
# LEXPUBLI_HTTPS=1 quando o site é servido por HTTPS (proxy reverso na frente).
LEXPUBLI_HTTPS = env_bool("LEXPUBLI_HTTPS", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
if LEXPUBLI_HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("LEXPUBLI_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = env_bool("LEXPUBLI_HSTS_PRELOAD", False)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LEXPUBLI_LOG_LEVEL", "INFO")},
    # Tarefas imediatas do Wagtail (índice de busca/referências) logam cada execução.
    "loggers": {
        "django_tasks": {"level": "WARNING"},
        "django.tasks": {"level": "WARNING"},
        "pika": {"level": "WARNING"},  # INFO do pika loga cada passo da conexão
    },
}
