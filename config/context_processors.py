from django.conf import settings


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
