"""Bounded, local source previews; no OCR, CAD conversion or external actions.

Original bytes are only read. PDF links, JavaScript, attachments and form
actions are never opened or executed. PDFium is loaded only for PDF inputs.
Coordinates in TextSpan.bbox are normalized to the upright preview's top-left
origin; source_bbox retains the original PDF bottom-left page coordinates.
"""
from contextlib import closing
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import math
from threading import RLock
from typing import Any
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_PDF_PAGES = 50
MAX_PREVIEW_EDGE = 2200
MAX_TEXT_CHARACTERS = 100_000
MAX_PAGE_OBJECTS = 100_000
MAX_FORM_DEPTH = 16
_PDF_LOCK = RLock()  # PDFium is not thread-safe, including different documents.


class RenderError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class TextSpan:
    text: str
    bbox: tuple[float, float, float, float]
    source_bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class RenderedPage:
    png_bytes: bytes
    width: int
    height: int
    text_spans: tuple[TextSpan, ...]
    warnings: tuple[str, ...]
    source_metadata: dict[str, Any]


def _sniff(data: bytes) -> str:
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith(b'%PDF-'):
        return 'application/pdf'
    raise RenderError('unsupported_format',
                      'Nur JPEG, PNG und unverschlüsselte PDF-Dateien werden unterstützt; '
                      'HEIC, DXF und DWG benötigen einen eigenen Importweg.')


def _check_dimensions(width: float, height: float) -> None:
    if not all(math.isfinite(n) and n > 0 for n in (width, height)):
        raise RenderError('invalid_document', 'Ungültige Seitengröße.')
    if math.ceil(width) * math.ceil(height) > MAX_IMAGE_PIXELS:
        raise RenderError('image_too_large', 'Höchstens 40 Millionen Bildpunkte erlaubt.')


def _png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format='PNG', compress_level=6)
    return output.getvalue()


def _image_transform(orientation: int, width: int, height: int) -> list[float]:
    # Affine transform from original pixel bounds to normalized upright bounds.
    return {
        1: [1 / width, 0, 0, 0, 1 / height, 0],
        2: [-1 / width, 0, 1, 0, 1 / height, 0],
        3: [-1 / width, 0, 1, 0, -1 / height, 1],
        4: [1 / width, 0, 0, 0, -1 / height, 1],
        5: [0, 1 / height, 0, 1 / width, 0, 0],
        6: [0, -1 / height, 1, 1 / width, 0, 0],
        7: [0, -1 / height, 1, -1 / width, 0, 1],
        8: [0, 1 / height, 0, -1 / width, 0, 1],
    }[orientation]


def _render_image(data: bytes, mime: str, page: int) -> RenderedPage:
    if page != 0:
        raise RenderError('invalid_page', 'Ein Foto besitzt nur Seite 0.')
    notes = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as probe:
                width, height = probe.size
                _check_dimensions(width, height)
                if probe.format not in ('JPEG', 'PNG') or getattr(probe, 'n_frames', 1) != 1:
                    raise RenderError('unsupported_format', 'Nur einzelne JPEG-/PNG-Bilder werden unterstützt.')
                probe.verify()
            with Image.open(BytesIO(data)) as image:
                orientation = image.getexif().get(274, 1)
                if orientation not in range(1, 9):
                    orientation = 1
                    notes.append('invalid_exif_orientation_ignored')
                # A square bound commutes with EXIF orientation; shrink first
                # so transposition does not duplicate a full-resolution photo.
                image.thumbnail((MAX_PREVIEW_EDGE, MAX_PREVIEW_EDGE), Image.Resampling.LANCZOS)
                with ImageOps.exif_transpose(image) as upright:
                    # A fresh RGB image excludes source EXIF/GPS and flattens
                    # transparency to the same white background used for PDFs.
                    with Image.new('RGB', upright.size, 'white') as preview:
                        if 'A' in upright.getbands() or 'transparency' in upright.info:
                            with upright.convert('RGBA') as rgba:
                                with rgba.getchannel('A') as alpha:
                                    preview.paste(rgba, mask=alpha)
                        else:
                            with upright.convert('RGB') as rgb:
                                preview.paste(rgb)
                        png = _png(preview)
                        preview_width, preview_height = preview.size
        swapped = orientation in (5, 6, 7, 8)
        return RenderedPage(png, preview_width, preview_height, (), tuple(notes), {
            'kind': 'image', 'mime_type': mime, 'page_index': 0, 'page_count': 1,
            'source_width': width, 'source_height': height,
            'oriented_width': height if swapped else width,
            'oriented_height': width if swapped else height,
            'exif_orientation': orientation,
            'rotation': {3: 180, 6: 90, 8: 270}.get(orientation, 0),
            'coordinate_system': 'normalized_top_left',
            'source_coordinate_system': 'image_pixels_top_left',
            'source_to_preview': _image_transform(orientation, width, height),
        })
    except RenderError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise RenderError('image_too_large', 'Höchstens 40 Millionen Bildpunkte erlaubt.') from error
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, TypeError) as error:
        raise RenderError('invalid_document', 'JPEG-/PNG-Datei ist beschädigt oder ungültig.') from error


def _pdf_transform(page, bitmap, bounds) -> list[float]:
    left, bottom, right, top = bounds
    converter = bitmap.get_posconv(page)
    origin = converter.to_bitmap(left, bottom)
    horizontal = converter.to_bitmap(right, bottom)
    vertical = converter.to_bitmap(left, top)
    a = (horizontal[0] - origin[0]) / (right - left) / bitmap.width
    b = (vertical[0] - origin[0]) / (top - bottom) / bitmap.width
    d = (horizontal[1] - origin[1]) / (right - left) / bitmap.height
    e = (vertical[1] - origin[1]) / (top - bottom) / bitmap.height
    return [a, b, origin[0] / bitmap.width - a * left - b * bottom,
            d, e, origin[1] / bitmap.height - d * left - e * bottom]


def _normalized_box(box, transform):
    left, bottom, right, top = box
    a, b, c, d, e, f = transform
    corners = [(a * x + b * y + c, d * x + e * y + f)
               for x in (left, right) for y in (bottom, top)]
    return (max(0., min(1., min(p[0] for p in corners))),
            max(0., min(1., min(p[1] for p in corners))),
            max(0., min(1., max(p[0] for p in corners))),
            max(0., min(1., max(p[1] for p in corners))))


def _text_spans(page, pdfium, transform) -> tuple[TextSpan, ...]:
    spans = []
    word, boxes = [], []

    def flush():
        if boxes:
            box = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                   max(b[2] for b in boxes), max(b[3] for b in boxes))
            normalized = _normalized_box(box, transform)
            if normalized[0] < normalized[2] and normalized[1] < normalized[3]:
                spans.append(TextSpan(''.join(word), normalized, box))
        word.clear()
        boxes.clear()

    with closing(page.get_textpage()) as textpage:
        count = textpage.count_chars()
        if count > MAX_TEXT_CHARACTERS:
            raise RenderError('resource_limit', 'PDF-Seite enthält zu viele Textzeichen.')
        for index in range(count):
            codepoint = pdfium.raw.FPDFText_GetUnicode(textpage, index)
            character = chr(codepoint) if 0 <= codepoint <= 0x10ffff else ''
            if not character or character.isspace() or not character.isprintable():
                flush()
                continue
            box = textpage.get_charbox(index)
            if not all(math.isfinite(n) for n in box):
                raise RenderError('invalid_document', 'PDF enthält ungültige Textpositionen.')
            word.append(character)
            boxes.append(box)
        flush()
    return tuple(spans)


def _check_pdf_objects(page, pdfium):
    count = 0
    for obj in page.get_objects(max_depth=MAX_FORM_DEPTH):
        count += 1
        if count > MAX_PAGE_OBJECTS or (obj.type == pdfium.raw.FPDF_PAGEOBJ_FORM and
                                      obj.level >= MAX_FORM_DEPTH - 1):
            raise RenderError('resource_limit', 'PDF-Seite ist zu komplex oder zu tief verschachtelt.')
        if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
            _check_dimensions(*obj.get_px_size())


def _render_pdf(data: bytes, page_index: int) -> RenderedPage:
    try:
        import pypdfium2 as pdfium
    except ImportError as error:
        raise RenderError('missing_dependency', 'PDFium ist für den lokalen PDF-Import erforderlich.') from error
    try:
        with _PDF_LOCK, closing(pdfium.PdfDocument(data)) as document:
            # Empty-user-password PDFs may open successfully but are encrypted
            # nevertheless; they are deliberately outside this first import.
            if pdfium.raw.FPDF_GetSecurityHandlerRevision(document) >= 0:
                raise RenderError('encrypted_pdf', 'Verschlüsselte PDFs werden noch nicht unterstützt.')
            count = len(document)
            if count > MAX_PDF_PAGES:
                raise RenderError('pdf_too_many_pages', 'PDF mit höchstens 50 Seiten erwartet.')
            if not 0 <= page_index < count:
                raise RenderError('invalid_page', 'Gewählte PDF-Seite ist nicht vorhanden.')
            with closing(document.get_page(page_index)) as page:
                width, height = page.get_size()
                # PDF canvas units are not raster pixels: even a large vector
                # sheet is rendered only at the bounded preview resolution.
                if not all(math.isfinite(n) and n > 0 for n in (width, height)):
                    raise RenderError('invalid_document', 'Ungültige PDF-Seitengröße.')
                bounds = tuple(page.get_bbox())
                if not all(math.isfinite(n) for n in bounds) or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                    raise RenderError('invalid_document', 'Ungültiger PDF-Seitenbereich.')
                _check_pdf_objects(page, pdfium)
                scale = math.nextafter(MAX_PREVIEW_EDGE / max(width, height), 0.)
                # Explicitly no init_forms(), link/action APIs or JavaScript.
                # Static ink annotations remain visible in an annotated plan.
                with closing(page.render(scale=scale, may_draw_forms=False, draw_annots=True,
                                         limit_image_cache=True, rev_byteorder=True)) as bitmap:
                    if max(bitmap.width, bitmap.height) > MAX_PREVIEW_EDGE:
                        raise RenderError('resource_limit', 'PDF-Vorschau überschreitet die Bildgrenze.')
                    transform = _pdf_transform(page, bitmap, bounds)
                    with bitmap.to_pil() as image:
                        png = _png(image)
                    spans = _text_spans(page, pdfium, transform)
                    notes = [] if spans else ['no_embedded_text']
                    if document.get_formtype() != 0:
                        notes.append('pdf_forms_not_rendered')
                    return RenderedPage(png, bitmap.width, bitmap.height, spans, tuple(notes), {
                        'kind': 'pdf', 'mime_type': 'application/pdf',
                        'page_index': page_index, 'page_count': count,
                        'source_width': bounds[2] - bounds[0], 'source_height': bounds[3] - bounds[1],
                        'display_width': width, 'display_height': height,
                        'page_bbox': bounds, 'rotation': page.get_rotation(),
                        'coordinate_system': 'normalized_top_left',
                        'source_coordinate_system': 'pdf_points_bottom_left',
                        'source_units': 'PDF canvas units, normally 1/72 inch; no scale inferred',
                        'source_to_preview': transform,
                    })
    except RenderError:
        raise
    except pdfium.PdfiumError as error:
        if error.err_code == pdfium.raw.FPDF_ERR_PASSWORD:
            raise RenderError('encrypted_pdf', 'Verschlüsselte PDFs werden noch nicht unterstützt.') from error
        raise RenderError('invalid_document', 'PDF ist beschädigt oder kann nicht gelesen werden.') from error
    except (ValueError, OSError, OverflowError) as error:
        raise RenderError('invalid_document', 'PDF besitzt ungültige Seitendaten.') from error


def render_source(data: bytes, mime_type: str | None = None, page: int = 0) -> RenderedPage:
    """Render one zero-based source page entirely locally.

    A generic application/octet-stream hint is treated as unspecified. A
    specific hint must match the actual signature. Text is embedded PDF text
    only: an image/scan yields no invented OCR result. Preview transforms map
    source x,y to normalized x'=a*x+b*y+c, y'=d*x+e*y+f.
    """
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise RenderError('invalid_input', 'Nichtleere Quelldatei als Bytes erwartet.')
    if len(data) > MAX_INPUT_BYTES:
        raise RenderError('input_too_large', 'Quelldatei darf höchstens 20 MiB groß sein.')
    if type(page) is not int or page < 0:
        raise RenderError('invalid_page', 'Seitenindex muss eine nichtnegative ganze Zahl sein.')
    payload = bytes(data)
    mime = _sniff(payload)
    if mime_type is not None:
        if not isinstance(mime_type, str):
            raise RenderError('invalid_input', 'MIME-Hinweis muss eine Zeichenfolge sein.')
        hint = mime_type.split(';', 1)[0].strip().lower()
        hint = {'image/jpg': 'image/jpeg'}.get(hint, hint)
        if hint not in ('', 'application/octet-stream', mime):
            raise RenderError('mime_mismatch', 'MIME-Hinweis stimmt nicht mit dem Dateiinhalt überein.')
    result = _render_pdf(payload, page) if mime == 'application/pdf' else _render_image(payload, mime, page)
    result.source_metadata.update(source_bytes=len(payload), sha256=sha256(payload).hexdigest())
    return result
