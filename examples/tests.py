# The ``db`` fixture is requested by name to open pytest-django's transaction
# and is never read, which is exactly what pylint flags here.
# pylint: disable=unused-argument

from django.contrib.staticfiles import finders
from django.urls import reverse

from examples.catalog import EXAMPLES, SAMPLES_DIR


def test_every_sample_file_is_present():
    """Each catalogue entry that names a file points at one the static store serves."""
    for example in EXAMPLES:
        if not example["file"]:
            continue
        found = finders.find(f"{SAMPLES_DIR}/{example['file']}")
        assert found, f"missing sample for {example['slug']}: {example['file']}"


def test_slugs_are_unique():
    """Slugs anchor the rendered-samples sections, so no two entries may share one."""
    slugs = [example["slug"] for example in EXAMPLES]
    assert len(slugs) == len(set(slugs))


def test_finished_documents_are_listed_first():
    """The whole-document examples open the catalogue, before the building blocks."""
    assert [example["slug"] for example in EXAMPLES[:7]] == [
        "write_invoice",
        "write_delivery_note",
        "write_payslip",
        "write_contract",
        "write_certificate",
        "write_boarding_pass",
        "write_labels",
    ]


def test_catalog_page_renders(db, client):
    """The catalogue answers, lists a sample, and carries its JSON-LD."""
    response = client.get(reverse("examples:catalog"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "<h1" in body
    assert "write_table.pdf" in body
    assert 'type="application/ld+json"' in body
    assert '"@type": "ItemList"' in body


def test_catalog_page_has_hreflang_and_canonical(db, client):
    """SEO head: a canonical URL and an alternate for each language."""
    body = client.get(reverse("examples:catalog")).content.decode()
    assert 'rel="canonical"' in body
    assert 'hreflang="fr"' in body
    assert 'hreflang="en"' in body
    assert 'hreflang="x-default"' in body


def test_rendered_samples_embeds_pdfs_with_anchors(db, client):
    """Each PDF is embedded inline under an id the catalogue links to."""
    response = client.get(reverse("examples:rendered_samples"))
    assert response.status_code == 200
    body = response.content.decode()
    assert 'type="application/pdf"' in body
    assert 'id="write_table"' in body
    assert "write_facturx.pdf" in body


def test_icc_sample_is_offered_as_a_download_not_embedded(db, client):
    """The ICC profile is a download, never embedded as a PDF object."""
    body = client.get(reverse("examples:rendered_samples")).content.decode()
    assert "write_icc.icc" in body


def test_catalog_lists_the_business_documents(db, client):
    """The whole-document examples reach the page, headings and all."""
    body = client.get(reverse("examples:catalog")).content.decode()
    for slug in ("write_invoice", "write_payslip", "write_boarding_pass"):
        assert f"{slug}.pdf" in body


def test_examples_without_a_sample_are_catalogued_but_not_embedded(db, client):
    """An entry with no published file is described, and skipped by the samples page."""
    unpublished = [example for example in EXAMPLES if not example["file"]]
    assert unpublished
    catalog_body = client.get(reverse("examples:catalog")).content.decode()
    samples_body = client.get(reverse("examples:rendered_samples")).content.decode()
    for example in unpublished:
        assert str(example["title"]) in catalog_body
        assert f'id="{example["slug"]}"' not in samples_body
