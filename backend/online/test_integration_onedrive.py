"""Synthetic OneDrive bot-source validation; no Microsoft or database calls."""
import copy
import json
import unittest

from core import Problem
from online.integration_onedrive import (
    MAX_ITEMS, MAX_PAYLOAD_BYTES, normalize_bridge_catalog,
    normalize_bridge_resource, normalize_bridge_snapshot,
)


IDENTITY = {'id': 'synthetic-account-17', 'label': 'Synthetisches Microsoft-Konto'}
FOLDER = {'id': 'synthetic-folder-17', 'drive_id': 'b!synthetic-drive-17',
          'name': 'Projekt Ährenweg', 'path': '/Projekt Ährenweg',
          'url': 'https://synthetic.sharepoint.com/sites/Test/Shared%20Documents/Projekt%20%C3%84hrenweg'}
SELECTION = {'drive_id': FOLDER['drive_id'], 'folder_id': FOLDER['id']}
FILE = {'id': 'synthetic-file-17', 'drive_id': FOLDER['drive_id'], 'parent_id': FOLDER['id'],
        'name': 'Grundriss Ährenweg.pdf', 'path': '/Projekt Ährenweg/Grundriss Ährenweg.pdf',
        'rev': '"{SYNTHETIC-ETAG-17},1"', 'size': 12000, 'media_type': 'application/pdf',
        'url': 'https://synthetic.sharepoint.com/sites/Test/Shared%20Documents/Grundriss%20%C3%84hrenweg.pdf'}


def catalog(**changes):
    return {'complete': True, 'identity': copy.deepcopy(IDENTITY), 'folders': [copy.deepcopy(FOLDER)], **changes}


def resource(**changes):
    return {'complete': True, 'folder': copy.deepcopy(FOLDER), 'files': [copy.deepcopy(FILE)], **changes}


class OneDriveBridgeNormalizerTests(unittest.TestCase):
    def problem(self, status, callback):
        with self.assertRaises(Problem) as raised:
            callback()
        self.assertEqual(raised.exception.status, status, raised.exception.message)
        self.assertNotIn('synthetic-secret', raised.exception.message)
        return raised.exception

    def test_actual_normalized_catalog_preserves_original_identifiers_and_optional_parent(self):
        payload = catalog()
        payload['folders'][0]['parent_id'] = 'actual-parent-17'
        normalized = normalize_bridge_catalog(payload)
        self.assertEqual(normalized['identity'], IDENTITY)
        self.assertEqual(normalized['folders'], payload['folders'])
        self.assertNotIn('complete', normalized)
        payload['identity']['label'] = 'Later mutation'
        payload['folders'][0]['name'] = 'Later mutation'
        self.assertEqual(normalized['identity']['label'], IDENTITY['label'])
        self.assertEqual(normalized['folders'][0]['name'], FOLDER['name'])

    def test_catalog_ids_are_unique_per_drive_not_across_independent_drives(self):
        other = {**FOLDER, 'drive_id': 'b!another-drive'}
        self.assertEqual(len(normalize_bridge_catalog(catalog(folders=[FOLDER, other]))['folders']), 2)
        self.problem(400, lambda: normalize_bridge_catalog(catalog(folders=[FOLDER, FOLDER])))

    def test_resource_and_snapshot_match_exact_selection_and_keep_real_etag_and_mime(self):
        for normalize in (normalize_bridge_resource, normalize_bridge_snapshot):
            normalized = normalize(resource(), SELECTION)
            self.assertEqual(normalized, {'folder': FOLDER, 'files': [FILE]})
            self.assertEqual(normalized['files'][0]['rev'], '"{SYNTHETIC-ETAG-17},1"')
            self.assertNotIn('downloadable', normalized['files'][0])
            self.assertNotIn('content_hash', normalized['files'][0])

    def test_direct_parent_drive_and_path_are_all_required_not_inferred_from_names(self):
        for changes in ({'parent_id': 'different-folder'}, {'drive_id': 'another-drive'},
                        {'path': '/Other/Grundriss Ährenweg.pdf'}, {'id': FOLDER['id']},
                        {'path': '/Projekt Ährenweg/Subfolder/Grundriss Ährenweg.pdf'}):
            with self.subTest(changes=changes):
                self.problem(409, lambda: normalize_bridge_snapshot(resource(files=[{**FILE, **changes}]), SELECTION))
        for selection in ({**SELECTION, 'drive_id': 'another-drive'}, {**SELECTION, 'folder_id': 'another-folder'}):
            self.problem(409, lambda: normalize_bridge_resource(resource(), selection))

    def test_partial_or_undeclared_catalog_and_snapshots_never_become_empty_success(self):
        for complete in (False, None, 1, 'true'):
            self.problem(400, lambda: normalize_bridge_catalog(catalog(complete=complete)))
            self.problem(400, lambda: normalize_bridge_snapshot(resource(complete=complete), SELECTION))
        without = resource()
        without.pop('complete')
        self.problem(400, lambda: normalize_bridge_resource(without, SELECTION))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(has_more=True)))
        self.problem(400, lambda: normalize_bridge_resource(resource(has_more='false'), SELECTION))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(**{'@odata.nextLink': 'https://graph.microsoft.com/private'})))
        self.assertNotIn('has_more', normalize_bridge_resource(resource(has_more=False), SELECTION))

    def test_genuine_complete_empty_lists_still_require_identity_or_selected_folder(self):
        self.assertEqual(normalize_bridge_catalog(catalog(folders=[])), {'identity': IDENTITY, 'folders': []})
        self.assertEqual(normalize_bridge_resource(resource(files=[]), SELECTION), {'folder': FOLDER, 'files': []})
        self.problem(400, lambda: normalize_bridge_catalog({'complete': True, 'folders': []}))
        self.problem(400, lambda: normalize_bridge_snapshot({'complete': True, 'files': []}, SELECTION))

    def test_only_original_first_party_https_browser_links_are_retained(self):
        personal = 'https://onedrive.live.com/?cid=0123456789ABCDEF&id=0123456789ABCDEF%2117'
        normalized = normalize_bridge_resource(resource(files=[{**FILE, 'url': personal}]), SELECTION)
        self.assertEqual(normalized['files'][0]['url'], personal)
        for url in ('http://onedrive.live.com/file', 'https://1drv.ms/s/short', 'https://sharepoint.com/file',
                    'https://synthetic.sharepoint.com.evil.example/file', 'https://onedrive.live.com.evil.example/file',
                    'https://synthetic.sharepoint.com:444/file', 'https://secret@synthetic.sharepoint.com/file',
                    'https://synthetic.sharepoint.com/file#secret', 'https://onedrive.live.com/?authkey=synthetic-secret',
                    'https://synthetic.sharepoint.com/file?access_token=synthetic-secret',
                    'https://synthetic.sharepoint.com/file?download=1', 'https://synthetic.sharepoint.com/file?action=download',
                    'https://synthetic.sharepoint.com/file?sharetoken=synthetic-secret',
                    'https://tenant.-invalid.sharepoint.com/file',
                    'https://synthetic.sharepoint.com/:b:/s/Team/secret', 'https://synthetic.sharepoint.com/file%0Aheader',
                    'https://synthetic.sharepoint.com/file?web=1&web=0', 'https://api.onedrive.com/private/download'):
            with self.subTest(url=url):
                self.problem(400, lambda: normalize_bridge_resource(resource(files=[{**FILE, 'url': url}]), SELECTION))

    def test_no_provider_tokens_raw_download_links_binary_or_graph_raw_objects_are_accepted(self):
        for key, value in (('access_token', 'synthetic-secret'), ('download_url', 'https://provider.invalid/private'),
                           ('@microsoft.graph.downloadUrl', 'https://provider.invalid/private'), ('content', 'BASE64')):
            with self.subTest(key=key):
                self.problem(400, lambda: normalize_bridge_snapshot(resource(files=[{**FILE, key: value}]), SELECTION))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(access_token='synthetic-secret')))
        self.problem(400, lambda: normalize_bridge_resource(resource(files=[{**FILE, 'eTag': FILE['rev']}]), SELECTION))
        self.problem(400, lambda: normalize_bridge_snapshot(resource(files=[{**FILE, 'url': None}]), SELECTION))

    def test_name_path_identity_and_id_controls_are_rejected_without_changing_original_text(self):
        for field, value in (('name', '../Plan.pdf'), ('name', 'nested\\Plan.pdf'), ('name', 'Plan\n.pdf'),
                             ('path', '/Projekt Ährenweg/../Plan.pdf'), ('path', '/Projekt Ährenweg//Plan.pdf'),
                             ('path', 'relative/Plan.pdf'), ('path', '/Projekt Ährenweg/Plan\x00.pdf'),
                             ('id', 'not an opaque id'), ('rev', 'tag\nwith-control')):
            with self.subTest(field=field, value=repr(value)):
                self.problem(400, lambda: normalize_bridge_snapshot(resource(files=[{**FILE, field: value}]), SELECTION))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(identity={'id': 'account', 'label': ' '})))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(identity={**IDENTITY, 'drives': []})))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(folders=[{**FOLDER, 'parent_id': FOLDER['id']}])))
        self.problem(400, lambda: normalize_bridge_resource(resource(), {**SELECTION, 'url': FILE['url']}))

    def test_file_sizes_and_mime_types_are_real_metadata_not_financial_or_preview_guesses(self):
        for value in (-1, True, 1.5, '12000', 2 ** 63):
            self.problem(400, lambda: normalize_bridge_resource(resource(files=[{**FILE, 'size': value}]), SELECTION))
        for value in ('', 'application', 'application/pdf; charset=utf-8', 'application/\npdf', 'x' * 101):
            self.problem(400, lambda: normalize_bridge_resource(resource(files=[{**FILE, 'media_type': value}]), SELECTION))
        # Opening the original in OneDrive is separate from Gmail's bounded PDF
        # preview; no 20 MiB binary-transfer cap is invented for metadata links.
        huge = {**FILE, 'size': 100 * 1024 * 1024 * 1024}
        self.assertEqual(normalize_bridge_snapshot(resource(files=[huge]), SELECTION)['files'][0]['size'], huge['size'])
        empty = {**FILE, 'size': 0}
        self.assertEqual(normalize_bridge_resource(resource(files=[empty]), SELECTION)['files'][0]['size'], 0)

    def test_item_counts_payload_bytes_and_malformed_json_values_are_bounded(self):
        folders = [{**FOLDER, 'id': 'folder-' + str(index)} for index in range(MAX_ITEMS)]
        self.assertEqual(len(normalize_bridge_catalog(catalog(folders=folders))['folders']), MAX_ITEMS)
        self.problem(400, lambda: normalize_bridge_catalog(catalog(folders=folders + [FOLDER])))
        files = [{**FILE, 'id': 'file-' + str(index)} for index in range(MAX_ITEMS)]
        self.assertEqual(len(normalize_bridge_snapshot(resource(files=files), SELECTION)['files']), MAX_ITEMS)
        self.problem(400, lambda: normalize_bridge_resource(resource(files=files + [FILE]), SELECTION))
        self.problem(413, lambda: normalize_bridge_catalog(catalog(identity={'id': 'account', 'label': 'x' * MAX_PAYLOAD_BYTES})))
        self.problem(400, lambda: normalize_bridge_resource(resource(files=[{**FILE, 'size': float('nan')}]), SELECTION))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(identity={'id': 'account', 'label': '\ud800'})))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(folders=b'not json')))

    def test_root_folder_paths_and_files_have_explicit_direct_parent_membership(self):
        folder = {**FOLDER, 'name': 'root', 'path': '/'}
        file = {**FILE, 'path': '/Grundriss Ährenweg.pdf'}
        normalized = normalize_bridge_resource(resource(folder=folder, files=[file]), SELECTION)
        self.assertEqual(normalized['files'][0]['parent_id'], FOLDER['id'])
        self.assertEqual(json.loads(json.dumps(normalized)), normalized)


if __name__ == '__main__':
    unittest.main(verbosity=2)
