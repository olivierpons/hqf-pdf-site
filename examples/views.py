"""The public examples gallery: a catalogue and the rendered samples.

Two server-rendered pages, both built from :data:`examples.catalog.EXAMPLES` and neither
touching the database (zero SQL queries): a catalogue that names and describes every
example, and a page that previews each rendered sample and offers it for download.
Both carry their own worked ``<title>``, meta description and JSON-LD so the gallery is
indexable on its own.
"""

import json
import struct
from functools import lru_cache

from django.contrib.staticfiles import finders
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .catalog import EXAMPLES, SAMPLES_DIR, THUMBNAILS_DIR


@lru_cache(maxsize=None)
def _png_size(static_path):
    """Return a PNG's intrinsic ``(width, height)`` in pixels, read once.

    Reads the file's IHDR header from the static store the first time a path is
    asked for and remembers it for the life of the process, so the samples page
    can stamp each thumbnail with its own size and the browser reserves its space
    before the image loads — no layout shift as the page scrolls.

    Args:
        static_path: The thumbnail's path within the static store.

    Returns:
        The width and height in pixels.
    """
    path = finders.find(static_path)
    with open(path, "rb") as handle:
        header = handle.read(24)
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def _sample_url(request, example):
    """Return the absolute URL of an example's rendered sample file.

    Args:
        request: The current request, for its scheme and host.
        example: One entry of :data:`examples.catalog.EXAMPLES`.

    Returns:
        The absolute URL of the file served from the static store.
    """
    return request.build_absolute_uri(static(f"{SAMPLES_DIR}/{example['file']}"))


def _thumbnail(request, example):
    """Return a PDF sample's first-page thumbnail: its URL and pixel size.

    The thumbnail shares the sample's basename with a ``.png`` extension, and is
    what the samples page shows in place of the file itself: a light image the
    browser lazy-loads and the visitor clicks through to the PDF. Its intrinsic
    size travels with it so the ``img`` reserves the right box before it loads.

    Args:
        request: The current request, for its scheme and host.
        example: One entry of :data:`examples.catalog.EXAMPLES`.

    Returns:
        A mapping with the absolute ``url`` and the ``width`` and ``height`` in
        pixels.
    """
    path = f"{THUMBNAILS_DIR}/{example['file'].rsplit('.', 1)[0]}.png"
    width, height = _png_size(path)
    return {
        "url": request.build_absolute_uri(static(path)),
        "width": width,
        "height": height,
    }


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
            "description": str(example["summary"]),
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
            "[Browse the PDFs hqf-pdf produces: invoices, delivery notes, "
            "payslips, contracts, certificates and labels, plus text flow, "
            "tables, images, barcodes, QR codes, forms and Factur-X PDF/A-3. "
            "Every sample is viewable and downloadable.]"
        ),
        "jsonld": _catalog_jsonld(request),
    }
    return render(request, "examples/catalog.html", context)


def rendered_samples(request):
    """Show every rendered sample as a clickable thumbnail, each with a download link.

    Queries: none.

    Args:
        request: The current request.

    Returns:
        The rendered-samples page.
    """
    samples = [
        {
            **example,
            "url": _sample_url(request, example),
            "thumbnail": (
                _thumbnail(request, example) if example["kind"] == "pdf" else None
            ),
        }
        for example in EXAMPLES
    ]
    context = {
        "samples": samples,
        "meta_title": _("[Rendered PDF samples from hqf-pdf]"),
        "meta_description": _(
            "[Preview and download the PDFs hqf-pdf renders, from a minimal page to "
            "invoices, payslips, barcoded labels, interactive forms and "
            "Factur-X PDF/A-3 files, each a click away from the full document.]"
        ),
    }
    return render(request, "examples/rendered_samples.html", context)
