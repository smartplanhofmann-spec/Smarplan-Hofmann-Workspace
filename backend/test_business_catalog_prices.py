"""Own dated CSV-v2 behavior: synthetic files and real canonical articles."""
import base64
from datetime import datetime, timezone
import json
import sqlite3
import unittest
import uuid

from core import Problem
from business_tests.test_documents import DocumentsFixture
from business_documents import Documents
import business_catalog_prices as prices


def request(**values):
    return dict(request_id=uuid.uuid4().hex, **values)


def raw(*rows):
    return (';'.join(prices.FIELDS) + '\n' + '\n'.join(';'.join(row) for row in rows) + '\n').encode()


def row(price_id='nov', code='SYN-PRICE', role='sales_net', amount='10.00', start='2026-11-01', end='2026-11-30', basis='1', unit='ST'):
    return (price_id, code, 'Synthetic dated item', unit, role, amount, basis, 'EUR', '19', start, end)


class CatalogPricesTests(DocumentsFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        for statement in prices.schema_statements('BLOB') + prices.guard_statements('sqlite'):
            self.office.db.execute(statement)
        self.service = prices.CatalogPrices(self.office, clock=lambda: datetime(2026, 11, 4, tzinfo=timezone.utc))
        self.source = self.service.create_source(self.owner, request(name='Synthetic source', reference='SYNTHETIC'))
        self.sequence = 0

    def stage(self, original=None):
        self.sequence += 1
        return self.service.stage(self.owner, self.source['id'], request(catalog_revision='SYN-' + str(self.sequence),
            filename='synthetic-v2.csv', content_base64=base64.b64encode(original or raw(row())).decode()))

    def choices(self, staged, replacements=None):
        bindings = {}
        detail = self.service.detail(self.owner, staged['id'])
        for code in {line['code'] for line in staged['rows']}:
            prior = detail['bindings'].get(code)
            bindings[code] = dict(action='bind' if prior else 'create', article_id=prior['article']['id'] if prior else None,
                article_revision=prior['article']['revision'] if prior else None, expected_binding_revision=prior['binding_revision'] if prior else 0,
                confirm_name_difference=False)
        return dict(expected_source_version=detail['current_source_version'], bindings=bindings, replacements=replacements or {})

    def accept(self, staged, decisions=None):
        decisions = decisions or self.choices(staged)
        checked = self.service.preview(self.owner, staged['id'], decisions)
        command = request(**decisions, preview_sha256=checked['preview_sha256'], confirmation=True)
        return self.service.apply(self.owner, staged['id'], command), command

    def problem(self, status, fn, *args):
        with self.assertRaises(Problem) as raised:
            fn(*args)
        self.assertEqual(raised.exception.status, status)

    def test_parser_requires_explicit_role_dates_unit_and_exact_price_basis(self):
        value = prices.parse_catalog(raw(row(amount='1.00', basis='3')))[0]
        self.assertEqual((value['price_net'], value['price_base_quantity']), ('1.00', '3'))
        self.assertIsNone(prices.parse_catalog(raw(row(end='')))[0]['valid_until'])
        for original in (raw(row(start='')), raw(row(start='2026-04-31')), raw(row(start='2026-12-01')), raw(row(role='net')),
                         raw(row(amount='')), raw(row(amount='-1')), raw(row(basis='0')), raw(row(), row()), raw(row(unit='X'*21))):
            self.problem(400, prices.parse_catalog, original)
        self.problem(413, prices.parse_catalog, b'x' * (prices.MAX_BYTES + 1))
        self.assertEqual(prices.parse_catalog(raw(row(amount='0')))[0]['price_net'], '0')

    def test_equal_friendly_source_names_remain_distinguishable_by_their_declared_reference(self):
        first,_=self.accept(self.stage());article_id=first['bindings'][0]['article_id']
        original=prices.resolve_selection(self.office,self.owner,article_id,self.selection(first),'sales_net')
        self.source=self.service.create_source(self.owner,request(name='Synthetic source',reference='SYNTHETIC-SECOND'))
        staged=self.stage();choices=self.choices(staged)
        choices['bindings']['SYN-PRICE'].update(action='bind',article_id=article_id,article_revision=1)
        self.accept(staged,choices)
        candidates=self.service.candidates(self.owner,dict(article_id=article_id,price_role='sales_net',effective_on='2026-11-04'))['items']
        self.assertEqual({item['source_name'] for item in candidates},{'Synthetic source'})
        self.assertEqual({item['source_reference'] for item in candidates},{'SYNTHETIC','SYNTHETIC-SECOND'})
        self.assertEqual(len({item['source_id'] for item in candidates}),2)
        self.assertEqual(prices.validate_snapshot(self.office,original),original)

    def test_readonly_preview_does_not_create_articles_and_apply_freezes_original_and_two_periods(self):
        original = raw(row(), row(price_id='dec', amount='12.00', start='2026-12-01', end=''))
        staged = self.stage(original)
        before = {table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                  for table in (*prices.TABLES, 'business_articles', 'business_article_versions', 'audit')}
        decisions = self.choices(staged)
        checked = self.service.preview(self.owner, staged['id'], decisions)
        for table, count in before.items():
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], count)
        self.assertEqual([line['action'] for line in checked['rows']], ['create', 'create'])
        accepted, command = self.accept(staged, decisions)
        self.assertEqual(self.service.apply(self.owner, staged['id'], command), accepted)
        self.assertEqual(self.service.original(self.owner, staged['id'])[0], original)
        self.assertEqual(self.service.history(self.owner, self.source['id'], {})['total'], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_catalog_price_events').fetchone()[0], 2)
        article = Documents(self.office).catalog_item(self.owner, 'business_articles', accepted['bindings'][0]['article_id'])
        self.assertEqual((article['cost_price_net'], article['unit_price_net'], article['cost_known']), ('0', '0', False))
        self.assertTrue(prices.article_managed(self.office, article['id']))

    def test_overlap_cannot_replace_open_price_without_explicit_correction(self):
        first, _ = self.accept(self.stage(raw(row(end=''))))
        conflicting = self.stage(raw(row(price_id='dec', amount='12', start='2026-12-01', end='')))
        self.problem(409, self.service.preview, self.owner, conflicting['id'], self.choices(conflicting))
        corrective = self.stage(raw(row(end='2026-11-30'), row(price_id='dec', amount='12', start='2026-12-01', end='')))
        previous = first['prices'][0]
        choices = self.choices(corrective, {'nov': {'revision': previous['revision'], 'sha256': previous['sha256']}})
        accepted, _ = self.accept(corrective, choices)
        self.assertEqual([item['revision'] for item in accepted['prices']], [2, 1])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_catalog_price_events').fetchone()[0], 3)
        old = self.office.db.execute('SELECT payload_json FROM business_catalog_price_events WHERE id=? AND revision=1', (previous['price_id'],)).fetchone()
        self.assertIsNone(json.loads(old['payload_json'])['price']['valid_until'])

    def test_identical_new_catalog_keeps_price_identity_and_manual_article_values(self):
        first, _ = self.accept(self.stage())
        article_id = first['bindings'][0]['article_id']
        article = Documents(self.office).catalog_item(self.owner, 'business_articles', article_id)
        Documents(self.office).save_article(self.owner, request(revision=article['revision'], name='Manually clarified name', unit_price_net='99'), article_id)
        second = self.stage()
        decisions = self.choices(second)
        self.problem(409, self.service.preview, self.owner, second['id'], decisions)
        decisions['bindings']['SYN-PRICE']['confirm_name_difference'] = True
        checked = self.service.preview(self.owner, second['id'], decisions)
        self.assertEqual(checked['rows'][0]['action'], 'unchanged')
        accepted, _ = self.accept(second, decisions)
        self.assertEqual(accepted['prices'], first['prices'])
        self.assertEqual(Documents(self.office).catalog_item(self.owner, 'business_articles', article_id)['unit_price_net'], '99')

    def test_stale_preview_rejected_then_same_original_can_be_explicitly_rechecked(self):
        staged = self.stage()
        decisions = self.choices(staged)
        checked = self.service.preview(self.owner, staged['id'], decisions)
        other = self.stage(raw(row(code='SYN-OTHER', price_id='other')))
        self.accept(other)
        body = request(**decisions, preview_sha256=checked['preview_sha256'], confirmation=True)
        self.problem(409, self.service.apply, self.owner, staged['id'], body)
        fresh = self.choices(staged)
        accepted, _ = self.accept(staged, fresh)
        self.assertEqual(accepted['original_sha256'], staged['original']['sha256'])

    def test_immutable_price_and_binding_rows_and_changed_source_revision_are_rejected(self):
        staged = self.stage()
        accepted, _ = self.accept(staged)
        for table in prices.TABLES:
            with self.assertRaises(sqlite3.IntegrityError):
                self.office.db.execute('DELETE FROM ' + table)
        self.problem(409, self.service.stage, self.owner, self.source['id'], request(catalog_revision=staged['catalog_revision'], filename='synthetic-v2.csv', content_base64=base64.b64encode(raw(row(amount='11'))).decode()))
        self.assertEqual(self.service.detail(self.owner, staged['id'])['application'], accepted)

    def selection(self, accepted, index=0, day='2026-11-04'):
        proof = accepted['prices'][index]
        return dict(price_id=proof['price_id'], price_revision=proof['revision'], price_sha256=proof['sha256'], effective_on=day)

    def test_date_boundaries_gap_and_roles_never_choose_another_price(self):
        accepted, _ = self.accept(self.stage(raw(row(end='2026-11-29'), row(price_id='dec', amount='12', start='2026-12-01', end=''),
                                                   row(price_id='purchase', role='purchase_net', amount='1', basis='3'))))
        article_id = accepted['bindings'][0]['article_id']
        for day in ('2026-11-01','2026-11-29'):
            snapshot = prices.resolve_selection(self.office,self.owner,article_id,self.selection(accepted,day=day),'sales_net')
            self.assertEqual(snapshot['price']['price_net'],'10.00')
        for day in ('2026-10-31','2026-11-30','2026-12-01'):
            self.problem(409,prices.resolve_selection,self.office,self.owner,article_id,self.selection(accepted,day=day),'sales_net')
        result = self.service.candidates(self.owner,dict(article_id=article_id,price_role='sales_net',effective_on='2026-11-30'))
        self.assertEqual([item['status'] for item in sorted(result['items'],key=lambda item:item['price']['valid_from'])],['expired','not_yet_valid'])
        self.assertEqual(prices.resolve_selection(self.office,self.owner,article_id,self.selection(accepted,1,'2026-12-01'),'sales_net')['price']['price_net'],'12')
        self.problem(409,prices.resolve_selection,self.office,self.owner,article_id,self.selection(accepted,2),'sales_net')
        cost = prices.resolve_selection(self.office,self.owner,article_id,self.selection(accepted,2),'purchase_net')
        self.assertEqual((cost['price']['price_net'],cost['price']['price_base_quantity']),('1','3'))
        prices.validate_integrity(self.office)

    def test_withdrawal_stales_new_selection_but_preserves_historical_snapshot_and_exact_replay(self):
        accepted, _ = self.accept(self.stage())
        article_id = accepted['bindings'][0]['article_id']
        selected = self.selection(accepted)
        original = prices.resolve_selection(self.office,self.owner,article_id,selected,'sales_net')
        body = request(revision=1,sha256=selected['price_sha256'],reason='Synthetic withdrawn source',confirmation=True)
        result = self.service.withdraw(self.owner,selected['price_id'],body)
        self.assertEqual(self.service.withdraw(self.owner,selected['price_id'],body),result)
        self.problem(409,prices.resolve_selection,self.office,self.owner,article_id,selected,'sales_net')
        self.assertEqual(prices.validate_snapshot(self.office,original,article_id,'sales_net'),original)
        self.assertEqual(self.service.candidates(self.owner,dict(article_id=article_id,price_role='sales_net',effective_on='2026-11-04'))['items'][0]['status'],'withdrawn')
        self.assertEqual(len(self.service.price_history(self.owner,selected['price_id'])['items']),2)
        prices.validate_integrity(self.office)

    def test_correction_stales_old_choice_and_cannot_mutate_old_snapshot(self):
        accepted, _ = self.accept(self.stage())
        article_id = accepted['bindings'][0]['article_id']
        selected = self.selection(accepted)
        original = prices.resolve_selection(self.office,self.owner,article_id,selected,'sales_net')
        staged = self.stage(raw(row(amount='11')))
        corrected, _ = self.accept(staged,self.choices(staged,{'nov':dict(revision=1,sha256=selected['price_sha256'])}))
        self.problem(409,prices.resolve_selection,self.office,self.owner,article_id,selected,'sales_net')
        self.assertEqual(prices.resolve_selection(self.office,self.owner,article_id,self.selection(corrected),'sales_net')['price']['price_net'],'11')
        self.assertEqual(prices.validate_snapshot(self.office,original)['price']['price_net'],'10.00')
        modified = json.loads(json.dumps(original)); modified['price']['price_net']='0'
        modified['snapshot_sha256']=prices.sha({key:value for key,value in modified.items() if key!='snapshot_sha256'})
        self.problem(409,prices.validate_snapshot,self.office,modified)
        prices.validate_integrity(self.office)

    def test_explicit_new_article_binding_retires_old_future_selection_without_rewriting_facts(self):
        accepted, _ = self.accept(self.stage())
        article_id = accepted['bindings'][0]['article_id']
        original = prices.resolve_selection(self.office,self.owner,article_id,self.selection(accepted),'sales_net')
        staged = self.stage(raw(row(price_id='metres',unit='m')))
        choices = self.choices(staged)
        self.problem(409,self.service.preview,self.owner,staged['id'],choices)
        choices['bindings']['SYN-PRICE'].update(action='create',article_id=None,article_revision=None)
        newer, _ = self.accept(staged,choices)
        self.assertNotEqual(newer['bindings'][0]['article_id'],article_id)
        self.problem(409,prices.resolve_selection,self.office,self.owner,article_id,self.selection(accepted),'sales_net')
        self.assertEqual(prices.validate_snapshot(self.office,original),original)
        self.assertTrue(prices.article_managed(self.office,article_id))
        prices.validate_integrity(self.office)

    def test_inclusive_overlap_and_wrong_article_fail_before_mutation(self):
        accepted, _ = self.accept(self.stage())
        staged = self.stage(raw(row(price_id='overlap',start='2026-11-30',end='2026-12-30')))
        self.problem(409,self.service.preview,self.owner,staged['id'],self.choices(staged))
        other = Documents(self.office).save_article(self.owner,request(name='Other',unit='ST',kind='material',unit_price_net='99'))
        self.problem(409,prices.resolve_selection,self.office,self.owner,other['id'],self.selection(accepted),'sales_net')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_catalog_price_events').fetchone()[0],1)

    def test_every_price_row_is_checked_against_document_amount_limit_before_any_acceptance(self):
        staged=self.stage(raw(row(amount='9999999999999'),row(price_id='later',start='2026-12-01',end='',amount='1')))
        before=self.office.db.execute('SELECT COUNT(*) FROM business_articles').fetchone()[0]
        self.problem(400,self.service.preview,self.owner,staged['id'],self.choices(staged))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_articles').fetchone()[0],before)

    def test_server_preview_identifies_required_correction_without_mutating_or_accepting_it(self):
        first,_=self.accept(self.stage())
        staged=self.stage(raw(row(amount='11')))
        choices=self.choices(staged)
        before=self.office.db.total_changes
        checked=self.service.preview(self.owner,staged['id'],choices)
        self.assertFalse(checked['ready'])
        self.assertEqual(checked['required_replacements'],[dict(external_price_id='nov',revision=1,sha256=first['prices'][0]['sha256'])])
        self.assertEqual(self.office.db.total_changes,before)
        self.problem(409,self.service.apply,self.owner,staged['id'],request(**choices,preview_sha256=checked['preview_sha256'],confirmation=True))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_catalog_price_events').fetchone()[0],1)

    def test_current_article_unit_change_blocks_new_selection_but_not_older_snapshot(self):
        accepted, _ = self.accept(self.stage())
        article_id = accepted['bindings'][0]['article_id']
        original = prices.resolve_selection(self.office,self.owner,article_id,self.selection(accepted),'sales_net')
        Documents(self.office).save_article(self.owner,request(revision=1,unit='m'),article_id)
        self.problem(409,prices.resolve_selection,self.office,self.owner,article_id,self.selection(accepted),'sales_net')
        self.assertEqual(prices.validate_snapshot(self.office,original),original)
        prices.validate_integrity(self.office)


if __name__ == '__main__':
    unittest.main()
