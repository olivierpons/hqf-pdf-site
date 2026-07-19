"""Django settings for the hqf-pdf-site project.

Every deployment-specific value is read from a TOML file, resolved in this
order:

1. the path in the ``TOML_CONFIG_FILE`` environment variable,
2. otherwise ``~/.config/hqf_pdf_site.toml``.

The file is read at import time and each section is validated here, so a
misconfigured deployment fails at boot with a message naming the missing key,
never later in the middle of a request. ``install/config_template.toml`` is the
reference template and is printed on any configuration error.
"""

import os
import sys
import tomllib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

##########################
# Read configuration file
##########################
toml_file = os.environ.get("TOML_CONFIG_FILE")
if toml_file is None:
    site_config_path = Path.home() / ".config" / "hqf_pdf_site.toml"
else:
    site_config_path = Path(toml_file)


def bad_config_file(msg):
    """Print a configuration error along with the template, then exit.

    Args:
        msg: What is wrong, naming the section and key at fault.
    """
    print(
        f"\n*** {msg} ***\n\nConfiguration file Path = {site_config_path}\n",
        file=sys.stderr,
    )
    template = BASE_DIR / "install" / "config_template.toml"
    print(f"A template exists in {template} and looks like this : \n", file=sys.stderr)
    print(template.open().read(), file=sys.stderr)
    sys.exit(1)


if not site_config_path.exists():
    bad_config_file("Configuration file does not exist")

with site_config_path.open("rb") as fh:
    SITE_CONFIG = tomllib.load(fh)

SITE_CONFIG_PATH = site_config_path

##############
# Confidential
##############
try:
    SECRET_KEY = SITE_CONFIG["confidential"]["secret_key"]
except KeyError:
    bad_config_file("[confidential] section or secret_key missing in TOML config file")

###########
# Debugging
###########
DEBUGGING_CONFIG = SITE_CONFIG.get("debugging")
if not DEBUGGING_CONFIG:
    bad_config_file("Missing [debugging] section")

DEBUG = bool(DEBUGGING_CONFIG.get("debug"))

##########
# Security
##########
SECURITY_CONFIG = SITE_CONFIG.get("security")
if not SECURITY_CONFIG:
    bad_config_file("Missing [security] section")

INTERNAL_IPS = SECURITY_CONFIG.get("internal_ips") or ("127.0.0.1",)
ALLOWED_HOSTS = SECURITY_CONFIG.get("allowed_hosts") or ("127.0.0.1",)
if "csrf_trusted_origins" in SECURITY_CONFIG:
    CSRF_TRUSTED_ORIGINS = SECURITY_CONFIG["csrf_trusted_origins"]

# Set this only behind a TLS-terminating proxy: on a directly exposed server a
# client can forge the header and make Django believe the request was HTTPS.
if "secure_proxy_ssl_header" in SECURITY_CONFIG:
    SECURE_PROXY_SSL_HEADER = (SECURITY_CONFIG["secure_proxy_ssl_header"], "https")

###################
# Application paths
###################
APP_PATHS = SITE_CONFIG.get("app_paths", {})
TMP_DIR = Path(APP_PATHS.get("tmp_dir", "/tmp/hqf_pdf_site"))
TMP_DIR.mkdir(parents=True, exist_ok=True)

###########
# Databases
###########
DATABASES_CONFIG = SITE_CONFIG.get("databases")
if not DATABASES_CONFIG or not DATABASES_CONFIG.get("default"):
    bad_config_file("[databases] section or its 'default' entry is missing")

default_db = DATABASES_CONFIG["default"]
if not default_db.get("name"):
    bad_config_file("'name' missing in [databases.default] section")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": default_db["name"],
        "USER": default_db.get("user"),
        "PASSWORD": default_db.get("password"),
        "HOST": default_db.get("host") or "localhost",
        "PORT": default_db.get("port") or 5432,
        "CONN_MAX_AGE": 60,
        "ATOMIC_REQUESTS": True,
    }
}

###############
# Render server
###############
# The site owns the render server's front: a bridge command turns the live API
# keys into the two files that grant access. ``clients_file`` is the TOML the
# server reads for what each client may do; ``nginx_map_file`` is the map nginx
# reads to turn an API key into a client name; ``font_store_dir`` is the parent
# a client's own font directory hangs under, named for the client.
PDF_SERVER_CONFIG = SITE_CONFIG.get("pdf_server")
if not PDF_SERVER_CONFIG:
    bad_config_file("Missing [pdf_server] section")

PDF_SERVER_CLIENTS_FILE = PDF_SERVER_CONFIG.get("clients_file")
if not PDF_SERVER_CLIENTS_FILE:
    bad_config_file(
        "'clients_file' missing in [pdf_server] section "
        "(ex: '/etc/hqf-pdf-server/clients.toml')"
    )
PDF_SERVER_CLIENTS_FILE = Path(PDF_SERVER_CLIENTS_FILE)

PDF_SERVER_NGINX_MAP_FILE = PDF_SERVER_CONFIG.get("nginx_map_file")
if not PDF_SERVER_NGINX_MAP_FILE:
    bad_config_file(
        "'nginx_map_file' missing in [pdf_server] section "
        "(ex: '/etc/nginx/hqf-pdf-clients.map')"
    )
PDF_SERVER_NGINX_MAP_FILE = Path(PDF_SERVER_NGINX_MAP_FILE)

PDF_SERVER_FONT_STORE_DIR = PDF_SERVER_CONFIG.get("font_store_dir")
if not PDF_SERVER_FONT_STORE_DIR:
    bad_config_file(
        "'font_store_dir' missing in [pdf_server] section "
        "(ex: '/etc/hqf-pdf-server/fonts')"
    )
PDF_SERVER_FONT_STORE_DIR = Path(PDF_SERVER_FONT_STORE_DIR)

# The shared secret the render server presents when it reports usage back to the
# site. The same value is set on the server; the ingest endpoint accepts a push
# only when the header carries it.
PDF_SERVER_USAGE_TOKEN = PDF_SERVER_CONFIG.get("usage_token")
if not PDF_SERVER_USAGE_TOKEN:
    bad_config_file(
        "'usage_token' missing in [pdf_server] section "
        "(the shared secret the render server presents to report usage)"
    )

#########
# Billing
#########
BILLING_CONFIG = SITE_CONFIG.get("billing")
if not BILLING_CONFIG:
    bad_config_file("Missing [billing] section")

# TODO: plug the USD conversion in here, when a second currency is sold.
BILLING_CURRENCY = BILLING_CONFIG.get("currency")
if BILLING_CURRENCY != "EUR":
    bad_config_file("'currency' in [billing] section must be \"EUR\"")

##############
# Static files
##############
STATIC_CONFIG = SITE_CONFIG.get("static_files")
if (
    not STATIC_CONFIG
    or "static_url" not in STATIC_CONFIG
    or "static_root" not in STATIC_CONFIG
):
    bad_config_file("[static_files] section needs both 'static_url' and 'static_root'")

STATIC_URL = STATIC_CONFIG["static_url"]
STATIC_ROOT = STATIC_CONFIG["static_root"]
STATICFILES_DIRS = [BASE_DIR / "static"]

##############
# Applications
##############
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # Must precede staticfiles: disables runserver's own static handler so
    # WhiteNoise serves static in dev exactly as it does in production.
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "crispy_forms",
    "crispy_bootstrap5",
    "core",
    "accounts",
    "api_keys",
    "billing",
    "examples",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.front",
                "config.context_processors.seo",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

#################
# Authentication
#################
AUTH_USER_MODEL = "accounts.User"

# auth.E003 demands a *total* uniqueness on USERNAME_FIELD. A closed User row
# keeps its email, so uniqueness can only hold over live rows, and Django counts
# no conditional constraint as total. ``uniq_user_email_when_live`` enforces it
# where it can hold, and ``User.objects`` filters authentication down to the
# live row that constraint protects.
SILENCED_SYSTEM_CHECKS = ["auth.E003"]

PASSWORD_VALIDATION = "django.contrib.auth.password_validation"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"{PASSWORD_VALIDATION}.UserAttributeSimilarityValidator"},
    {"NAME": f"{PASSWORD_VALIDATION}.MinimumLengthValidator"},
    {"NAME": f"{PASSWORD_VALIDATION}.CommonPasswordValidator"},
    {"NAME": f"{PASSWORD_VALIDATION}.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "home"

######################
# Internationalization
######################
# DO NOT translate: each name must appear in its own language in the picker.
LANGUAGES = (
    ("en", "English"),
    ("fr", "Français"),
)
LANGUAGE_CODE = "en"
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

##########
# Sessions
##########
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = not DEBUG

#######
# Front
#######
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Assets load from a CDN and fall back to the copies collectstatic serves. The
# fallback covers a CDN outage, not the GDPR question: in the nominal case the
# visitor's IP reaches the third party.
CDN_ENABLED = SITE_CONFIG.get("front", {}).get("cdn_enabled", True)
