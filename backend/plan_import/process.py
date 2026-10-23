"""Bounded subprocess entry point; never called inside an HTTP transaction."""
import argparse
from dataclasses import asdict
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import stat
import sys


def _limit():
    # Each parser is killable and cannot consume the entire shared pilot host.
    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (40, 45))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "OMP_THREAD_LIMIT",
                 "OPENCV_FOR_THREADS_NUM"):
        os.environ[name] = "1"


def process_source(data, *, media_type=None, page=0, ocr_languages="eng"):
    from PIL import Image
    from .render import render_source
    from .recognize import recognize_image
    from .report import build_review

    rendered = render_source(data, media_type, page)
    with Image.open(io.BytesIO(rendered.png_bytes)) as image:
        image.load()
        analysis = recognize_image(image, ocr_languages=ocr_languages)
    result = {
        "schema_version": 1, "status": "needs_review",
        "source": {**rendered.source_metadata, "sha256": hashlib.sha256(data).hexdigest(),
                   "size": len(data), "selected_page": page},
        "preview": {"width": rendered.width, "height": rendered.height,
                    "coordinate_system": "normalized_top_left"},
        "analysis": analysis,
        "pdf_text": [asdict(span) for span in rendered.text_spans],
        "warnings": list(dict.fromkeys([*rendered.warnings, *analysis["warnings"]])),
        "calibration": {"status": "unknown", "units": "unitless"},
    }
    return {"preview.png": rendered.png_bytes,
            "review.html": build_review(rendered.png_bytes, result)}, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--media-type", required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--ocr-languages", default="eng")
    args = parser.parse_args()
    _limit()
    try:
        from .store import MAX_SOURCE_BYTES, MAX_RECOGNITION_BYTES, MAX_DERIVED_BYTES
        descriptor = os.open(args.source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('Source must be a regular file')
            data = stream.read(MAX_SOURCE_BYTES + 1)
        if len(data) > MAX_SOURCE_BYTES or hashlib.sha256(data).hexdigest() != args.sha256:
            raise ValueError("Source integrity validation failed")
        derived, result = process_source(data, media_type=args.media_type, page=args.page,
                                         ocr_languages=args.ocr_languages)
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > MAX_RECOGNITION_BYTES or any(len(v) > MAX_DERIVED_BYTES for v in derived.values()):
            raise ValueError("Recognition result exceeded its publication limit")
        output = Path(args.output)
        for name, content in {**derived, "result.json": encoded}.items():
            with (output / name).open("xb") as stream:
                stream.write(content)
        print(json.dumps({"status": "needs_review"}))
        return 0
    except Exception as error:
        # No raw parser diagnostics or extracted document contents in logs.
        code = getattr(error, "code", "processing_failed")
        print(json.dumps({"status": "failed", "error_code": code,
                          "message": "Lokale Verarbeitung fehlgeschlagen; das Original bleibt erhalten."}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
