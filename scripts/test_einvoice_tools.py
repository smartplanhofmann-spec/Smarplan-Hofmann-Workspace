"""Reject tampered tools and unsafe bundles before installation (no network)."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('invoice_tool_setup', Path(__file__).with_name('fetch-einvoice-tools.py'))
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


class ToolSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_wrong_digest_never_installs_or_reuses_a_tool(self):
        content = b'Synthetic wrong tool, not an executable'
        with patch.object(tools.urllib.request, 'urlopen', return_value=io.BytesIO(content)):
            with self.assertRaisesRegex(ValueError, 'prüfsumme'):
                tools.download(self.root, 'tool.jar', 'https://example.test/tool', '0' * 64)
        self.assertEqual(list(self.root.iterdir()), [])
        destination = self.root / 'tool.jar'
        destination.write_bytes(content)
        with patch.object(tools.urllib.request, 'urlopen') as network:
            with self.assertRaises(ValueError):
                tools.download(self.root, 'tool.jar', 'https://example.test/tool', '0' * 64)
        network.assert_not_called()
        self.assertEqual(destination.read_bytes(), content)

    def test_verified_cached_tool_never_needs_another_download(self):
        content = b'Synthetic pinned bytes'
        (self.root / 'tool.jar').write_bytes(content)
        with patch.object(tools.urllib.request, 'urlopen') as network:
            result = tools.download(self.root, 'tool.jar', 'https://example.test/tool', hashlib.sha256(content).hexdigest())
        network.assert_not_called()
        self.assertEqual(result.read_bytes(), content)

    def test_total_download_deadline_cannot_leave_an_installable_partial_tool(self):
        content = b'Synthetic slow download'
        with patch.object(tools.urllib.request, 'urlopen', return_value=io.BytesIO(content)), \
                patch.object(tools.time, 'monotonic', side_effect=[0, 121]):
            with self.assertRaisesRegex(ValueError, 'Zeitlimit'):
                tools.download(self.root, 'tool.jar', 'https://example.test/tool', hashlib.sha256(content).hexdigest())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_traversal_and_symlink_entries_cannot_escape_staging(self):
        for name, symlink in (('../outside', False), ('/absolute', False), ('folder\\outside', False), ('link', True)):
            with self.subTest(name=name):
                archive = self.root / 'bad.zip'
                with zipfile.ZipFile(archive, 'w') as output:
                    info = zipfile.ZipInfo(name)
                    if symlink:
                        info.external_attr = 0o120777 << 16
                    output.writestr(info, b'Synthetic unsafe bundle')
                with self.assertRaises(ValueError):
                    tools.extract_configuration(archive, self.root / 'configuration')
                self.assertFalse((self.root / 'configuration').exists())
        self.assertFalse((self.root.parent / 'outside').exists())

    def test_modified_configuration_cannot_be_accepted_as_official(self):
        destination = self.root / 'configuration'
        destination.mkdir()
        (destination / 'scenarios.xml').write_text('<synthetic/>')
        with self.assertRaisesRegex(ValueError, 'verändert'):
            tools.extract_configuration(self.root / 'not-read.zip', destination)


if __name__ == '__main__':
    unittest.main()
