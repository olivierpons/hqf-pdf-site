"""The static catalogue of rendered examples the gallery is built from.

Each entry mirrors one example the engine ships, with the title and one-line summary
shown on the pages, the rendered sample file it produced, and which language bindings
demonstrate it. The order is the order the pages list them in: the finished documents
first, then the pieces they are built from, from the smallest file to the archival ones.

``kind`` tells a sample apart: ``"pdf"`` files are embedded inline and viewable in the
browser, while ``"icc"`` is a colour profile the engine emits, offered as a download
rather than shown.

``file`` is ``None`` for an example the engine ships but whose rendered sample is not
published yet: it is listed and described in the catalogue, and left out of the
rendered-samples page.

Adding an example is one entry here plus its file under ``static/examples/samples/``;
nothing else references the list by position.
"""

from django.utils.translation import gettext_lazy as _

SAMPLES_DIR = "examples/samples"

EXAMPLES = [
    {
        "slug": "write_invoice",
        "file": "write_invoice.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A commercial invoice]"),
        "summary": _(
            "[A commercial invoice: letterhead, logo, a billed-lines table, "
            "totals, and a QR code that pays it by SEPA transfer.]"
        ),
    },
    {
        "slug": "write_delivery_note",
        "file": "write_delivery_note.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A delivery note]"),
        "summary": _(
            "[The note that travels with the goods: a barcode against each "
            "article, a box the receiver ticks, and the consignment's own code.]"
        ),
    },
    {
        "slug": "write_payslip",
        "file": "write_payslip.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A payslip]"),
        "summary": _(
            "[A payslip: eighteen contribution lines with employee and employer "
            "shares, the month against the year to date.]"
        ),
    },
    {
        "slug": "write_contract",
        "file": "write_contract.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A two-page services contract]"),
        "summary": _(
            "[A services agreement over two pages, ending in signature, name and "
            "date fields a reader fills in.]"
        ),
    },
    {
        "slug": "write_certificate",
        "file": "write_certificate.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A landscape certificate]"),
        "summary": _(
            "[A landscape certificate whose border and seal are drawn as paths, "
            "not placed as pictures.]"
        ),
    },
    {
        "slug": "write_boarding_pass",
        "file": "write_boarding_pass.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A boarding pass]"),
        "summary": _(
            "[A boarding pass carrying the IATA BCBP string a gate scanner reads.]"
        ),
    },
    {
        "slug": "write_labels",
        "file": "write_labels.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A sheet of shelf labels]"),
        "summary": _(
            "[A sheet of die-cut shelf labels, priced and barcoded, with cut "
            "marks in the margins.]"
        ),
    },
    {
        "slug": "write_pdf",
        "file": "write_pdf.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A minimal PDF]"),
        "summary": _("[The smallest complete file: a page, and shapes drawn on it.]"),
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
        "slug": "write_soft_hyphen",
        "file": "write_soft_hyphen.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Soft hyphens and no-break spaces]"),
        "summary": _(
            "[A justified column set twice: the long words breaking at their soft "
            "hyphens with a hyphen shown, or left whole, and a figure a no-break "
            "space keeps together.]"
        ),
    },
    {
        "slug": "write_break_after",
        "file": "write_break_after.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Break points after a slash or a hyphen]"),
        "summary": _(
            "[A justified column set twice: file paths and compounds running past "
            "the edge with no break points, then wrapping where a break after a "
            "slash or a hyphen is allowed.]"
        ),
    },
    {
        "slug": "write_clip",
        "file": "write_clip.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Clipping paths]"),
        "summary": _(
            "[A field of stripes shown through two clipping paths: a disc set by "
            "the nonzero rule, and a frame set by the even-odd rule over two "
            "nested rectangles.]"
        ),
    },
    {
        "slug": "write_transparency",
        "file": "write_transparency.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Transparency and blend modes]"),
        "summary": _(
            "[Half-opacity fills that overlap and mix, and one orange square laid "
            "over a blue bar in four blend modes, through an extended graphics "
            "state.]"
        ),
    },
    {
        "slug": "write_columns",
        "file": "write_columns.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Text poured into columns]"),
        "summary": _(
            "[One long passage poured into three columns, each fitting the lines "
            "its height allows and handing the rest to the next.]"
        ),
    },
    {
        "slug": "write_paragraphs",
        "file": "write_paragraphs.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Paragraph indents and spacing]"),
        "summary": _(
            "[The same two paragraphs six ways: indents, the room around a "
            "paragraph, its last line, its first baseline.]"
        ),
    },
    {
        "slug": "write_contents",
        "file": "write_contents.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A contents page with dot leaders]"),
        "summary": _(
            "[A contents page whose entries are led to their page numbers by dots "
            "the layout draws.]"
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
        "slug": "write_stamp",
        "file": "write_stamp.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Stamps fitted to a box]"),
        "summary": _(
            "[What a document says about itself — DRAFT, COPY, PAID — laid across "
            "boxes of four different shapes and scaled to each.]"
        ),
    },
    {
        "slug": "write_shrink_and_turn",
        "file": "write_shrink_and_turn.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Shrunk headings and a turned label]"),
        "summary": _(
            "[Headings of different lengths shrunk to share one column, and a "
            "label turned a quarter turn up the page's spine.]"
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
        "slug": "write_table_colored_borders",
        "file": "write_table_colored_borders.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Coloured cell borders and fills]"),
        "summary": _(
            "[A cell's four sides in four different colours, and coloured fills "
            "told apart from coloured borders.]"
        ),
    },
    {
        "slug": "write_table_paginated",
        "file": "write_table_paginated.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A self-paginating table]"),
        "summary": _(
            "[A long table handed over whole, deciding its own pagination, its "
            "heading on top of every page, its footnote under every page, its "
            "shading said once for the whole table, and a note the caller draws "
            "under each page from the geometry the placement gives it.]"
        ),
    },
    {
        "slug": "write_cell_overflow",
        "file": "write_cell_overflow.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Overlong text in a narrow cell]"),
        "summary": _(
            "[Overlong text in a narrow table cell: left to overflow the column, "
            "or cut to it.]"
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
        "slug": "write_image_gallery",
        "file": "write_image_gallery.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A gallery of picture formats]"),
        "summary": _(
            "[Every picture the tests ship with, on one page, each captioned with "
            "what its own file declares.]"
        ),
    },
    {
        "slug": "write_barcode",
        "file": "write_barcode.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Code 128 and retail barcodes]"),
        "summary": _(
            "[A page of barcodes, drawn as bars: Code 128 and the retail family, "
            "EAN-13, UPC-A, EAN-8.]"
        ),
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
        "slug": "write_datamatrix",
        "file": None,
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Data Matrix codes]"),
        "summary": _("[A page of Data Matrix codes, drawn as squares.]"),
    },
    {
        "slug": "write_pdf417",
        "file": "write_pdf417.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[PDF417 codes]"),
        "summary": _("[A page of PDF417 codes, drawn as stacked bars.]"),
    },
    {
        "slug": "write_aztec",
        "file": "write_aztec.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[Aztec codes]"),
        "summary": _("[A page of Aztec codes, drawn as squares.]"),
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
        "slug": "write_tagged",
        "file": None,
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[A tagged, accessible document]"),
        "summary": _(
            "[A document that says what each run of ink stands for, and which "
            "runs are furniture. Its prose and its table describe themselves, a "
            "paragraph and a cell at a time. Validates as PDF/A-3a and PDF/UA-1.]"
        ),
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
        "slug": "write_eval_watermark",
        "file": "write_eval_watermark.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[The evaluation watermark]"),
        "summary": _(
            "[What an unlicensed copy looks like: the evaluation watermark the "
            "library stamps on every page.]"
        ),
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
        "python": True,
        "title": _("[A Factur-X electronic invoice]"),
        "summary": _("[An electronic invoice: a PDF/A-3 file carrying its own XML.]"),
    },
    {
        "slug": "write_archival_form",
        "file": "write_archival_form.pdf",
        "kind": "pdf",
        "rust": True,
        "python": True,
        "title": _("[An archivable PDF/A-3 form]"),
        "summary": _(
            "[A form that is also a PDF/A-3 file: every field baked in with a "
            "visible border, needing no reader.]"
        ),
    },
    {
        "slug": "write_icc",
        "file": "write_icc.icc",
        "kind": "icc",
        "rust": True,
        "python": True,
        "title": _("[The embedded ICC profile]"),
        "summary": _("[The ICC profile the library embeds in a PDF/A file.]"),
    },
]
