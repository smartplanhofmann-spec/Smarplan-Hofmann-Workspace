"""Synthetic Flutter JSON protocol fixtures; no SDK, credentials or network."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('report-flutter-test-failures.py')
spec = importlib.util.spec_from_file_location('flutter_failure_reporter', SCRIPT)
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


class FlutterFailureReporterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'tests.jsonl'
        self.log = self.root / 'expanded.log'

    def events(self, *events):
        self.source.write_text(''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')

    def start(self, identifier, name):
        return {'type': 'testStart', 'test': {'id': identifier, 'name': name}}

    def error(self, identifier, message):
        return {'type': 'error', 'testID': identifier, 'error': message,
                'stackTrace': 'package:smartplan/synthetic_test.dart 12:3', 'isFailure': True}

    def run_report(self):
        output = io.StringIO()
        reporter.report(self.source, log_path=self.log, output=output)
        return output.getvalue()

    def test_interleaved_tests_map_actual_failure_and_never_include_unrelated_progress(self):
        self.events(self.start(1, 'Synthetic Windows import'), self.start(2, 'Unrelated passing widget'),
                    self.error(1, 'Expected: source retained\nActual: missing source'),
                    {'type': 'testDone', 'testID': 2, 'result': 'success'},
                    {'type': 'testDone', 'testID': 1, 'result': 'failure'}, {'type': 'done', 'success': False})
        self.log.write_text('UNRELATED PROGRESS\n' * 500)
        output = self.run_report()
        annotations = [line for line in output.splitlines() if line.startswith('::error ')]
        self.assertEqual(len(annotations), 1)
        self.assertIn('Synthetic Windows import', annotations[0])
        self.assertIn('Actual: missing source', annotations[0])
        self.assertIn('synthetic_test.dart 12:3', annotations[0])
        self.assertNotIn('Unrelated passing widget', output)
        self.assertNotIn('UNRELATED PROGRESS', output)

    def test_encoded_annotation_is_bounded_and_cannot_inject_workflow_commands(self):
        self.events(self.start(1, 'Synthetic\n::notice title=unsafe::name'),
                    self.error(1, '\x1b[31mCAUSE\x1b[0m\n' + '%\n::error::injected\n' * 10000))
        output = self.run_report()
        annotations = [line for line in output.splitlines() if line.startswith('::error ')]
        self.assertEqual(len(annotations), 1)
        self.assertLessEqual(len(annotations[0]), 3000)
        self.assertIn('CAUSE', annotations[0])
        self.assertIn('%25', annotations[0])
        self.assertNotIn('\x1b', output)
        self.assertNotIn('\n::notice', output)
        self.assertNotIn('\n::error::injected', output)

    def test_maximum_ten_distinct_failures_and_duplicate_error_done_is_one_annotation(self):
        events = []
        for identifier in range(14):
            events.extend([self.start(identifier, 'Synthetic case ' + str(identifier)),
                           self.error(identifier, 'Synthetic failure'),
                           {'type': 'testDone', 'testID': identifier, 'result': 'failure'}])
        self.events(*events)
        summary = self.root / 'summary.md'
        output = io.StringIO()
        reporter.report(self.source, summary_path=summary, output=output)
        self.assertEqual(sum(line.startswith('::error ') for line in output.getvalue().splitlines()), 10)
        self.assertIn('Additional failures omitted (limit 10)', summary.read_text())

    def test_test_done_failure_without_error_and_error_before_start_keep_test_names(self):
        self.events(self.error(4, 'Synthetic early exception'), self.start(4, 'Named after startup'),
                    self.start(5, 'Synthetic interrupted test'), {'type': 'testDone', 'testID': 5, 'result': 'error'})
        output = self.run_report()
        self.assertIn('Named after startup', output)
        self.assertIn('Synthetic interrupted test', output)
        self.assertIn('no error event was recorded', output)

    def test_missing_report_uses_only_a_bounded_log_tail_and_creates_summary(self):
        self.log.write_text('EARLY UNRELATED PROGRESS\n' * 10000 + 'SYNTHETIC FINAL CAUSE\n')
        summary = self.root / 'summary.md'
        result = subprocess.run([sys.executable, str(SCRIPT), '--report', str(self.source), '--log', str(self.log),
                                 '--summary', str(summary)], capture_output=True, text=True, check=True, timeout=5)
        annotation = result.stdout.splitlines()[0]
        self.assertLessEqual(len(annotation), 3000)
        self.assertIn('SYNTHETIC FINAL CAUSE', annotation)
        self.assertNotIn('EARLY UNRELATED PROGRESS%0AEARLY UNRELATED PROGRESS%0AEARLY', annotation[:120])
        self.assertIn('missing or unusable', summary.read_text())

    def test_malformed_and_oversized_lines_do_not_hide_a_later_real_failure(self):
        self.events(self.start(1, 'Synthetic later failure'), self.error(1, 'VISIBLE REAL CAUSE'))
        self.source.write_bytes(b'not json\n' + b'x' * (reporter.MAX_LINE_BYTES + 100) + b'\n' + self.source.read_bytes())
        output = self.run_report()
        self.assertIn('Synthetic later failure', output)
        self.assertIn('VISIBLE REAL CAUSE', output)

    def test_successful_machine_report_never_reads_fallback_or_emits_failure(self):
        self.events(self.start(1, 'Passing'), {'type': 'testDone', 'testID': 1, 'result': 'success'},
                    {'type': 'done', 'success': True})
        self.log.mkdir()  # Reading this as a fallback file would fail.
        output = self.run_report()
        self.assertNotIn('::error', output)
        self.assertIn('0 failing test(s) mapped', output)

    def test_flutter_widget_print_exception_precedes_generic_error_for_the_same_test(self):
        name = 'Camera capture acknowledges an encrypted photo and note before deleting its temporary original'
        self.events(self.start(1, name), self.start(2, 'Unrelated passing widget'),
                    {'type': 'print', 'testID': 2, 'messageType': 'print', 'message': 'UNRELATED WIDGET OUTPUT'},
                    {'type': 'print', 'testID': 1, 'messageType': 'print',
                     'message': '══╡ EXCEPTION CAUGHT BY FLUTTER TEST FRAMEWORK ╞══\n'
                                'Expected: exactly one matching candidate\nActual: zero widgets with text "Encrypted photo saved"\n'
                                'The expectation failed at synthetic_camera_test.dart:71'},
                    self.error(1, 'Test failed. See exception logs above.'),
                    {'type': 'testDone', 'testID': 1, 'result': 'failure'},
                    {'type': 'testDone', 'testID': 2, 'result': 'success'})
        output = self.run_report()
        annotation = next(line for line in output.splitlines() if line.startswith('::error '))
        self.assertLessEqual(len(annotation), 3000)
        self.assertIn(name, annotation)
        self.assertIn('Actual: zero widgets with text "Encrypted photo saved"', annotation)
        self.assertIn('synthetic_camera_test.dart:71', annotation)
        self.assertLess(annotation.index('Expected:'), annotation.index('Test failed. See exception logs above.'))
        self.assertNotIn('UNRELATED WIDGET OUTPUT', output)

    def test_print_context_remains_bounded_and_follows_a_specific_error(self):
        events = [self.start(3, 'Synthetic print bounds')]
        events.extend({'type': 'print', 'testID': 3, 'messageType': 'print', 'message': 'OLD CONTEXT ' + 'x' * 3000}
                      for _ in range(100))
        events.extend([self.error(3, 'SPECIFIC ROOT ERROR'),
                       {'type': 'print', 'testID': 3, 'messageType': 'print',
                        'message': 'LATEST PRINT DETAIL\n::error::not a workflow command\n' + '%' * 5000},
                       {'type': 'testDone', 'testID': 3, 'result': 'error'}])
        self.events(*events)
        result = reporter.parse_report(self.source)
        self.assertLessEqual(len(result['failures'][3]['context']), 2400)
        output = self.run_report()
        annotation = next(line for line in output.splitlines() if line.startswith('::error '))
        self.assertLessEqual(len(annotation), 3000)
        self.assertLess(annotation.index('SPECIFIC ROOT ERROR'), annotation.index('LATEST PRINT DETAIL'))
        self.assertNotIn('\n::error::not a workflow command', output)


if __name__ == '__main__':
    unittest.main()
