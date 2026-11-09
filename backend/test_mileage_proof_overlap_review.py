"""Independent actual-original overlap review; no simulated claims or payments."""
from copy import deepcopy
import base64
import unittest

from core import Problem, canonical
from business_travel_allowances import _ref
from test_business_planning import rid
from test_business_travel_mileage import MileageFixture


class MileageProofOverlapReview(unittest.TestCase):
    def setUp(self):
        self.x = MileageFixture(self)
        self.f = self.x.f
        self.api = self.x.api
        self.x.submitted()
        self.original = self.x.approval()

    def assert_rejected(self, actor, command, day):
        draft = self.api.save_trip(actor, command)['result']
        trip = self.api.trip_action(actor, draft['id'], 'submit', dict(
            request_id=rid(), employee_id=command['employee_id'], revision=1,
            source_hash=self.api._basis(command['employee_id']), confirmed=True))['result']
        proposal = dict(self.x.preview_input, employee_id=command['employee_id'],
            trip_refs=[_ref(trip)], period_from=day, period_to=day)
        preview = self.api.preview(self.f.owner, proposal)
        accepted = dict(proposal, id=rid(), request_id=rid(), revision=0,
            source_hash=preview['source_hash'], preview_hash=preview['preview_hash'], confirmed=True)
        try:
            self.api.approve(self.f.owner, accepted)
        except Problem as error:
            self.assertEqual(error.status, 409)
        else:
            self.fail('The real domain accepted a second settlement containing an already claimed original plus a different second proof')
        self.assertFalse(preview['can_approve'])
        blocker = next(x for x in preview['blockers'] if x['code'] == 'mileage_original_already_settled')
        self.assertIsNone(blocker['source_ref'])
        self.assertEqual(self.f.office.db.execute(
            'SELECT COUNT(*) FROM business_travel_settlements').fetchone()[0], 1)
        self.assertEqual(self.f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0], 0)
        return preview

    def test_extra_route_proof_cannot_release_used_original_on_another_day(self):
        extra = self.f.upload(visible=True, marker=b'Different original for a second route leg')
        command = deepcopy(self.x.input)
        command.update(request_id=rid(), id=rid())
        details = command['details']
        details['source_file_ids'].append(extra['id'])
        for field in ('departed_at', 'returned_at'):
            details[field] = details[field].replace('2026-10-26', '2026-10-27')
        for leg in details['mileage']['legs']:
            leg['id'] = rid()
            for field in ('departed_at', 'arrived_at'):
                leg[field] = leg[field].replace('2026-10-26', '2026-10-27')
        details['mileage']['legs'][1]['evidence_file_id'] = extra['id']
        self.assert_rejected(self.f.technician, command, '2026-10-27')

    def test_extra_route_proof_cannot_release_copied_original_for_another_person(self):
        f = self.f
        user = f.office.add_user('overlap-review@example.test', 'Synthetic-overlap-review-123', 'technician')
        actor = f.office.user(f.office.login('overlap-review@example.test', 'Synthetic-overlap-review-123'))
        f.office.assign(f.owner, f.project, user)
        employee = f.planning.save_employee(f.owner, dict(request_id=rid(), user_id=user,
            name='Synthetic overlap review employee', weekly_minutes=1200,
            hourly_cost_minor=2000, employment_from='2026-01-01', employment_to=None))
        copied = []
        for original in (self.x.vehicle, self.x.evidence):
            raw = f.hr.file_content(f.owner, original['id'])[0]
            copied.append(f.hr.upload(f.owner, dict(request_id=rid(), employee_id=employee['id'],
                purpose='personnel', owner_visible=True, filename=original['filename'],
                media_type=original['media_type'], content_base64=base64.b64encode(raw).decode())))
        extra = f.hr.upload(f.owner, dict(request_id=rid(), employee_id=employee['id'],
            purpose='personnel', owner_visible=True, filename='extra-route.pdf', media_type='application/pdf',
            content_base64=base64.b64encode(b'%PDF-1.4\nDifferent actual route original\n%%EOF').decode()))
        sites = []
        for original in (f.home, f.place):
            sites.append(f.api.save_site(f.owner, dict(request_id=rid(), employee_id=employee['id'],
                id=rid(), revision=0, status='active', correction_reason='',
                details=dict(original['details'], source_file_ids=[copied[1]['id']])))['result'])
        command = deepcopy(self.x.input)
        command.update(request_id=rid(), id=rid(), employee_id=employee['id'])
        command['details'].update(home_site_ref=_ref(sites[0]), source_file_ids=[x['id'] for x in copied] + [extra['id']])
        mileage = command['details']['mileage']
        mileage.update(vehicle_file_id=copied[0]['id'], declaration_file_id=copied[1]['id'])
        for index, leg in enumerate(mileage['legs']):
            leg.update(id=rid(), from_site_ref=_ref(sites[index]), to_site_ref=_ref(sites[1-index]),
                evidence_file_id=copied[1]['id'] if index == 0 else extra['id'])
        preview = self.assert_rejected(actor, command, '2026-10-26')
        self.assertNotIn(self.x.f.employee['id'], canonical(preview))


if __name__ == '__main__':
    unittest.main()
