"""Module 1 - File management.

Handles picking, validating and loading a presentation. PDF files are
rendered directly with PyMuPDF. PowerPoint files are exported to images via
PowerPoint automation so that the rest of the app can treat every slide as an
image regardless of the source format.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from PIL import Image

from . import config


class PresentationError(Exception):
    """Raised when a presentation cannot be validated or loaded."""


@dataclass
class LoadedPresentation:
    path: Path
    kind: str  # "pdf" or "pptx"
    page_count: int
    title: str


def validate_file(path: str | Path) -> Path:
    """Validate extension and existence of a presentation file."""
    if path is None:
        raise PresentationError("No file selected.")

    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise PresentationError(f"File not found: {file_path}")

    if file_path.stat().st_size == 0:
        raise PresentationError(f"File is empty: {file_path.name}")

    if file_path.suffix.lower() not in config.SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(config.SUPPORTED_EXTENSIONS))
        raise PresentationError(
            f"Unsupported file type '{file_path.suffix}'. Allowed: {allowed}"
        )

    return file_path


class BaseDocument:
    """Common interface for rendered presentations."""

    kind = "base"

    def __init__(self, path: Path, page_count: int) -> None:
        self.path = path
        self.page_count = page_count

    @property
    def title(self) -> str:
        return self.path.stem

    def render(self, index: int, target_width: int = config.SLIDE_BASE_WIDTH) -> Image.Image:
        raise NotImplementedError

    def close(self) -> None:
        pass


class PDFDocument(BaseDocument):
    """PDF presentation backed by PyMuPDF."""

    kind = "pdf"

    def __init__(self, path: Path) -> None:
        import pymupdf  # imported lazily so tests do not need the dependency

        self._doc = pymupdf.open(path)
        if self._doc.page_count == 0:
            raise PresentationError("The PDF contains no pages.")
        super().__init__(path, self._doc.page_count)

    def render(self, index: int, target_width: int = config.SLIDE_BASE_WIDTH) -> Image.Image:
        import pymupdf

        if not 0 <= index < self.page_count:
            raise PresentationError(f"Page {index} out of range.")

        page = self._doc.load_page(index)
        scale = target_width / max(page.rect.width, 1.0)
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def close(self) -> None:
        self._doc.close()


class PptxDocument(BaseDocument):
    """PowerPoint presentation exported to PNG images via PowerPoint COM."""

    kind = "pptx"

    def __init__(self, path: Path, export_dir: Path) -> None:
        self._export_dir = export_dir
        self._images = sorted(
            (p for p in export_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}),
            key=_natural_key,
        )
        if not self._images:
            raise PresentationError("PowerPoint export produced no slides.")
        super().__init__(path, len(self._images))

    def render(self, index: int, target_width: int = config.SLIDE_BASE_WIDTH) -> Image.Image:
        if not 0 <= index < self.page_count:
            raise PresentationError(f"Slide {index} out of range.")
        img = Image.open(self._images[index]).convert("RGB")
        if img.width != target_width:
            ratio = target_width / img.width
            img = img.resize((target_width, max(int(img.height * ratio), 1)))
        return img


def _natural_key(path: Path) -> tuple:
    import re

    parts = re.split(r"(\d+)", path.stem)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)


def export_pptx_to_images(path: Path, dest: Path) -> None:
    """Export every slide of a PPTX to PNG using PowerPoint automation."""
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except ImportError as exc:  # pragma: no cover - Windows only
        raise PresentationError(
            "PowerPoint automation requires pywin32. Install it with 'pip install pywin32'."
        ) from exc

    dest.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        presentation = app.Presentations.Open(
            str(path), ReadOnly=True, Untitled=False, WithWindow=False
        )
        presentation.Export(str(dest), "PNG")
    except Exception as exc:  # pragma: no cover - depends on host
        raise PresentationError(
            "Could not export the PowerPoint file. Make sure Microsoft PowerPoint "
            f"is installed and the file opens correctly. ({exc})"
        ) from exc
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


def load_document(
    path: str | Path,
    cache_dir: Path | None = None,
    progress: Optional[Callable[[str], None]] = None,
) -> BaseDocument:
    """Validate and load a presentation file into a renderable document."""
    file_path = validate_file(path)
    cache_dir = cache_dir or config.CACHE_DIR

    if file_path.suffix.lower() == ".pdf":
        if progress:
            progress("Reading PDF pages...")
        return PDFDocument(file_path)

    if file_path.suffix.lower() == ".ppt":
        raise PresentationError(
            "Legacy .ppt files are not supported directly. Save as .pptx first."
        )

    export_dir = cache_dir / f"pptx_{abs(hash(file_path.resolve().as_posix()))}"
    if export_dir.exists():
        shutil.rmtree(export_dir, ignore_errors=True)
    if progress:
        progress("Exporting slides with PowerPoint...")
    export_pptx_to_images(file_path, export_dir)
    return PptxDocument(file_path, export_dir)
