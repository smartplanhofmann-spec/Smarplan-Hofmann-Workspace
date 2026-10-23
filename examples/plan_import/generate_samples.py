#!/usr/bin/env python3
"""Generate synthetic-only JPEG/PNG and a two-page vector/scan PDF.

Run with the pinned backend/plan_import/requirements-test.lock environment:
    python examples/plan_import/generate_samples.py --output NEW_DIRECTORY

The red strokes resemble pen marks, not a handwriting-recognition benchmark.
No photographs, customer documents, external assets or network calls are used.
"""
import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import sys
import uuid

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


WIDTH, HEIGHT = 1800, 1300
FILENAMES = ('hausplan-foto.jpg', 'hausplan.png', 'hausplan.pdf')
BLACK = (28, 32, 35)
RED = (186, 35, 45)
PAPER = (250, 248, 243)


def _commands():
    # The same geometry, labels and pen-like marks drive raster and vector files.
    return [
        ('text', (900, 90), 'SYNTHETISCHER MUSTERPLAN', 48, BLACK),
        ('text', (900, 150), 'Fiktives Erdgeschoss - keine Kundenunterlagen', 28, BLACK),
        ('rect', (180, 230, 1620, 1130), 12, BLACK),
        ('line', [(900, 230), (900, 1130)], 10, BLACK),
        ('line', [(180, 830), (900, 830)], 10, BLACK),
        ('line', [(900, 680), (1620, 680)], 10, BLACK),
        ('text', (530, 410), 'WOHNEN', 58, BLACK),
        ('text', (530, 475), '6.00 x 5.00 m', 34, BLACK),
        ('text', (1260, 410), 'SCHLAFEN', 54, BLACK),
        ('text', (1260, 475), '6.00 x 3.75 m', 34, BLACK),
        ('text', (530, 950), 'KUECHE', 54, BLACK),
        ('text', (530, 1010), '6.00 x 2.50 m', 32, BLACK),
        ('text', (1260, 865), 'BAD', 58, BLACK),
        ('text', (1260, 930), '6.00 x 3.75 m', 34, BLACK),
        ('line', [(180, 1175), (1620, 1175)], 3, BLACK),
        ('line', [(180, 1160), (180, 1190)], 3, BLACK),
        ('line', [(1620, 1160), (1620, 1190)], 3, BLACK),
        ('text', (900, 1220), 'Beispielmass: 12.00 m', 32, BLACK),
        ('line', [(1660, 230), (1660, 1130)], 3, BLACK),
        ('line', [(1645, 230), (1675, 230)], 3, BLACK),
        ('line', [(1645, 1130), (1675, 1130)], 3, BLACK),
        ('text', (1725, 680), '7.50 m', 27, BLACK),
        # Deliberately irregular freehand-like "2x", arrow and crossed-out mark.
        ('line', [(425, 570), (442, 550), (470, 548), (489, 565),
                  (480, 585), (450, 604), (432, 617), (492, 620)], 7, RED),
        ('line', [(516, 566), (551, 620)], 7, RED),
        ('line', [(550, 563), (515, 621)], 7, RED),
        ('line', [(595, 589), (662, 582), (730, 591), (797, 578), (862, 584)], 7, RED),
        ('line', [(834, 564), (862, 584), (831, 602)], 7, RED),
        ('line', [(1050, 989), (1112, 978), (1164, 986), (1213, 975)], 6, RED),
        ('line', [(1055, 974), (1092, 1002), (1138, 974), (1180, 1000)], 6, RED),
        ('line', [(1370, 565), (1418, 599), (1460, 642)], 7, RED),
        ('line', [(1454, 608), (1460, 642), (1426, 635)], 7, RED),
        ('text', (900, 1280), 'Nur synthetische Testdaten - keine kalibrierte Zeichnung oder Handschrift-Abnahme', 21, BLACK),
    ]


def _raster(commands):
    image = Image.new('RGB', (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    for kind, *values in commands:
        if kind == 'text':
            position, text, size, color = values
            draw.text(position, text, font=ImageFont.load_default(size=size),
                      fill=color, anchor='mm')
        elif kind == 'rect':
            bounds, width, color = values
            draw.rectangle(bounds, outline=color, width=width)
        else:
            points, width, color = values
            draw.line(points, fill=color, width=width, joint='curve')
    return image


def _vector_page(document, commands):
    document.setFillColorRGB(*(channel / 255 for channel in PAPER))
    document.rect(0, 0, WIDTH, HEIGHT, fill=1, stroke=0)
    document.setLineCap(1)
    document.setLineJoin(1)
    for kind, *values in commands:
        if kind == 'text':
            (x, y), text, size, color = values
            document.setFillColorRGB(*(channel / 255 for channel in color))
            document.setFont('Helvetica', size)
            document.drawCentredString(x, HEIGHT - y - size * .35, text)
        elif kind == 'rect':
            (left, top, right, bottom), width, color = values
            document.setStrokeColorRGB(*(channel / 255 for channel in color))
            document.setLineWidth(width)
            document.rect(left, HEIGHT - bottom, right - left, bottom - top, fill=0, stroke=1)
        else:
            points, width, color = values
            document.setStrokeColorRGB(*(channel / 255 for channel in color))
            document.setLineWidth(width)
            path = document.beginPath()
            path.moveTo(points[0][0], HEIGHT - points[0][1])
            for x, y in points[1:]:
                path.lineTo(x, HEIGHT - y)
            document.drawPath(path, fill=0, stroke=1)


def sample_bytes():
    commands = _commands()
    with _raster(commands) as image:
        png, jpeg = BytesIO(), BytesIO()
        image.save(png, format='PNG', compress_level=6, dpi=(144, 144))
        image.save(jpeg, format='JPEG', quality=94, subsampling=0, dpi=(144, 144))
        pdf = BytesIO()
        document = Canvas(pdf, pagesize=(WIDTH / 2, HEIGHT / 2), invariant=1, pageCompression=1)
        document.setTitle('Synthetischer Musterplan: Vektor und Scan')
        document.setAuthor('Smartplan synthetic fixtures')
        document.setCreator('examples/plan_import/generate_samples.py')
        document.scale(.5, .5)
        _vector_page(document, commands)
        document.showPage()
        # No separate PDF text on page 2: it is an image-only scan fixture.
        document.drawImage(ImageReader(BytesIO(png.getvalue())), 0, 0,
                           width=WIDTH / 2, height=HEIGHT / 2)
        document.showPage()
        document.save()
        return dict(zip(FILENAMES, (jpeg.getvalue(), png.getvalue(), pdf.getvalue())))


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_samples(output):
    output = Path(output).absolute()
    if '..' in output.parts:
        raise ValueError('Parent traversal is not permitted for the output directory.')
    for path in (output, *output.parents):
        if path.is_symlink():
            raise ValueError('Symlink output paths are not permitted.')
    created_directory = False
    try:
        output.mkdir(mode=0o700)
        created_directory = True
        _sync_directory(output.parent)
    except FileExistsError:
        pass
    info = output.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError('The output must be a user-owned directory without group/other write permission.')
    for name in FILENAMES:
        path = output / name
        if path.exists() or path.is_symlink():
            raise FileExistsError('Refusing to replace an existing sample file: ' + name)
    created_files = []
    pending = None
    try:
        sources = sample_bytes()
        for name, content in sources.items():
            pending = output / ('.sample-' + uuid.uuid4().hex)
            descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
                file_info = os.fstat(stream.fileno())
            destination = output / name
            os.link(pending, destination, follow_symlinks=False)
            created_files.append((destination, file_info.st_dev, file_info.st_ino))
            pending.unlink()
            pending = None
            _sync_directory(output)
        return {'synthetic': True, 'directory': str(output),
                'files': {name: {'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
                          for name, content in sources.items()},
                'pdf_pages': ['vector_geometry_and_printed_text', 'image_only_scan'],
                'note': 'Pen-like red strokes are fixtures, not evidence of handwriting recognition.'}
    except BaseException:
        if pending is not None:
            pending.unlink(missing_ok=True)
        for path, device, inode in reversed(created_files):
            try:
                info = path.lstat()
                if (info.st_dev, info.st_ino) == (device, inode):
                    path.unlink()
            except FileNotFoundError:
                pass
        _sync_directory(output)
        if created_directory and not any(output.iterdir()):
            output.rmdir()
            _sync_directory(output.parent)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New directory, or a directory without these sample filenames.')
    args = parser.parse_args()
    try:
        result = write_samples(args.output)
    except (OSError, ValueError) as error:
        print('Sample generation failed: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
