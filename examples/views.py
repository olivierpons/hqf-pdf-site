"""The public examples gallery: a catalogue and the rendered samples.

Two server-rendered pages, both built from :data:`examples.catalog.EXAMPLES` and neither
touching the database (zero SQL queries): a catalogue that names and describes every
example, and a page that shows each rendered sample inline and offers it for download.
Both carry their own worked ``<title>``, meta description and JSON-LD so the gallery is
indexable on its own.
"""

import json

from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .catalog import EXAMPLES, SAMPLES_DIR


def _sample_url(request, example):
    """Return the absolute URL of an example's rendered sample file.

    Args:
        request: The current request, for its scheme and host.
        example: One entry of :data:`examples.catalog.EXAMPLES`.

    Returns:
        The absolute URL of the file served from the static store.
    """
    return request.build_absolute_uri(static(f"{SAMPLES_DIR}/{example['file']}"))


def _catalog_jsonld(request):
    """Return the catalogue page's JSON-LD, as a string ready to embed.

    Describes the page as a ``CollectionPage`` whose main entity is an ordered
    ``ItemList`` of the examples, each a ``ListItem`` naming the example and pointing at
    its rendered sample. Lazy titles are resolved against the active language before
    serialisation.

    Args:
        request: The current request, for absolute URLs.

    Returns:
        A JSON string.
    """
    items = [
        {
            "@type": "ListItem",
            "position": position,
            "name": str(example["title"]),
            "url": _sample_url(request, example),
        }
        for position, example in enumerate(EXAMPLES, start=1)
    ]
    document = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": str(_("[PDF examples rendered by hqf-pdf]")),
        "url": request.build_absolute_uri(reverse("examples:catalog")),
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(items),
            "itemListElement": items,
        },
    }
    return json.dumps(document)


def catalog(request):
    """List every example with its title, summary and bindings.

    Queries: none.

    Args:
        request: The current request.

    Returns:
        The catalogue page.
    """
    context = {
        "examples": EXAMPLES,
        "samples_url": reverse("examples:rendered_samples"),
        "meta_title": _("[PDF examples gallery — see what hqf-pdf renders]"),
        "meta_description": _(
            "[Browse the PDFs hqf-pdf produces: text flow, tables, styled runs, "
            "images, barcodes, QR codes, interactive forms, PDF/A-3 and Factur-X "
            "invoices. Every sample is viewable and downloadable.]"
        ),
        "jsonld": _catalog_jsonld(request),
    }
    return render(request, "examples/catalog.html", context)


def rendered_samples(request):
    """Show every rendered sample inline, each with a download link.

    Queries: none.

    Args:
        request: The current request.

    Returns:
        The rendered-samples page.
    """
    samples = [
        {**example, "url": _sample_url(request, example)} for example in EXAMPLES
    ]
    context = {
        "samples": samples,
        "meta_title": _("[Rendered PDF samples from hqf-pdf]"),
        "meta_description": _(
            "[View and download the PDFs hqf-pdf renders, from a minimal page to "
            "PDF/A-3 and Factur-X invoices, each shown inline in your browser.]"
        ),
    }
    return render(request, "examples/rendered_samples.html", context)
