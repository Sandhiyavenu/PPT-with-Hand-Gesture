from pathlib import Path

import pymupdf
import pytest

from app import file_manager
from app.file_manager import PresentationError, load_document, validate_file


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Slide {i + 1}")
    path = tmp_path / "deck.pdf"
    doc.save(path)
    doc.close()
    return path


def test_validate_rejects_unsupported_extension(tmp_path: Path):
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    with pytest.raises(PresentationError):
        validate_file(bad)


def test_validate_rejects_missing_and_empty(tmp_path: Path):
    with pytest.raises(PresentationError):
        validate_file(tmp_path / "missing.pdf")

    empty = tmp_path / "empty.pdf"
    empty.touch()
    with pytest.raises(PresentationError):
        validate_file(empty)


def test_validate_accepts_supported(sample_pdf: Path):
    assert validate_file(sample_pdf) == sample_pdf


def test_load_pdf_document(sample_pdf: Path, tmp_path: Path):
    document = load_document(sample_pdf, cache_dir=tmp_path / "cache")
    assert document.kind == "pdf"
    assert document.page_count == 3
    image = document.render(1)
    assert image.width == file_manager.config.SLIDE_BASE_WIDTH
    assert image.height > 0
    document.close()


def test_legacy_ppt_is_rejected(tmp_path: Path):
    legacy = tmp_path / "old.ppt"
    legacy.write_bytes(b"not really a ppt")
    with pytest.raises(PresentationError):
        load_document(legacy, cache_dir=tmp_path / "cache")
