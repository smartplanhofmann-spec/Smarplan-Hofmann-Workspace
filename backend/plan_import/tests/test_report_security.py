"""Parse real standalone review HTML to keep imported text out of executable DOM.

These tests generate only a synthetic PNG and result dictionaries. They neither
open a browser nor resolve, fetch or execute any imported URL or document text.
"""
import base64
from copy import deepcopy
from hashlib import sha256
import html
from html.parser import HTMLParser
from io import BytesIO
import json
import math
import unittest

from PIL import Image

from plan_import.report import build_review


class ReviewDocument(HTMLParser):
    def __init__(self, document):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.scripts = []
        self.styles = []
        self.text = []
        self._active = None
        self.feed(document)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, tuple(attrs)))
        if tag in ('script', 'style'):
            target = self.scripts if tag == 'script' else self.styles
            target.append('')
            self._active = target

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._active = None

    def handle_data(self, data):
        self.text.append(data)
        if self._active is not None:
            self._active[-1] += data

    def attributes(self, tag):
        return [dict(attrs) for name, attrs in self.elements if name == tag]


def review_result():
    return {
        'schema_version': 1,
        'status': 'needs_review',
        'source': {'kind': 'pdf', 'filename': 'Synthetic plan.pdf', 'page_index': 0},
        'preview': {'width': 40, 'height': 30, 'coordinate_system': 'normalized_top_left'},
        'analysis': {
            'line_candidates': [{'start': [.1, .2], 'end': [.8, .7]}],
            'text_candidates': [{'text': 'Printed room', 'bbox': [.1, .1, .4, .3]}],
        },
        'pdf_text': [{'text': 'PDF room', 'bbox': [.5, .5, .8, .7],
                      'source_bbox': [200, 90, 320, 150]}],
        'warnings': ['Synthetic review fixture'],
    }


class ReportSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with Image.new('RGB', (40, 30), 'white') as image:
            output = BytesIO()
            image.save(output, format='PNG')
            cls.png = output.getvalue()

    def document(self, result):
        output = build_review(self.png, result)
        self.assertIsInstance(output, bytes)
        decoded = output.decode('utf-8')
        return decoded, ReviewDocument(decoded)

    def assert_no_imported_elements(self, baseline, actual):
        # Text may change, while element names, attributes, CSS and the one
        # fixed interaction script must remain exactly the same.
        self.assertEqual(actual.elements, baseline.elements)
        self.assertEqual(actual.scripts, baseline.scripts)
        self.assertEqual(actual.styles, baseline.styles)
        self.assertEqual(len(actual.scripts), 1)

    def test_ocr_and_pdf_script_terminators_stay_literal_text(self):
        _, baseline = self.document(review_result())
        payloads = (
            '</script><script>alert("OCR/PDF")</script>',
            '</button><img src="https://example.invalid/track" onerror="alert(1)">',
            '<svg onload="alert(1)"><a href="javascript:alert(2)">open</a></svg>',
            'Room A & B < 5 > 2 "quoted" \'single\' · Küche',
        )
        for origin in ('ocr', 'pdf'):
            for payload in payloads:
                with self.subTest(origin=origin, payload=payload):
                    result = review_result()
                    words = result['analysis']['text_candidates'] if origin == 'ocr' else result['pdf_text']
                    words[0]['text'] = payload
                    output, parsed = self.document(result)
                    self.assert_no_imported_elements(baseline, parsed)
                    self.assertIn(html.escape(payload, quote=True), output)
                    self.assertIn(payload, ''.join(parsed.text))
                    self.assertNotIn(payload, ''.join(parsed.scripts))

    def test_warning_and_source_filename_urls_are_displayed_without_becoming_resources(self):
        _, baseline = self.document(review_result())
        payload = '</pre><script>fetch("https://example.invalid/leak")</script><img src="file:///private/key">'
        result = review_result()
        result['warnings'] = [payload]
        result['source'] = {
            'filename': '"><image href="https://example.invalid/source.svg" onload="alert(1)">',
            'source_url': 'javascript:alert("source")',
            'nested': {'untrusted': payload, 'path': 'file:///private/secret.pdf'},
        }
        output, parsed = self.document(result)
        self.assert_no_imported_elements(baseline, parsed)
        self.assertIn(payload, ''.join(parsed.text))
        metadata = json.dumps(result['source'], ensure_ascii=False, indent=2, allow_nan=False)
        self.assertIn(html.escape(metadata, quote=True), output)
        for _, attrs in parsed.elements:
            for _, value in attrs:
                if value is not None:
                    self.assertNotIn('example.invalid', value)
                    self.assertNotIn('file:', value)
                    self.assertNotIn('javascript:', value)

    def test_imported_template_slot_names_are_not_expanded_a_second_time(self):
        _, baseline = self.document(review_result())
        payload = '__ROWS__ __IMAGE__ __LINES__ __WIDTH__ __METADATA__ </script><script>alert(1)</script>'
        result = review_result()
        result['analysis']['text_candidates'][0]['text'] = payload
        result['pdf_text'][0]['text'] = payload
        result['warnings'] = [payload]
        result['source']['filename'] = payload
        output, parsed = self.document(result)
        self.assert_no_imported_elements(baseline, parsed)
        self.assertIn(html.escape(payload, quote=True), output)
        self.assertIn(payload, ''.join(parsed.text))

    def test_preview_is_exact_self_contained_png_data_uri(self):
        _, parsed = self.document(review_result())
        images = parsed.attributes('image')
        self.assertEqual(len(images), 1)
        self.assertEqual((images[0]['width'], images[0]['height']), ('40', '30'))
        prefix = 'data:image/png;base64,'
        self.assertTrue(images[0]['href'].startswith(prefix))
        embedded = base64.b64decode(images[0]['href'][len(prefix):], validate=True)
        self.assertEqual(embedded, self.png)
        with Image.open(BytesIO(embedded)) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.size, (40, 30))

    def test_review_blocks_network_and_has_no_external_resource_or_fetch_code(self):
        _, parsed = self.document(review_result())
        policies = [meta['content'] for meta in parsed.attributes('meta')
                    if meta.get('http-equiv', '').lower() == 'content-security-policy']
        self.assertEqual(len(policies), 1)
        policy = dict((parts[0], parts[1:]) for directive in policies[0].split(';')
                      if (parts := directive.strip().split()))
        for directive in ('default-src', 'connect-src', 'base-uri', 'form-action'):
            self.assertEqual(policy.get(directive), ["'none'"])
        self.assertEqual(policy.get('img-src'), ['data:'])
        self.assertFalse(any('*' in values or any('http' in value for value in values)
                             for values in policy.values()))
        forbidden = {'iframe', 'frame', 'object', 'embed', 'base', 'link', 'form', 'audio', 'video'}
        self.assertFalse(forbidden.intersection(tag for tag, _ in parsed.elements))
        resource_attributes = {'src', 'href', 'xlink:href', 'srcset', 'action', 'formaction', 'poster', 'data'}
        resources = [(tag, name, value) for tag, attrs in parsed.elements for name, value in attrs
                     if name in resource_attributes]
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0][:2], ('image', 'href'))
        self.assertTrue(resources[0][2].startswith('data:image/png;base64,'))
        self.assertFalse(any(meta.get('http-equiv', '').lower() == 'refresh'
                             for meta in parsed.attributes('meta')))
        for style in parsed.styles:
            self.assertNotRegex(style, r'(?i)@import\b|url\s*\(')
        for script in parsed.scripts:
            self.assertNotRegex(script, r'(?i)\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|importScripts)\b|sendBeacon|\bimport\s*\(|\bWorker\s*\(')
            self.assertNotRegex(script, r'\b(?:eval|Function)\s*\(|innerHTML|outerHTML|document\.write')
        for _, attrs in parsed.elements:
            self.assertFalse(any(name.lower().startswith('on') for name, _ in attrs))

    def test_invalid_text_coordinates_cannot_escape_svg_attributes(self):
        invalid_boxes = (
            [math.nan, .1, .5, .5], [0, math.inf, .5, .5],
            [-.1, .1, .5, .5], [0, .1, 1.1, .5],
            [.8, .1, .5, .5], [0, .8, .5, .5],
            ['0" onload="alert(1)', .1, .5, .5], [False, .1, .5, .5],
        )
        for origin in ('ocr', 'pdf'):
            for box in invalid_boxes:
                with self.subTest(origin=origin, box=box):
                    result = review_result()
                    words = result['analysis']['text_candidates'] if origin == 'ocr' else result['pdf_text']
                    words[0]['bbox'] = box
                    with self.assertRaises(ValueError):
                        build_review(self.png, result)

    def test_invalid_line_coordinates_cannot_escape_svg_attributes(self):
        for coordinate in (math.nan, math.inf, -.1, 1.1, True, '0" onload="alert(1)'):
            with self.subTest(coordinate=coordinate):
                result = review_result()
                result['analysis']['line_candidates'][0]['start'][0] = coordinate
                with self.assertRaises(ValueError):
                    build_review(self.png, result)

    def test_non_finite_source_metadata_is_rejected_and_valid_inputs_are_unchanged(self):
        result = review_result()
        original = deepcopy(result)
        original_png_hash = sha256(self.png).digest()
        self.document(result)
        self.assertEqual(result, original)
        self.assertEqual(sha256(self.png).digest(), original_png_hash)
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                result = review_result()
                result['source']['untrusted_number'] = value
                with self.assertRaises(ValueError):
                    build_review(self.png, result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
