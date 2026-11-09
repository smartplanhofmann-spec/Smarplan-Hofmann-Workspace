"""Actual prior-code bundle originals stay unchanged and reserve each part."""
import base64
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from core import Office,Problem
from business_travel_allowances import _ref,validate_integrity
from business_travel_mileage import MileageTravel
from test_business_planning import rid
from travel_allowance_cash import record_payment


class MileageLegacyBundleOriginals(unittest.TestCase):
    def test_actual_old_two_original_bundle_replays_and_blocks_a_partial_overlap(self):
        root=Path(__file__).resolve().parent/'testdata'
        original=json.loads((root/'mileage_legacy_bundle.json').read_text())
        with tempfile.TemporaryDirectory(prefix='synthetic-mileage-old-bundle-review-') as directory:
            path=Path(directory)/'original.sqlite3'
            path.write_bytes(gzip.decompress((root/'mileage_legacy_bundle.sqlite3.gz').read_bytes()))
            office=Office(path)
            try:
                api=MileageTravel(office);actor=original['actor'];employee_actor=original['employee_actor']
                self.assertTrue(validate_integrity(office))
                self.assertEqual(api.approve(actor,original['settlement_command']),original['receipt'])
                self.assertEqual(record_payment(api,actor,original['payment_command']),original['payment'])
                self.assertEqual(api.export(actor,original['settlement']['id'],1,'pdf')[0],base64.b64decode(original['pdf_base64']))
                before=[dict(r) for r in office.db.execute('SELECT * FROM business_travel_claims ORDER BY claim_key')]
                self.assertEqual(before,original['claims'])
                self.assertEqual(len(before),2)
                self.assertEqual({r['source_kind'] for r in before},{'employee_day','mileage'})
                extra=api.hr.upload(actor,dict(request_id=rid(),employee_id=original['employee']['id'],purpose='personnel',
                    owner_visible=True,filename='new-other-route-original.pdf',media_type='application/pdf',
                    content_base64=base64.b64encode(b'%PDF-1.4\nActual different route original Z\n%%EOF').decode()))
                command=deepcopy(original['trip_command']);command.update(request_id=rid(),id=rid(),revision=0)
                d=command['details'];d['source_file_ids'].append(extra['id'])
                d['mileage']['legs'][1]['evidence_file_id']=extra['id']
                for k in ('departed_at','returned_at'):d[k]=d[k].replace('2026-10-26','2026-10-27')
                for leg in d['mileage']['legs']:
                    leg['id']=rid()
                    for k in ('departed_at','arrived_at'):leg[k]=leg[k].replace('2026-10-26','2026-10-27')
                draft=api.save_trip(employee_actor,command)['result']
                trip=api.trip_action(employee_actor,draft['id'],'submit',dict(request_id=rid(),employee_id=original['employee']['id'],
                    revision=1,source_hash=api._basis(original['employee']['id']),confirmed=True))['result']
                proposal={k:v for k,v in original['settlement_command'].items() if k not in ('id','request_id','revision','source_hash','preview_hash','confirmed')}
                proposal.update(trip_refs=[_ref(trip)],period_from='2026-10-27',period_to='2026-10-27')
                preview=api.preview(actor,proposal)
                self.assertFalse(preview['can_approve'])
                self.assertIsNone(next(v for v in preview['blockers'] if v['code']=='mileage_original_already_settled')['source_ref'])
                with self.assertRaises(Problem) as error:
                    api.approve(actor,dict(proposal,id=rid(),request_id=rid(),revision=0,source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],confirmed=True))
                self.assertEqual(error.exception.status,409)
                self.assertEqual([dict(r) for r in office.db.execute('SELECT * FROM business_travel_claims ORDER BY claim_key')],before)
                self.assertEqual(office.db.execute('SELECT COUNT(*) FROM business_travel_settlements').fetchone()[0],1)
                self.assertTrue(validate_integrity(office))
                old_trip=original['settlement']['sources']['trips'][0]
                rejected=api.trip_action(actor,old_trip['id'],'reject',dict(request_id=rid(),employee_id=original['employee']['id'],
                    revision=old_trip['revision'],source_hash=api._basis(original['employee']['id']),confirmed=True,
                    reason='Independent correction of the previously archived route'))['result']
                correction=deepcopy(original['trip_command']);correction.update(request_id=rid(),revision=rejected['revision'],
                    correction_reason='Actual shorter route within the same original settlement identity')
                for leg in correction['details']['mileage']['legs']:leg['distance_m']=25000
                draft=api.save_trip(employee_actor,correction)['result']
                trip=api.trip_action(employee_actor,draft['id'],'submit',dict(request_id=rid(),employee_id=original['employee']['id'],
                    revision=draft['revision'],source_hash=api._basis(original['employee']['id']),confirmed=True))['result']
                proposal={k:v for k,v in original['settlement_command'].items() if k not in ('id','request_id','revision','source_hash','preview_hash','confirmed')}
                proposal.update(trip_refs=[_ref(trip)],correction_of=_ref(original['settlement']))
                preview=api.preview(actor,proposal);self.assertTrue(preview['can_approve'])
                self.assertEqual(preview['totals']['overpaid_minor'],1500)
                current=api.approve(actor,dict(proposal,id=original['settlement']['id'],request_id=rid(),revision=1,
                    source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],confirmed=True))['result']
                self.assertEqual(current['revision'],2)
                self.assertEqual([dict(r) for r in office.db.execute('SELECT * FROM business_travel_claims WHERE revision=1 ORDER BY claim_key')],before)
                new_rows=[dict(r) for r in office.db.execute('SELECT * FROM business_travel_claims WHERE revision=2')]
                self.assertEqual(len(new_rows),3)
                self.assertEqual(sum(r['source_kind']=='mileage_original' for r in new_rows),2)
                self.assertEqual(api.approve(actor,original['settlement_command']),original['receipt'])
                self.assertEqual(record_payment(api,actor,original['payment_command']),original['payment'])
                self.assertTrue(validate_integrity(office))
            finally:office.db.close()


if __name__=='__main__':unittest.main()
