"""Local geometric and printed-text candidates from an oriented source preview.

The caller owns decoding, EXIF orientation, source preservation and job storage.
This module never changes the supplied image, infers a drawing scale, interprets
handwriting or turns an image line into a confirmed wall. Coordinates describe
the input image extent, normalized to [0, 1], with the origin at the top left.
"""
from __future__ import annotations

import csv
import io
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import tempfile
import time

from PIL import Image


MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_SIDE = 6000
MAX_ANALYSIS_SIDE = 2048
MAX_LINE_CANDIDATES = 2000
MAX_TEXT_CANDIDATES = 2000
MAX_OCR_STDOUT_BYTES = 4 * 1024 * 1024
MAX_OCR_STDERR_BYTES = 64 * 1024


class RecognitionError(RuntimeError):
    """An explicit failed recognition attempt; no partial success is implied."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _kill_and_reap(process: subprocess.Popen, *, supervised: bool) -> None:
    if supervised:
        # The outer worker controller owns the group and cleans descendants.
        # Never signal that group here: it includes this recognizer process.
        process.kill()
    else:
        # Also kill children if the parent exited while a child kept a pipe open.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def _run_bounded(arguments: list[str], timeout: float, *, stdout_limit: int) -> bytes:
    """Drain both pipes with hard byte limits, then reap the local process."""
    if os.name != 'posix':
        raise RecognitionError('recognizer_unavailable', 'Local recognition requires the Linux worker.')
    supervised = os.environ.get('SMARTPLAN_IMPORT_SUPERVISED') == '1'
    try:
        process = subprocess.Popen(
            arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=not supervised,
            env={**os.environ, 'OMP_THREAD_LIMIT': '1'},
        )
    except OSError as exc:
        raise RecognitionError('ocr_unavailable', 'The local Tesseract executable is unavailable.') from exc

    output = bytearray()
    stderr_size = 0
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
    selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RecognitionError('ocr_timeout', 'Local OCR exceeded its time limit.')
            for key, _ in selector.select(min(remaining, 0.25)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if key.data == 'stdout':
                    if len(output) + len(chunk) > stdout_limit:
                        raise RecognitionError('ocr_output_limit', 'Local OCR exceeded its output limit.')
                    output.extend(chunk)
                else:
                    stderr_size += len(chunk)
                    if stderr_size > MAX_OCR_STDERR_BYTES:
                        raise RecognitionError('ocr_output_limit', 'Local OCR exceeded its diagnostic output limit.')
        try:
            returncode = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            raise RecognitionError('ocr_timeout', 'Local OCR exceeded its time limit.') from exc
        if returncode != 0:
            raise RecognitionError('ocr_failed', 'Local Tesseract did not complete successfully.')
        return bytes(output)
    finally:
        _kill_and_reap(process, supervised=supervised)
        selector.close()
        process.stdout.close()
        process.stderr.close()


def _language_selection(binary: str, requested: str, timeout: float) -> tuple[list[str], list[str], list[str]]:
    if not isinstance(requested, str) or not re.fullmatch(r'[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*', requested):
        raise RecognitionError('ocr_language', 'OCR languages must be local language IDs such as eng or deu+eng.')
    wanted = list(dict.fromkeys(requested.split('+')))
    raw = _run_bounded([binary, '--list-langs'], min(timeout, 5.0), stdout_limit=65536)
    available = {line.strip() for line in raw.decode('utf-8', errors='replace').splitlines()
                 if re.fullmatch(r'[A-Za-z0-9_]+', line.strip())}
    selected = [language for language in wanted if language in available and language != 'osd']
    missing = [language for language in wanted if language not in selected]
    warnings = ['ocr_language_unavailable:' + language for language in missing]
    if not selected and 'eng' in available:
        selected = ['eng']
        warnings.append('ocr_language_fallback_eng')
    if not selected:
        raise RecognitionError('ocr_language_unavailable', 'No requested local OCR language is installed.')
    return wanted, selected, warnings


def _rgb_copy(image: Image.Image) -> Image.Image:
    if 'A' in image.getbands() or (image.mode == 'P' and 'transparency' in image.info):
        rgba = image.convert('RGBA')
        background = Image.new('RGBA', image.size, 'white')
        background.alpha_composite(rgba)
        return background.convert('RGB')
    return image.convert('RGB')


def _lines(image: Image.Image) -> tuple[list[dict], list[str]]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RecognitionError('recognizer_unavailable', 'The local OpenCV/NumPy worker dependencies are missing.') from exc
    cv2.setNumThreads(1)
    analysis = image.copy()
    analysis.thumbnail((MAX_ANALYSIS_SIDE, MAX_ANALYSIS_SIDE), Image.Resampling.LANCZOS)
    width, height = analysis.size
    gray = cv2.cvtColor(np.asarray(analysis), cv2.COLOR_RGB2GRAY)
    detected = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(gray)[0]
    if detected is None:
        return [], []

    minimum_length = max(12.0, max(width, height) * 0.015)
    candidates = []
    seen = set()
    for raw in detected.reshape(-1, 4):
        x1, y1, x2, y2 = (float(value) for value in raw)
        length = math.hypot(x2 - x1, y2 - y1)
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)) or length < minimum_length:
            continue
        start, end = sorted(([max(0.0, min(1.0, x1 / width)), max(0.0, min(1.0, y1 / height))],
                             [max(0.0, min(1.0, x2 / width)), max(0.0, min(1.0, y2 / height))]))
        key = tuple(round(value * dimension) for point in (start, end)
                    for value, dimension in zip(point, (width, height)))
        if key in seen:
            continue
        seen.add(key)
        candidates.append((length, start, end))
    candidates.sort(key=lambda value: (-value[0], value[1], value[2]))
    warnings = ['line_candidate_limit_reached'] if len(candidates) > MAX_LINE_CANDIDATES else []
    result = []
    for index, (_, start, end) in enumerate(candidates[:MAX_LINE_CANDIDATES], 1):
        result.append({'id': f'line-{index:04d}', 'start': start, 'end': end,
                       'bbox': [min(start[0], end[0]), min(start[1], end[1]),
                                max(start[0], end[0]), max(start[1], end[1])],
                       'class': 'unknown', 'confidence': None, 'method': 'opencv_lsd'})
    return result, warnings


def _texts(tsv: bytes, width: int, height: int) -> tuple[list[dict], list[str]]:
    try:
        decoded = tsv.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise RecognitionError('ocr_malformed', 'Local OCR returned invalid text encoding.') from exc
    rows = csv.DictReader(io.StringIO(decoded), delimiter='\t', quoting=csv.QUOTE_NONE)
    required = {'level', 'left', 'top', 'width', 'height', 'conf', 'text'}
    if not rows.fieldnames or not required <= set(rows.fieldnames):
        raise RecognitionError('ocr_malformed', 'Local OCR returned an invalid TSV header.')
    result, warnings = [], []
    invalid = False
    limited = False
    try:
        for row in rows:
            if row.get('level') != '5':
                continue
            text = (row.get('text') or '').strip()
            if not text:
                continue
            try:
                left, top, box_width, box_height = (int(row[name]) for name in ('left', 'top', 'width', 'height'))
                confidence = float(row['conf'])
            except (TypeError, ValueError):
                invalid = True
                continue
            if (not math.isfinite(confidence) or not 0 <= confidence <= 100 or
                    min(left, top) < 0 or min(box_width, box_height) <= 0 or
                    left + box_width > width or top + box_height > height):
                invalid = True
                continue
            if len(result) == MAX_TEXT_CANDIDATES:
                limited = True
                continue
            result.append({'id': f'text-{len(result) + 1:04d}', 'text': text,
                           'bbox': [left / width, top / height,
                                    (left + box_width) / width, (top + box_height) / height],
                           'confidence': confidence / 100.0,
                           'class': 'unknown_text', 'method': 'tesseract_printed_ocr'})
    except csv.Error as exc:
        raise RecognitionError('ocr_malformed', 'Local OCR returned an invalid TSV structure.') from exc
    if invalid:
        warnings.append('ocr_invalid_rows_ignored')
    if limited:
        warnings.append('text_candidate_limit_reached')
    return result, warnings


def recognize_image(image: Image.Image, *, tesseract_binary: str = 'tesseract',
                    timeout_seconds: float = 15.0, ocr_languages: str = 'eng') -> dict:
    """Return local line/printed-word candidates; every result needs review.

    Input pixels stay untouched. The caller must retain the full source/preview,
    including colored marks, curved strokes and any handwriting not recognized.
    Missing local tools, timeouts and output overflows fail explicitly.
    """
    if not isinstance(image, Image.Image):
        raise RecognitionError('image_invalid', 'An oriented, decoded PIL image is required.')
    width, height = image.size
    if min(width, height) <= 0 or max(width, height) > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
        raise RecognitionError('image_limit', 'The recognition image exceeds the bounded worker dimensions.')
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or
            not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120):
        raise RecognitionError('ocr_timeout_invalid', 'OCR timeout must be positive and at most 120 seconds.')
    if not isinstance(tesseract_binary, (str, os.PathLike)) or not os.fspath(tesseract_binary):
        raise RecognitionError('ocr_unavailable', 'A local Tesseract executable is required.')
    binary = os.fspath(tesseract_binary)
    requested, selected, language_warnings = _language_selection(binary, ocr_languages, timeout_seconds)
    rgb = _rgb_copy(image)
    lines, line_warnings = _lines(rgb)
    with tempfile.TemporaryDirectory(prefix='smartplan-plan-ocr-') as directory:
        image_path = Path(directory) / 'source.png'
        rgb.save(image_path, format='PNG')
        tsv = _run_bounded([binary, str(image_path), 'stdout', '-l', '+'.join(selected),
                            '--psm', '11', 'tsv'], timeout_seconds, stdout_limit=MAX_OCR_STDOUT_BYTES)
    texts, text_warnings = _texts(tsv, width, height)
    return {
        'status': 'needs_review', 'image_size': {'width': width, 'height': height},
        'coordinate_system': 'normalized_0_1', 'origin': 'top_left',
        'line_candidates': lines, 'text_candidates': texts,
        'ocr': {'engine': 'tesseract', 'languages_requested': requested,
                'languages_used': selected, 'scope': 'printed_text_only',
                'confidence_kind': 'tesseract_word_score'},
        'warnings': ['geometry_has_no_cad_semantics', 'handwriting_not_interpreted', 'ocr_printed_text_only']
                    + language_warnings + line_warnings + text_warnings,
    }
