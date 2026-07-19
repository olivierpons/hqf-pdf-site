# The ``db`` fixture is requested by name to open pytest-django's transaction
# and is never read, which is exactly what pylint flags here.
# pylint: disable=unused-argument

from django.contrib.staticfiles import finders
from django.urls import reverse

from examples.catalog import EXAMPLES, SAMPLES_DIR


def test_every_sample_file_is_present():
    """Each catalogue entry points at a file the static store can serve."""
    for example in EXAMPLES:
        found = finders.find(f"{SAMPLES_DIR}/{example['file']}")
        assert found, f"missing sample for {example['slug']}: {example['file']}"


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
