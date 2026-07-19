"""The static catalogue of rendered examples the gallery is built from.

Each entry mirrors one example the engine ships, with the title and one-line summary
shown on the pages, the rendered sample file it produced, and which language bindings
demonstrate it. The order is the order the pages list them in, from the smallest file to
the archival ones.

``kind`` tells a sample apart: ``"pdf"`` files are embedded inline and viewable in the
browser, while ``"icc"`` is a colour profile the engine emits, offered as a download
rather than shown.

Adding an example is one entry here plus its file under ``static/examples/samples/``;
nothing else references the list by position.
"""

from django.utils.translation import gettext_lazy as _

SAMPLES_DIR = "examples/samples"

EXAMPLES = [
    {
        "slug": "write_pdf",
        "file": "write_pdf.pdf",
        "kind": "pdf",
        "rust": True,
        "python": False,
        "title": _("[A minimal PDF]"),
        "summary": _("[The smallest complete file: a page, and text on it.]"),
    },
    {
        "slug": "write_text",
        "file": "write_text.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Embedded, subset fonts]"),
        "summary": _("[Text in an embedded font, subset to the glyphs it draws.]"),
    },
    {
        "slug": "write_flow",
        "file": "write_flow.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Paragraph flow and alignment]"),
        "summary": _(
            "[A paragraph broken into lines, set four ways: left, right, "
            "centred, justified.]"
        ),
    },
    {
        "slug": "write_flow_break",
        "file": "write_flow_break.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Breaking an overlong word]"),
        "summary": _(
            "[A word too wide for its column: left whole, or cut to the edge.]"
        ),
    },
    {
        "slug": "write_rich_text",
        "file": "write_rich_text.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Styled runs inside a paragraph]"),
        "summary": _(
            "[A paragraph whose style changes inside it: size, underline, colour.]"
        ),
    },
    {
        "slug": "write_table",
        "file": "write_table.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A multi-page invoice table]"),
        "summary": _(
            "[An invoice table, laid out across as many pages as its lines need.]"
        ),
    },
    {
        "slug": "write_table_borders",
        "file": "write_table_borders.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Cell margin, border, padding and fill]"),
        "summary": _(
            "[What a cell can do with its own box: margin, border, padding, fill.]"
        ),
    },
    {
        "slug": "write_table_paginated",
        "file": "write_table_paginated.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A self-paginating table]"),
        "summary": _("[A long table handed over whole, deciding its own pagination.]"),
    },
    {
        "slug": "write_meal_plan",
        "file": "write_meal_plan.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A narrow table with wide content]"),
        "summary": _(
            "[A day's meals in a narrow table: a dish too wide for its column, "
            "left whole or cut to it.]"
        ),
    },
    {
        "slug": "write_image",
        "file": "write_image.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Images on a page]"),
        "summary": _("[Images placed on a page.]"),
    },
    {
        "slug": "write_barcode",
        "file": "write_barcode.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Code 128 and EAN-13 barcodes]"),
        "summary": _("[A page of barcodes, drawn as bars: Code 128 and EAN-13.]"),
    },
    {
        "slug": "write_qr",
        "file": "write_qr.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[QR codes]"),
        "summary": _("[A page of QR codes, drawn as squares.]"),
    },
    {
        "slug": "write_links",
        "file": "write_links.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Internal and external links]"),
        "summary": _("[Pages that link out of themselves and to each other.]"),
    },
    {
        "slug": "write_page_labels",
        "file": "write_page_labels.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Custom page labels]"),
        "summary": _("[Pages numbered by their labels rather than their position.]"),
    },
    {
        "slug": "write_overlay",
        "file": "write_overlay.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[An overlay on a letterhead]"),
        "summary": _("[An invoice laid on a letterhead somebody else made.]"),
    },
    {
        "slug": "write_form",
        "file": "write_form.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[An interactive form]"),
        "summary": _(
            "[A form a reader fills in: text boxes, a check box, a drop-down, "
            "radio buttons.]"
        ),
    },
    {
        "slug": "write_facturx",
        "file": "write_facturx.pdf",
        "kind": "pdf",
        "rust": True,
        "python": False,
        "title": _("[A Factur-X electronic invoice]"),
        "summary": _("[An electronic invoice: a PDF/A-3 file carrying its own XML.]"),
    },
    {
        "slug": "write_archival_form",
        "file": "write_archival_form.pdf",
        "kind": "pdf",
        "rust": True,
        "python": False,
        "title": _("[An archivable PDF/A-3 form]"),
        "summary": _(
            "[A form that is also a PDF/A-3 file: every field baked in, "
            "needing no reader.]"
        ),
    },
    {
        "slug": "write_icc",
        "file": "write_icc.icc",
        "kind": "icc",
        "rust": True,
        "python": False,
        "title": _("[The embedded ICC profile]"),
        "summary": _("[The ICC profile the library embeds in a PDF/A file.]"),
    },
]
