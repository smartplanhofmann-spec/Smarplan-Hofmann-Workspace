"""Real in-memory source fixtures for safe plan previews and text coordinates.

The fixtures contain synthetic drawings only. No files, URLs, scripts or external
PDF actions are imported; text extraction is distinguished from image-only scans.
"""
from hashlib import sha256
from contextlib import closing
import importlib.util
from io import BytesIO
import math
import unittest

from PIL import Image, ImageDraw
HAS_REPORTLAB = importlib.util.find_spec('reportlab') is not None
HAS_PDFIUM = importlib.util.find_spec('pypdfium2') is not None
if HAS_REPORTLAB:
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.pdfencrypt import StandardEncryption
    from reportlab.pdfgen import canvas

from plan_import.render import RenderError, render_source


MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_PREVIEW_SIDE = 2200
requires_pdf = unittest.skipUnless(HAS_PDFIUM and HAS_REPORTLAB,
                                  'PDF fixture tests require the plan-import worker PDFium/ReportLab extras.')


def image_bytes(size=(120, 80), *, format='PNG', orientation=None):
    with Image.new('RGB', size, 'white') as image:
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, size[0] - 1, size[1] // 2 - 1), fill=(230, 20, 20))
        draw.rectangle((0, size[1] // 2, size[0] - 1, size[1] - 1), fill=(20, 20, 230))
        output = BytesIO()
        options = {}
        if orientation is not None:
            exif = Image.Exif()
            exif[274] = orientation
            options['exif'] = exif
        if format == 'JPEG':
            options['quality'] = 95
        image.save(output, format=format, **options)
        return output.getvalue()


def vector_pdf(*, pages=1, rotation=0, encrypted=False, page_size=(400, 300)):
    output = BytesIO()
    encryption = StandardEncryption('synthetic-password', ownerPassword='synthetic-owner', strength=128) if encrypted else None
    document = canvas.Canvas(output, pagesize=page_size, invariant=1, pageCompression=0, encrypt=encryption)
    for index in range(pages):
        document.setPageRotation(rotation)
        document.setFont('Helvetica', 12)
        document.drawString(72, 200, f'Floor {index + 1} reference 4.20 m')
        document.rect(35, 35, 240, 180, stroke=1, fill=0)
        document.showPage()
    document.save()
    return output.getvalue()


def scan_pdf():
    output = BytesIO()
    document = canvas.Canvas(output, pagesize=(400, 300), invariant=1)
    with Image.new('RGB', (500, 300), 'white') as image:
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 470, 270), outline='black', width=4)
        draw.text((65, 110), 'SCANNED NOTES ONLY', fill='black')
        document.drawImage(ImageReader(image), 30, 30, width=340, height=204)
    document.showPage()
    document.save()
    return output.getvalue()


class RenderSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.png = image_bytes()
        cls.jpeg = image_bytes(format='JPEG')
        if HAS_PDFIUM and HAS_REPORTLAB:
            cls.pdf = vector_pdf()
            cls.multi_pdf = vector_pdf(pages=2)

    def assert_png_preview(self, rendered):
        self.assertIsInstance(rendered.png_bytes, bytes)
        self.assertTrue(rendered.png_bytes.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertIsInstance(rendered.width, int)
        self.assertIsInstance(rendered.height, int)
        self.assertGreater(rendered.width, 0)
        self.assertGreater(rendered.height, 0)
        self.assertLessEqual(max(rendered.width, rendered.height), MAX_PREVIEW_SIDE)
        with Image.open(BytesIO(rendered.png_bytes)) as preview:
            self.assertEqual(preview.format, 'PNG')
            self.assertEqual(preview.size, (rendered.width, rendered.height))
            preview.load()
        self.assertIsInstance(rendered.source_metadata, dict)
        self.assertIsInstance(rendered.warnings, (list, tuple))
        self.assertTrue(all(isinstance(warning, str) and warning.strip() for warning in rendered.warnings))

    def assert_render_error(self, data, **kwargs):
        with self.assertRaises(RenderError) as caught:
            render_source(data, **kwargs)
        self.assertIsInstance(caught.exception.code, str)
        self.assertTrue(caught.exception.code.strip())
        self.assertTrue(str(caught.exception).strip())
        return caught.exception

    @staticmethod
    def text(rendered):
        return ''.join(span.text for span in rendered.text_spans).replace(' ', '').replace('\r', '').replace('\n', '')

    def assert_transform_matches_span(self, span, metadata):
        left, bottom, right, top = span.source_bbox
        self.assertLess(left, right)
        self.assertLess(bottom, top)
        a, b, c, d, e, f = metadata['source_to_preview']
        points = [(a * x + b * y + c, d * x + e * y + f)
                  for x in (left, right) for y in (bottom, top)]
        expected = (min(p[0] for p in points), min(p[1] for p in points),
                    max(p[0] for p in points), max(p[1] for p in points))
        self.assertEqual(len(span.bbox), 4)
        for actual, target in zip(span.bbox, expected):
            self.assertTrue(math.isfinite(actual))
            self.assertGreaterEqual(actual, -1e-6)
            self.assertLessEqual(actual, 1 + 1e-6)
            self.assertAlmostEqual(actual, target, delta=1e-5)

    def test_png_and_jpeg_are_sniffed_without_filename_and_keep_original_bytes(self):
        for source, expected_mime in ((self.png, 'image/png'), (self.jpeg, 'image/jpeg')):
            with self.subTest(mime=expected_mime):
                before = sha256(source).digest()
                rendered = render_source(source)
                self.assert_png_preview(rendered)
                self.assertEqual(rendered.source_metadata['kind'], 'image')
                self.assertEqual(rendered.source_metadata['mime_type'], expected_mime)
                self.assertEqual(rendered.source_metadata['source_width'], 120)
                self.assertEqual(rendered.source_metadata['source_height'], 80)
                self.assertFalse(rendered.text_spans)
                self.assertEqual(sha256(source).digest(), before)

    def test_matching_mime_hints_are_accepted_and_mismatched_hints_rejected(self):
        for source, hint in ((self.png, 'image/png'), (self.jpeg, 'image/jpeg')):
            with self.subTest(hint=hint):
                self.assert_png_preview(render_source(source, mime_type=hint))
        for source, hint in ((self.png, 'application/pdf'), (self.jpeg, 'image/png')):
            with self.subTest(wrong_hint=hint):
                self.assert_render_error(source, mime_type=hint)

    @requires_pdf
    def test_pdf_mime_hint_must_match_actual_pdf_bytes(self):
        self.assert_png_preview(render_source(self.pdf, mime_type='application/pdf'))
        self.assert_render_error(self.pdf, mime_type='image/jpeg')

    def test_exif_rotation_changes_display_but_preserves_original_source_metadata(self):
        source = image_bytes((20, 40), format='JPEG', orientation=6)
        before = sha256(source).digest()
        rendered = render_source(source)
        self.assert_png_preview(rendered)
        metadata = rendered.source_metadata
        self.assertEqual((metadata['source_width'], metadata['source_height']), (20, 40))
        self.assertEqual((metadata['oriented_width'], metadata['oriented_height']), (40, 20))
        self.assertAlmostEqual(rendered.width / rendered.height, 2, delta=.05)
        with Image.open(BytesIO(rendered.png_bytes)) as preview:
            preview = preview.convert('RGB')
            left = preview.getpixel((preview.width // 4, preview.height // 2))
            right = preview.getpixel((preview.width * 3 // 4, preview.height // 2))
            self.assertGreater(left[2], left[0] + 80)
            self.assertGreater(right[0], right[2] + 80)
        self.assertEqual(sha256(source).digest(), before)
        self.assertFalse(rendered.text_spans)

    def test_large_allowed_image_is_downsampled_with_its_source_dimensions_intact(self):
        source = image_bytes((3000, 500))
        rendered = render_source(source)
        self.assert_png_preview(rendered)
        self.assertEqual((rendered.source_metadata['source_width'], rendered.source_metadata['source_height']), (3000, 500))
        self.assertLess(rendered.width, 3000)
        self.assertAlmostEqual(rendered.width / rendered.height, 6, delta=.03)

    @requires_pdf
    def test_vector_pdf_keeps_text_and_declares_both_coordinate_systems(self):
        before = sha256(self.pdf).digest()
        rendered = render_source(self.pdf)
        self.assert_png_preview(rendered)
        metadata = rendered.source_metadata
        self.assertEqual(metadata['kind'], 'pdf')
        self.assertEqual(metadata['mime_type'], 'application/pdf')
        self.assertEqual(metadata['coordinate_system'], 'normalized_top_left')
        self.assertEqual(metadata['source_coordinate_system'], 'pdf_points_bottom_left')
        self.assertEqual((metadata['source_width'], metadata['source_height']), (400, 300))
        self.assertEqual((metadata['page_index'], metadata['page_count']), (0, 1))
        self.assertIn('Floor1reference4.20m', self.text(rendered))
        for span in rendered.text_spans:
            self.assert_transform_matches_span(span, metadata)
        self.assertEqual(sha256(self.pdf).digest(), before)

    @requires_pdf
    def test_scan_pdf_renders_without_claiming_extracted_text(self):
        rendered = render_source(scan_pdf())
        self.assert_png_preview(rendered)
        self.assertFalse(rendered.text_spans)
        self.assertEqual(rendered.source_metadata['page_count'], 1)
        self.assertTrue(rendered.warnings, 'A scan needs an explicit no-text/OCR limitation.')

    @requires_pdf
    def test_only_selected_zero_based_pdf_page_is_returned(self):
        first = render_source(self.multi_pdf, page=0)
        second = render_source(self.multi_pdf, page=1)
        self.assert_png_preview(second)
        self.assertEqual(second.source_metadata['page_index'], 1)
        self.assertEqual(second.source_metadata['page_count'], 2)
        self.assertIn('Floor1reference', self.text(first))
        self.assertNotIn('Floor2reference', self.text(first))
        self.assertIn('Floor2reference', self.text(second))
        self.assertNotIn('Floor1reference', self.text(second))
        self.assertNotEqual(first.png_bytes, second.png_bytes)

    @requires_pdf
    def test_pdf_rotation_is_reflected_in_preview_transform_and_text_boxes(self):
        expected = {
            0: (400, 300, (1 / 400, 0, 0, 0, -1 / 300, 1)),
            90: (300, 400, (0, 1 / 400, 0, 1 / 300, 0, 0)),
            180: (400, 300, (-1 / 400, 0, 1, 0, 1 / 300, 0)),
            270: (300, 400, (0, -1 / 400, 1, -1 / 300, 0, 1)),
        }
        for rotation, (width, height, transform) in expected.items():
            with self.subTest(rotation=rotation):
                rendered = render_source(vector_pdf(rotation=rotation))
                self.assert_png_preview(rendered)
                metadata = rendered.source_metadata
                self.assertEqual(metadata['rotation'], rotation)
                self.assertEqual((metadata['source_width'], metadata['source_height']), (width, height))
                self.assertEqual((metadata['display_width'], metadata['display_height']), (400, 300))
                self.assertEqual(len(metadata['source_to_preview']), 6)
                for actual, target in zip(metadata['source_to_preview'], transform):
                    self.assertAlmostEqual(actual, target, delta=1e-6)
                self.assertIn('Floor1reference', self.text(rendered))
                for span in rendered.text_spans:
                    self.assert_transform_matches_span(span, metadata)

    @requires_pdf
    def test_invalid_pdf_page_requests_raise_domain_errors(self):
        for page in (-1, 2, True, 1.5, '0', None):
            with self.subTest(page=page):
                self.assert_render_error(self.multi_pdf, page=page)

    def test_image_only_accepts_page_zero(self):
        for page in (-1, 1, True, 1.5, '0', None):
            with self.subTest(page=page):
                self.assert_render_error(self.png, page=page)

    def test_source_byte_limit_is_enforced_on_an_otherwise_valid_image(self):
        source = self.png + b'\0' * (MAX_SOURCE_BYTES + 1 - len(self.png))
        self.assertGreater(len(source), MAX_SOURCE_BYTES)
        self.assert_render_error(source)

    def test_source_image_pixel_limit_is_enforced_before_preview_downsampling(self):
        with Image.new('L', (9000, 5000), 255) as image:
            output = BytesIO()
            image.save(output, format='PNG')
        source = output.getvalue()
        self.assertLess(len(source), MAX_SOURCE_BYTES)
        self.assert_render_error(source)

    def test_source_image_at_exactly_forty_megapixels_is_accepted(self):
        # One-bit PNG keeps this real 40 MP boundary fixture small in memory.
        with Image.new('1', (8000, 5000), 1) as image:
            output = BytesIO()
            image.save(output, format='PNG')
        source = output.getvalue()
        self.assertLess(len(source), MAX_SOURCE_BYTES)
        rendered = render_source(source)
        self.assert_png_preview(rendered)
        self.assertEqual((rendered.source_metadata['source_width'],
                          rendered.source_metadata['source_height']), (8000, 5000))
        self.assertEqual((rendered.width, rendered.height), (2200, 1375))

    @requires_pdf
    def test_offset_pdf_cropbox_keeps_visible_text_and_source_coordinates_aligned(self):
        import pypdfium2 as pdfium

        cropbox = (50, 40, 350, 260)
        expected = {
            0: ((300, 220), (1 / 300, 0, -50 / 300, 0, -1 / 220, 260 / 220)),
            90: ((220, 300), (0, 1 / 220, -40 / 220, 1 / 300, 0, -50 / 300)),
        }
        for rotation, (display_size, transform) in expected.items():
            with self.subTest(rotation=rotation):
                output = BytesIO()
                with pdfium.PdfDocument(self.pdf) as document:
                    with closing(document.get_page(0)) as page:
                        page.set_cropbox(*cropbox)
                        page.set_rotation(rotation)
                    document.save(output)
                source = output.getvalue()
                before = sha256(source).digest()
                rendered = render_source(source)
                self.assert_png_preview(rendered)
                metadata = rendered.source_metadata
                self.assertEqual(tuple(metadata['page_bbox']), cropbox)
                self.assertEqual((metadata['source_width'], metadata['source_height']), (300, 220))
                self.assertEqual((metadata['display_width'], metadata['display_height']), display_size)
                self.assertEqual(metadata['rotation'], rotation)
                self.assertIn('Floor1reference4.20m', self.text(rendered))
                for actual, target in zip(metadata['source_to_preview'], transform):
                    self.assertAlmostEqual(actual, target, delta=1e-6)
                with Image.open(BytesIO(rendered.png_bytes)) as preview:
                    for span in rendered.text_spans:
                        self.assert_transform_matches_span(span, metadata)
                        left, top, right, bottom = span.bbox
                        pixel_box = (max(0, math.floor(left * preview.width) - 1),
                                     max(0, math.floor(top * preview.height) - 1),
                                     min(preview.width, math.ceil(right * preview.width) + 1),
                                     min(preview.height, math.ceil(bottom * preview.height) + 1))
                        with preview.crop(pixel_box).convert('L') as glyphs:
                            self.assertLess(glyphs.getextrema()[0], 100,
                                            f'Text span {span.text!r} must cover visible ink.')
                self.assertEqual(sha256(source).digest(), before)

    @requires_pdf
    def test_pdf_page_limit_and_last_accepted_page(self):
        self.assert_render_error(vector_pdf(pages=51))
        rendered = render_source(vector_pdf(pages=50), page=49)
        self.assert_png_preview(rendered)
        self.assertEqual((rendered.source_metadata['page_index'], rendered.source_metadata['page_count']), (49, 50))
        self.assertIn('Floor50reference', self.text(rendered))

    @requires_pdf
    def test_large_physical_pdf_page_never_produces_an_unbounded_bitmap(self):
        rendered = render_source(vector_pdf(page_size=(9000, 5000)))
        self.assert_png_preview(rendered)
        self.assertLessEqual(rendered.width * rendered.height, 40_000_000)

    @requires_pdf
    def test_encrypted_pdf_is_rejected_without_guessing_passwords(self):
        self.assert_render_error(vector_pdf(encrypted=True))

    def test_malformed_and_unsupported_sources_are_domain_errors(self):
        sources = (b'', b'not a drawing', self.png[:25], self.jpeg[:16],
                   b'\0\0\0\x18ftypheic\0\0\0\0heicmif1',
                   b'AC1032' + b'\0' * 50,
                   b'0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n',
                   b'AutoCAD Binary DXF\r\n\x1a\0' + b'\0' * 30)
        for source in sources:
            with self.subTest(header=source[:24]):
                self.assert_render_error(source)

    @requires_pdf
    def test_malformed_pdf_is_a_domain_error(self):
        self.assert_render_error(b'%PDF-1.7\n%%EOF\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
