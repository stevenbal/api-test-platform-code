import raven

from .base import *

#
# Standard Django settings.
#

DEBUG = False

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)
MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'vng-staging',
        'USER': 'vng-staging',
        'PASSWORD': 'vng-staging',
        'HOST': '',  # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '',  # Set to empty string for default.
    }
}

# EMAIL_HOST = 'smtp.sendgrid.net'
# EMAIL_HOST_USER = 'apikey'
# EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

# Make this unique, and don't share it with anybody.
SECRET_KEY = '-tu6q!6cvp@pe5!97e1i##lmp_%yxjj$k20*ul+ac^u(p2)clj'

ALLOWED_HOSTS = ['.maykin.nl']  # not possible in other way due to django constraints

# Redis cache backend
# NOTE: If you do not use a cache backend, do not use a session backend or
# cached template loaders that rely on a backend.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1", # NOTE: watch out for multiple projects using the same cache!
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": True,
        }
    }
}

# Caching sessions.
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = "default"

# Caching templates.
TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', RAW_TEMPLATE_LOADERS),
]

LOGGING['loggers'].update({
    '': {
        'handlers': ['sentry'],
        'level': 'WARNING',
        'propagate': False,
    },
    'django': {
        'handlers': ['django'],
        'level': 'INFO',
        'propagate': True,
    },
    'django.security.DisallowedHost': {
        'handlers': ['django'],
        'level': 'CRITICAL',
        'propagate': False,
    },
})

#
# Custom settings
#

CELERY_BROKER_URL = "redis://127.0.0.1:6379/13"
# Show active environment in admin.
ENVIRONMENT = 'staging'

# We will assume we're running under https
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
#X_FRAME_OPTIONS = 'DENY'
# Only set this when we're behind Nginx as configured in our example-deployment
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF = True # Sets X-Content-Type-Options: nosniff
SECURE_BROWSER_XSS_FILTER = True # Sets X-XSS-Protection: 1; mode=block


#
# Library settings
#
ELASTIC_APM['SERVICE_NAME'] += ' ' + ENVIRONMENT

# Raven
INSTALLED_APPS = INSTALLED_APPS + [
    'raven.contrib.django.raven_compat',
]
RAVEN_CONFIG = {
    'dsn': 'https://e95a42127e6042c59d19376e566f027a:216cdab1ea4f40d0bd0dd8a74e2eef57@sentry.maykinmedia.nl/104',
    'public_dsn': 'https://e95a42127e6042c59d19376e566f027a@sentry.maykinmedia.nl/104',
    'release': raven.fetch_git_sha(BASE_DIR),
}

LOGGING['handlers'].update({
    'sentry': {
        'level': 'WARNING',
        'class': 'raven.handlers.logging.SentryHandler',
        'dsn': RAVEN_CONFIG['dsn']
    },
})
