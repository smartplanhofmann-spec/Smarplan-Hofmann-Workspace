#!/usr/bin/env python3
"""Bounded GitHub diagnostics for Flutter --file-reporter json:<path>.

This reports results only; callers must preserve the Flutter process exit code.
No environment values, network services or test execution are used here.
"""
import argparse
import json
from pathlib import Path
import re
import sys

MAX_ANNOTATIONS = 10
MAX_ANNOTATION_CHARS = 3000
MAX_LINE_BYTES = 256 * 1024
MAX_REPORT_BYTES = 32 * 1024 * 1024
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def clean(value):
    if not isinstance(value, str):
        return ''
    value = ANSI.sub('', value).replace('\r\n', '\n').replace('\r', '\n')
    value = value.replace('\u2028', '\n').replace('\u2029', '\n')
    return ''.join(c if c in '\n\t' or ord(c) >= 32 else ' ' for c in value).encode('utf-8', 'replace').decode('utf-8')


def annotation(message):
    prefix = '::error title=Flutter test failure::'
    marker = '%0A[diagnostic truncated]'
    budget = MAX_ANNOTATION_CHARS - len(prefix) - len(marker)
    parts, size = [], 0
    for character in clean(message):
        escaped = {'%': '%25', '\n': '%0A'}.get(character, character)
        if size + len(escaped) > budget:
            return prefix + ''.join(parts) + marker
        parts.append(escaped)
        size += len(escaped)
    return prefix + ''.join(parts)


def parse_report(path):
    names, failures = {}, {}
    result = dict(failures=failures, recognized=0, malformed=0, omitted=False,
                  truncated=False, missing=False, success=None)

    def record(test_id, message=''):
        if test_id not in failures:
            if len(failures) >= MAX_ANNOTATIONS:
                result['omitted'] = True
                return
            failures[test_id] = {'name': names.get(test_id, 'Test #' + str(test_id)), 'message': ''}
        saved = failures[test_id]
        if message and len(saved['message']) < 6000:
            saved['message'] = (saved['message'] + ('\n' if saved['message'] else '') + message)[:6000]

    try:
        with Path(path).open('rb') as source:
            consumed = 0
            while True:
                raw = source.readline(MAX_LINE_BYTES + 1)
                if not raw:
                    break
                consumed += len(raw)
                if consumed > MAX_REPORT_BYTES:
                    result['truncated'] = True
                    break
                if len(raw) > MAX_LINE_BYTES:
                    result['malformed'] += 1
                    while raw and not raw.endswith(b'\n') and consumed <= MAX_REPORT_BYTES:
                        raw = source.readline(MAX_LINE_BYTES + 1)
                        consumed += len(raw)
                    continue
                try:
                    event = json.loads(raw)
                except (ValueError, UnicodeError):
                    result['malformed'] += 1
                    continue
                if not isinstance(event, dict):
                    result['malformed'] += 1
                    continue
                kind = event.get('type')
                if kind == 'testStart':
                    test = event.get('test')
                    if not isinstance(test, dict) or type(test.get('id')) is not int or not isinstance(test.get('name'), str):
                        result['malformed'] += 1
                        continue
                    test_id, name = test['id'], clean(test['name'])[:400]
                    if len(names) >= 4096:
                        names.pop(next(iter(names)))
                    names[test_id] = name
                    if test_id in failures:
                        failures[test_id]['name'] = name
                    result['recognized'] += 1
                elif kind in ('error', 'testDone'):
                    test_id = event.get('testID')
                    if type(test_id) is not int:
                        test_id = 'runner'
                        names[test_id] = 'Flutter test runner'
                    result['recognized'] += 1
                    if kind == 'error':
                        message = clean(event.get('error'))[:4500]
                        stack = clean(event.get('stackTrace'))[:1500]
                        record(test_id, message + ('\n' + stack if stack else ''))
                    else:
                        if event.get('result') in ('failure', 'error') and test_id not in failures:
                            record(test_id, 'Test ended with result ' + event['result'] + '; no error event was recorded.')
                        names.pop(test_id, None)
                elif kind == 'done':
                    result['recognized'] += 1
                    result['success'] = event.get('success')
    except OSError:
        result['missing'] = True
    return result


def fallback_tail(path):
    if path is None:
        return 'No fallback log was supplied.'
    try:
        with Path(path).open('rb') as source:
            source.seek(0, 2)
            source.seek(max(0, source.tell() - 8192))
            tail = source.read(8192).decode('utf-8', 'replace')
        return '\n'.join(clean(tail).splitlines()[-12:])[-2000:] or 'Fallback log is empty.'
    except OSError:
        return 'Fallback log is unavailable.'


def report(report_path, *, log_path=None, summary_path=None, output=None):
    output = output or sys.stdout
    result = parse_report(report_path)
    failures = list(result['failures'].values())
    summaries = ['### Flutter test failure report']
    if result['missing'] or not result['recognized']:
        message = 'Flutter JSON report is missing or unusable. Bounded fallback log tail:\n' + fallback_tail(log_path)
        print(annotation(message), file=output)
        summaries.append(message)
    elif failures:
        for failure in failures:
            print(annotation('Test: ' + failure['name'] + '\n' + failure['message']), file=output)
            name = clean(failure['name']).replace('\n', ' ').replace('`', "'")[:220]
            summaries.append('- `' + name.replace('<', '&lt;').replace('>', '&gt;') + '`')
        summaries.append(str(len(failures)) + ' failing test(s) reported.' +
                         (' Additional failures omitted (limit 10).' if result['omitted'] else ''))
    else:
        message = 'Flutter JSON contains no failing test events; inspect the Flutter process exit code separately.'
        if result['success'] is not True:
            print(annotation(message), file=output)
        summaries.append(message)
    if result['malformed'] or result['truncated']:
        summaries.append('Report was incomplete: malformed lines=' + str(result['malformed']) +
                         ', byte limit reached=' + str(result['truncated']).lower() + '.')
    summary = '\n\n'.join(summaries)[:6000] + '\n'
    if summary_path is not None:
        with Path(summary_path).open('a', encoding='utf-8') as destination:
            destination.write(summary)
    print('Flutter JSON diagnostics: ' + str(len(failures)) + ' failing test(s) mapped.', file=output)
    return len(failures)


def main(argv=None):
    if callable(getattr(sys.stdout, 'reconfigure', None)):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--log', type=Path, help='Expanded log; only read if the JSON report is unavailable')
    parser.add_argument('--summary', type=Path, help='Optional GitHub step summary file to append')
    args = parser.parse_args(argv)
    report(args.report, log_path=args.log, summary_path=args.summary)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
