"""Installer regression: incomplete iproute2 entries must not crash or fail open."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('check_dns', Path(__file__).with_name('check-dns.py'))
check_dns = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_dns)


class DnsPreflightTest(unittest.TestCase):
    def run_check(self, interfaces, answers):
        resolved = [(socket.AF_INET6 if ':' in address else socket.AF_INET,
                     socket.SOCK_STREAM, 6, '', (address, 443)) for address in answers]
        with patch.object(check_dns.subprocess, 'check_output', return_value=json.dumps(interfaces).encode()), \
                patch.object(check_dns.socket, 'getaddrinfo', return_value=resolved), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            check_dns.main()
            return output.getvalue()

    def test_incomplete_records_do_not_reject_matching_dns(self):
        interfaces = [{'addr_info': [{}, {'family': 'inet6'}, {'local': None},
                                     {'local': '116.203.43.69'}]}, {}]
        self.assertIn('DNS passt', self.run_check(interfaces, ['116.203.43.69']))

    def test_missing_local_addresses_fail_closed(self):
        with self.assertRaisesRegex(SystemExit, 'Keine lokalen'):
            self.run_check([{'addr_info': [{}]}], ['116.203.43.69'])

    def test_foreign_or_empty_dns_is_rejected(self):
        interfaces = [{'addr_info': [{}, {'local': '116.203.43.69'}]}]
        for answers in ([], ['192.0.2.1'], ['116.203.43.69', '2001:db8::1']):
            with self.subTest(answers=answers), self.assertRaisesRegex(SystemExit, 'DNS zeigt nicht'):
                self.run_check(interfaces, answers)

    def test_both_configured_ip_families_are_accepted(self):
        interfaces = [{'addr_info': [{'local': '116.203.43.69'}, {'local': '2001:db8::1'}]}]
        self.assertIn('DNS passt', self.run_check(interfaces, ['116.203.43.69', '2001:db8::1']))


if __name__ == '__main__':
    unittest.main()
