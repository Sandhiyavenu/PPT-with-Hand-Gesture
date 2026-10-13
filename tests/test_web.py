from pathlib import Path

import pymupdf
import pytest

from app.web import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client
    app.session_state.shutdown()  # type: ignore[attr-defined]


def make_pdf(path: Path, pages: int = 2) -> Path:
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1}")
    doc.save(path)
    doc.close()
    return path


def test_dashboard_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Touchless Presentation Control" in response.data


def test_status_defaults(client):
    payload = client.get("/api/status").get_json()
    assert payload["running"] is False
    assert payload["page_count"] == 0


def test_upload_rejects_missing_file(client):
    response = client.post("/api/upload", data={})
    assert response.status_code == 400


def test_upload_and_slide(client, tmp_path: Path):
    pdf = make_pdf(tmp_path / "deck.pdf", pages=3)
    with pdf.open("rb") as handle:
        response = client.post(
            "/api/upload",
            data={"file": (handle, "deck.pdf")},
            content_type="multipart/form-data",
        )
    assert response.status_code == 200
    info = response.get_json()
    assert info["page_count"] == 3

    slide = client.get("/api/slide/1")
    assert slide.status_code == 200
    assert slide.mimetype == "image/jpeg"

    status = client.get("/api/status").get_json()
    assert status["page_count"] == 3
    assert status["index"] == 0


def test_manual_action_updates_state(client, tmp_path: Path):
    pdf = make_pdf(tmp_path / "deck.pdf", pages=3)
    with pdf.open("rb") as handle:
        client.post(
            "/api/upload",
            data={"file": (handle, "deck.pdf")},
            content_type="multipart/form-data",
        )
    response = client.post("/api/action/next")
    assert response.get_json()["index"] == 1
    response = client.post("/api/action/zoom_in")
    assert response.get_json()["zoom"] > 1.0


def test_start_without_document_fails(client):
    response = client.post("/api/session/start")
    assert response.status_code == 400
    assert "error" in response.get_json()
