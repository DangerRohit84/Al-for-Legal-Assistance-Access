from backend.app.security import validate_pdf
import pytest


def test_rejects_non_pdf_extension():
    with pytest.raises(ValueError, match="PDF only"):
        validate_pdf("notes.txt", "application/pdf", 1000, 2)


def test_rejects_oversize():
    with pytest.raises(ValueError, match="10 MB"):
        validate_pdf("a.pdf", "application/pdf", 11 * 1024 * 1024, 2)


def test_rejects_too_many_pages():
    with pytest.raises(ValueError, match="100 pages"):
        validate_pdf("a.pdf", "application/pdf", 1000, 101)


def test_accepts_valid_pdf():
    assert validate_pdf("rent.pdf", "application/pdf", 1000, 5) is True


def test_rejects_empty_file():
    with pytest.raises(ValueError, match="Empty file"):
        validate_pdf("a.pdf", "application/pdf", 0, 1)
