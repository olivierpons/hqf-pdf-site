from django.conf import settings
from django.urls import translate_url
from django.utils.translation import gettext_lazy as _

SITE_NAME = "hqf-pdf"


def front(request):
    """Expose the front-end settings every page's base template needs.

    Args:
        request: The current request, unused.

    Returns:
        A mapping with ``CDN_ENABLED``, telling the base template whether to
        pull Bootstrap and htmx from a CDN or from this site's own static
        files.
    """
    return {"CDN_ENABLED": settings.CDN_ENABLED}


def seo(request):
    """Expose the per-request SEO values the base template's ``<head>`` needs.

    Builds the canonical URL of the page being served and, for a mono-domain
    ``i18n_patterns`` site, the ``hreflang`` alternates: the same path under each
    language prefix, plus an ``x-default`` pointing at the site's default language. A
    page that sets no ``meta_title``/``meta_description`` falls back to the site-wide
    defaults returned here.

    Args:
        request: The current request, used for its path and host.

    Returns:
        A mapping with ``site_name``, ``canonical_url``, ``hreflang_alternates``
        (a list of ``{"code", "url"}``), ``x_default_url`` and the default
        title and description.
    """
    path = request.get_full_path()
    alternates = [
        {"code": code, "url": request.build_absolute_uri(translate_url(path, code))}
        for code, __ in settings.LANGUAGES
    ]
    x_default_url = request.build_absolute_uri(
        translate_url(path, settings.LANGUAGE_CODE)
    )
    return {
        "site_name": SITE_NAME,
        "canonical_url": request.build_absolute_uri(path),
        "hreflang_alternates": alternates,
        "x_default_url": x_default_url,
        "default_meta_title": _("[hqf-pdf — generate PDFs from your own application]"),
        "default_meta_description": _(
            "[Send a render request, get a PDF back: text flow, tables, styled "
            "runs, PDF/A-3 and Factur-X invoices, with no PDF toolkit to "
            "install on your side.]"
        ),
    }
