"""Local recognition evidence and resource bounds, using synthetic sources only.

The real OpenCV check demonstrates line extraction, and the optional real
Tesseract check demonstrates printed OCR. Neither establishes photo, handwriting
or architectural interpretation quality.
"""
import hashlib
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

from PIL import Image, ImageDraw, ImageFont

from plan_import.recognize import (
    MAX_IMAGE_SIDE,
    MAX_OCR_STDERR_BYTES,
    MAX_OCR_STDOUT_BYTES,
    MAX_TEXT_CANDIDATES,
    RecognitionError,
    recognize_image,
)


TSV_HEADER = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'


class PlanImportRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-recognition-test-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def ocr_stub(self, body, *, languages=('eng',)):
        """An actual executable boundary; no subprocess or OCR parser is mocked."""
        path = self.directory / 'ocr ; literal executable'
        language_listing = 'List of available languages (' + str(len(languages)) + '):\n' + '\n'.join(languages) + '\n'
        path.write_text(
            '#!' + sys.executable + '\n'
            'import os, subprocess, sys, time\n'
            'if "--list-langs" in sys.argv:\n'
            '    sys.stdout.write(' + repr(language_listing) + ')\n'
            '    raise SystemExit(0)\n' + body + '\n', encoding='utf-8')
        path.chmod(0o700)
        return str(path)

    def empty_ocr(self):
        return self.ocr_stub('sys.stdout.write(' + repr(TSV_HEADER) + ')')

    def assert_error(self, code, image, binary, *, timeout=2.0):
        with self.assertRaises(RecognitionError) as caught:
            recognize_image(image, tesseract_binary=binary, timeout_seconds=timeout)
        self.assertEqual(caught.exception.code, code)

    def assert_normalized_box(self, box):
        self.assertEqual(len(box), 4)
        self.assertTrue(all(isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 1
                            for value in box), box)
        self.assertLessEqual(box[0], box[2])
        self.assertLessEqual(box[1], box[3])

    def test_real_line_detector_finds_rectangle_and_diagonal_without_mutating_source(self):
        image = Image.new('RGB', (640, 480), 'white')
        drawing = ImageDraw.Draw(image)
        drawing.rectangle((100, 80, 540, 400), outline='black', width=3)
        drawing.line((150, 340, 480, 120), fill='black', width=3)
        original = hashlib.sha256(image.tobytes()).digest()
        result = recognize_image(image, tesseract_binary=self.empty_ocr())
        self.assertEqual(hashlib.sha256(image.tobytes()).digest(), original)
        self.assertEqual(image.size, (640, 480))
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['image_size'], {'width': 640, 'height': 480})
        self.assertEqual(result['coordinate_system'], 'normalized_0_1')
        self.assertEqual(result['origin'], 'top_left')
        self.assertEqual(result['text_candidates'], [])
        candidates = result['line_candidates']
        self.assertGreaterEqual(len(candidates), 5)
        self.assertEqual(len({line['id'] for line in candidates}), len(candidates))
        for line in candidates:
            self.assertTrue(line['id'])
            self.assertEqual(line['class'], 'unknown')
            self.assertIsNone(line['confidence'])
            self.assertEqual(line['method'], 'opencv_lsd')
            self.assert_normalized_box(line['bbox'])
            for endpoint in (line['start'], line['end']):
                self.assertEqual(len(endpoint), 2)
                self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1 for value in endpoint))

        def close_to(line, first, second):
            actual = ([line['start'][0] * 640, line['start'][1] * 480],
                      [line['end'][0] * 640, line['end'][1] * 480])
            return min(max(math.dist(actual[0], first), math.dist(actual[1], second)),
                       max(math.dist(actual[1], first), math.dist(actual[0], second))) < 15

        for first, second in (((100, 80), (540, 80)), ((540, 80), (540, 400)),
                              ((540, 400), (100, 400)), ((100, 400), (100, 80)),
                              ((150, 340), (480, 120))):
            with self.subTest(expected_segment=(first, second)):
                self.assertTrue(any(close_to(line, first, second) for line in candidates), candidates)

    def test_real_tsv_parser_preserves_printed_text_and_normalizes_word_box(self):
        tsv = TSV_HEADER + (
            '1\t1\t0\t0\t0\t0\t0\t0\t640\t480\t-1\t\n'
            '5\t1\t1\t1\t1\t1\t100\t50\t120\t30\t87.9\tROOM\n')
        binary = self.ocr_stub('sys.stdout.write(' + repr(tsv) + ')')
        result = recognize_image(Image.new('RGB', (640, 480), 'white'), tesseract_binary=binary)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(len(result['text_candidates']), 1)
        word = result['text_candidates'][0]
        self.assertTrue(word['id'])
        self.assertEqual(word['text'], 'ROOM')
        self.assertEqual(word['class'], 'unknown_text')
        self.assertEqual(word['method'], 'tesseract_printed_ocr')
        self.assertAlmostEqual(word['confidence'], .879)
        for actual, expected in zip(word['bbox'], (100 / 640, 50 / 480, 220 / 640, 80 / 480)):
            self.assertAlmostEqual(actual, expected)
        self.assert_normalized_box(word['bbox'])

    def test_unavailable_requested_language_does_not_silently_fall_back(self):
        binary = self.ocr_stub('assert sys.argv[sys.argv.index("-l") + 1] == "eng"\n'
                               'sys.stdout.write(' + repr(TSV_HEADER) + ')', languages=('eng',))
        result = recognize_image(Image.new('RGB', (320, 240), 'white'),
                                 tesseract_binary=binary, ocr_languages='deu')
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('ocr_language_unavailable:deu', result['warnings'])
        self.assertIn('ocr_language_fallback_eng', result['warnings'])
        self.assertEqual(result['ocr']['languages_requested'], ['deu'])
        self.assertEqual(result['ocr']['languages_used'], ['eng'])

    def test_excess_text_candidates_are_visibly_limited(self):
        tsv = TSV_HEADER + ''.join(
            f'5\t1\t1\t1\t1\t{index + 1}\t1\t1\t10\t10\t90\tword-{index}\n'
            for index in range(MAX_TEXT_CANDIDATES + 1))
        result = recognize_image(Image.new('RGB', (64, 64), 'white'),
                                 tesseract_binary=self.ocr_stub('sys.stdout.write(' + repr(tsv) + ')'))
        self.assertEqual(len(result['text_candidates']), MAX_TEXT_CANDIDATES)
        self.assertEqual(len({word['id'] for word in result['text_candidates']}), MAX_TEXT_CANDIDATES)
        self.assertEqual(result['text_candidates'][0]['text'], 'word-0')
        self.assertEqual(result['text_candidates'][-1]['text'], f'word-{MAX_TEXT_CANDIDATES - 1}')
        self.assertIn('text_candidate_limit_reached', result['warnings'])
        self.assertEqual(result['status'], 'needs_review')

    def test_side_limit_rejects_image_before_executing_ocr(self):
        self.assert_error('image_limit', Image.new('RGB', (MAX_IMAGE_SIDE + 1, 1)),
                          str(self.directory / 'must-not-be-executed'))

    def test_missing_tsv_header_is_rejected(self):
        self.assert_error('ocr_malformed', Image.new('RGB', (64, 64), 'white'),
                          self.ocr_stub('sys.stdout.write("not a TSV document\\n")'))

    def test_stdout_limit_is_enforced_before_parsing(self):
        binary = self.ocr_stub('sys.stdout.buffer.write(b"x" * ' + str(MAX_OCR_STDOUT_BYTES + 1) + '); sys.stdout.flush()')
        self.assert_error('ocr_output_limit', Image.new('RGB', (64, 64), 'white'), binary)

    def test_stderr_limit_is_enforced_even_with_valid_empty_tsv(self):
        binary = self.ocr_stub('sys.stdout.write(' + repr(TSV_HEADER) + '); sys.stdout.flush()\n'
                               'sys.stderr.buffer.write(b"x" * ' + str(MAX_OCR_STDERR_BYTES + 1) + '); sys.stderr.flush()')
        self.assert_error('ocr_output_limit', Image.new('RGB', (64, 64), 'white'), binary)

    def test_timeout_also_stops_child_processes(self):
        marker = self.directory / 'descendant-escaped-timeout'
        child = 'import time; from pathlib import Path; time.sleep(1.0); Path(' + repr(str(marker)) + ').write_text("escaped")'
        binary = self.ocr_stub('subprocess.Popen([sys.executable, "-c", ' + repr(child) + '])\n'
                               'time.sleep(30)')
        start = time.monotonic()
        # Standalone mode owns its own OCR session and must reap descendants.
        # The supervised mode's outer controller is tested separately.
        with mock.patch.dict(os.environ):
            os.environ.pop('SMARTPLAN_IMPORT_SUPERVISED', None)
            self.assert_error('ocr_timeout', Image.new('RGB', (64, 64), 'white'), binary, timeout=.2)
        self.assertLess(time.monotonic() - start, 3.0)
        time.sleep(1.2)
        self.assertFalse(marker.exists(), 'An OCR descendant survived the timeout and kept processing.')

    def test_supervised_ocr_stays_in_supervisors_process_group(self):
        observed_group = self.directory / 'observed-ocr-process-group'
        binary = self.ocr_stub('from pathlib import Path\n'
                               'Path(' + repr(str(observed_group)) + ').write_text(str(os.getpgrp()))\n'
                               'sys.stdout.write(' + repr(TSV_HEADER) + ')')
        supervising_group = os.getpgrp()
        with mock.patch.dict(os.environ, {'SMARTPLAN_IMPORT_SUPERVISED': '1'}):
            result = recognize_image(Image.new('RGB', (64, 64), 'white'), tesseract_binary=binary)
        self.assertEqual(int(observed_group.read_text()), supervising_group)
        self.assertEqual(os.getpgrp(), supervising_group)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['text_candidates'], [])

    @unittest.skipUnless(shutil.which('tesseract'), 'Local Tesseract binary required for real printed-OCR evidence')
    def test_real_local_ocr_reads_synthetic_printed_text(self):
        font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
        if not font_path.is_file():
            self.skipTest('Synthetic printed-OCR fixture requires the local DejaVuSans font.')
        image = Image.new('RGB', (1100, 240), 'white')
        ImageDraw.Draw(image).text((40, 65), 'SMARTPLAN ROOM 42', font=ImageFont.truetype(str(font_path), 64), fill='black')
        result = recognize_image(image, tesseract_binary=shutil.which('tesseract'), timeout_seconds=15.0)
        words = ' '.join(word['text'] for word in result['text_candidates']).upper()
        self.assertIn('SMARTPLAN', words)
        self.assertIn('42', words)
        self.assertEqual(result['status'], 'needs_review')
        for word in result['text_candidates']:
            self.assertEqual(word['class'], 'unknown_text')
            self.assertGreaterEqual(word['confidence'], 0)
            self.assertLessEqual(word['confidence'], 1)
            self.assert_normalized_box(word['bbox'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
