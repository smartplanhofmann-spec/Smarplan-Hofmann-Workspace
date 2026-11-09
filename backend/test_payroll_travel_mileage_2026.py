"""Unreleased synthetic math fixtures for the explicit private-car contract.

These pure-kernel fixtures are not accepted database originals, payment
evidence or an external approval of the payroll software.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

from core import Problem, canonical
from payroll_travel_mileage_2026 import (calculate, DECLARATIONS, RATE_MINOR_PER_KM,
                                       RULE_VERSION, RULE_HASH, RULES, TABLE_HASH)


def ident(number):
    return format(number, '032x')


def reference(value):
    return {key: value[key] for key in ('id', 'revision', 'content_hash')}


def synthetic_site(number, kind, employee_id):
    return dict(id=ident(number), revision=1, content_hash=format(number, '064x'),
                employee_id=employee_id, status='active',
                details=dict(kind=kind, rate_id='de_2026', timezone='Europe/Berlin',
                             effective_from='2026-01-01', effective_to=None))


def unreleased_journey():
    employee_id = ident(1)
    home = synthetic_site(2, 'home', employee_id)
    workplace = synthetic_site(3, 'first_workplace', employee_id)
    external = synthetic_site(4, 'external_fixed', employee_id)
    files = [dict(id=ident(number), employee_id=employee_id, purpose='personnel',
                  sha256=hashlib.sha256(('Synthetic only ' + str(number)).encode()).hexdigest())
             for number in (5, 6)]
    details = dict(purpose='  Unreleased synthetic customer visit 🚗\r\n', project_id=None,
                   departed_at='2026-10-26T08:00:00+01:00', returned_at='2026-10-26T13:00:00+01:00',
                   timezone='Europe/Berlin', home_site_ref=reference(home),
                   first_workplace_ref=reference(workplace), source_file_ids=[value['id'] for value in files])
    mileage = dict(schema_version=1, vehicle_kind='private_car', vehicle_registration='SYNTHETISCH-1',
                   vehicle_file_id=files[0]['id'], declaration_file_id=files[1]['id'],
                   review_note='  Unreleased synthetic evidence, not a payment.\r\n',
                   **{key: True for key in DECLARATIONS})
    mileage['legs'] = [
        dict(id=ident(7), departed_at=details['departed_at'], arrived_at='2026-10-26T09:00:00+01:00',
             from_site_ref=reference(home), to_site_ref=reference(external), distance_m=50_000,
             evidence_file_id=files[1]['id']),
        dict(id=ident(8), departed_at='2026-10-26T12:00:00+01:00', arrived_at=details['returned_at'],
             from_site_ref=reference(external), to_site_ref=reference(home), distance_m=50_000,
             evidence_file_id=files[1]['id']),
    ]
    details['mileage'] = mileage
    trip = dict(id=ident(9), revision=1, content_hash='a' * 64, employee_id=employee_id,
                rule_version=RULE_VERSION, details=details, sources=dict(files=files))
    return trip, [home, workplace, external]


class MileageRulesTests(unittest.TestCase):
    def setUp(self):
        self.trip, self.sites = unreleased_journey()

    def result(self, **kwargs):
        return calculate([self.trip], self.sites, **kwargs)

    def invalid(self, trip=None, sites=None, **kwargs):
        with self.assertRaises(Problem) as caught:
            calculate([self.trip if trip is None else trip], self.sites if sites is None else sites, **kwargs)
        self.assertEqual(caught.exception.status, 400)

    def test_contract_exact_result_and_one_taxfree_payment_capacity(self):
        before = deepcopy((self.trip, self.sites))
        result = self.result()
        self.assertEqual(set(result), {'rule_version', 'rule_hash', 'table_hash', 'days', 'expense_items',
            'transport_sources', 'ground_calendar_sources', 'mixed_program_sources', 'mileage_items',
            'totals', 'blockers', 'payroll_required', 'can_approve', 'can_pay'})
        self.assertEqual(result['rule_version'], RULE_VERSION)
        self.assertEqual((result['rule_hash'], result['table_hash']), (RULE_HASH, TABLE_HASH))
        self.assertEqual(result['days'], [dict(date='2026-10-26', country='Deutschland', base_minor=0,
            meal_reduction_minor=0, meal_allowance_minor=0, lodging_allowance_minor=0,
            benefit_in_kind_minor=0, letter_m=False, mileage_allowance_minor=3000)])
        self.assertEqual(result['totals'], dict(meal_base_minor=0, meal_reduction_minor=0,
            meal_allowance_minor=0, lodging_allowance_minor=0, expense_allowance_minor=0,
            expense_already_paid_minor=0, requested_minor=3000, tax_free_minor=3000,
            flat_taxable_minor=0, individual_taxable_minor=0, benefit_in_kind_minor=0,
            already_paid_minor=0, remaining_minor=3000, overpaid_minor=0,
            mileage_distance_m=100_000, mileage_allowance_minor=3000))
        self.assertFalse(result['payroll_required'])
        self.assertTrue(result['can_approve']); self.assertTrue(result['can_pay'])
        for key in ('expense_items', 'transport_sources', 'ground_calendar_sources', 'mixed_program_sources', 'blockers'):
            self.assertEqual(result[key], [])
        self.assertEqual((self.trip, self.sites), before)
        for leg, actual in zip(self.trip['details']['mileage']['legs'], result['mileage_items']):
            self.assertEqual(actual, dict(trip_ref=reference(self.trip), leg_id=leg['id'],
                from_site_ref=leg['from_site_ref'], to_site_ref=leg['to_site_ref'], distance_m=50_000,
                rate_minor_per_km=30, evidence_file_id=ident(6),
                evidence_sha256=self.trip['sources']['files'][1]['sha256']))

    def test_published_rate_and_independent_once_only_half_up_vectors(self):
        self.assertEqual(RATE_MINOR_PER_KM, 30)
        # The expected values are independent Decimal results on the complete
        # route, including vectors whose separately rounded legs would differ.
        for distances, expected in [((1, 1), 0), ((5, 5), 0), ((8, 9), 1),
                ((17, 17), 1), ((25, 25), 2), ((49, 1), 2), ((500, 500), 30),
                ((10_001, 10_002), 600), ((2_000_000, 2_000_000), 120_000)]:
            with self.subTest(distances=distances):
                for leg, distance in zip(self.trip['details']['mileage']['legs'], distances):
                    leg['distance_m'] = distance
                independent = int((Decimal(sum(distances)) * Decimal('0.03')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                self.assertEqual(independent, expected)
                result = self.result()
                self.assertEqual(result['totals']['mileage_allowance_minor'], expected)
                self.assertEqual(result['totals']['requested_minor'], expected)
                self.assertEqual(result['can_pay'], expected > 0)

    def test_partial_full_payment_and_overpayment_never_add_money_twice(self):
        for paid, remaining, excess in ((1200, 1800, 0), (3000, 0, 0), (3100, 0, 100)):
            with self.subTest(paid=paid):
                result = self.result(already_paid_minor=paid)
                self.assertEqual(result['totals']['tax_free_minor'], 3000)
                self.assertEqual(result['totals']['remaining_minor'], remaining)
                self.assertEqual(result['totals']['overpaid_minor'], excess)
                self.assertEqual(result['can_pay'], remaining > 0)
                self.assertTrue(result['can_approve'])

    def test_six_unconfirmed_declarations_remain_explicit_nonpayable_drafts(self):
        for field in DECLARATIONS:
            with self.subTest(field=field):
                candidate = deepcopy(self.trip); candidate['details']['mileage'][field] = False
                result = calculate([candidate], self.sites)
                self.assertEqual(len(result['blockers']), 1)
                self.assertEqual(result['blockers'][0]['code'], 'mileage_' + field + '_missing')
                self.assertEqual(result['blockers'][0]['source_ref'], reference(candidate))
                self.assertFalse(result['can_approve']); self.assertFalse(result['can_pay'])
                self.assertEqual(result['totals']['mileage_allowance_minor'], 3000)
                for bad in (0, 1, 'true', None):
                    candidate['details']['mileage'][field] = bad; self.invalid(candidate)

    def test_unknown_fields_other_claims_and_other_rule_do_not_silently_default(self):
        for field, value in [('meals', []), ('requested_meal_minor', 1400), ('private_intervals', []), ('expense_refs', [])]:
            candidate = deepcopy(self.trip); candidate['details'][field] = value; self.invalid(candidate)
        for options in (dict(settlement_unit='combined_period'), dict(tax_choice='individual'),
                dict(requested_meal_minor=1), dict(requested_lodging_minor=1),
                dict(requested_meal_minor=None), dict(requested_lodging_minor=False),
                dict(already_paid_minor=True), dict(already_paid_minor=-1), dict(rule_version='de_travel_2026_v3')):
            with self.subTest(options=options): self.invalid(**options)
        candidate = deepcopy(self.trip); candidate['rule_version'] = 'de_travel_2026_v3'; self.invalid(candidate)
        for trips in ([], [self.trip, deepcopy(self.trip)], None):
            with self.assertRaises(Problem): calculate(trips, self.sites)

    def test_metres_must_be_whole_bounded_values_and_legs_unique(self):
        for value in (0, -1, 2_000_001, True, 12.5, '1000', None):
            candidate = deepcopy(self.trip); candidate['details']['mileage']['legs'][0]['distance_m'] = value
            with self.subTest(value=value): self.invalid(candidate)
        candidate = deepcopy(self.trip); legs = candidate['details']['mileage']['legs']; legs[1]['id'] = legs[0]['id']; self.invalid(candidate)
        for legs in ([], [self.trip['details']['mileage']['legs'][0]], [self.trip['details']['mileage']['legs'][0]] * 101):
            candidate = deepcopy(self.trip); candidate['details']['mileage']['legs'] = legs; self.invalid(candidate)

    def test_privately_borne_car_and_required_personnel_originals_are_bound(self):
        for vehicle in ('company_car', 'bicycle', None):
            candidate = deepcopy(self.trip); candidate['details']['mileage']['vehicle_kind'] = vehicle; self.invalid(candidate)
        for field in ('vehicle_file_id', 'declaration_file_id'):
            candidate = deepcopy(self.trip); candidate['details']['mileage'][field] = ident(99); self.invalid(candidate)
        candidate = deepcopy(self.trip); candidate['details']['mileage']['legs'][0]['evidence_file_id'] = ident(99); self.invalid(candidate)
        for field, value in (('employee_id', ident(99)), ('purpose', 'accounting'), ('sha256', 'bad')):
            candidate = deepcopy(self.trip); candidate['sources']['files'][0][field] = value; self.invalid(candidate)
        candidate = deepcopy(self.trip); candidate['sources']['files'].pop(); self.invalid(candidate)
        candidate = deepcopy(self.trip); candidate['details']['source_file_ids'] *= 2; self.invalid(candidate)

    def test_original_ref_employee_and_private_text_validation(self):
        for target, field, value in [('trip', 'employee_id', 'bad'), ('trip', 'revision', True), ('trip', 'content_hash', 'bad'),
                ('details', 'purpose', ''), ('details', 'purpose', '\ud800'), ('details', 'purpose', 'x' * 1001),
                ('mileage', 'schema_version', True), ('mileage', 'vehicle_registration', ' '),
                ('mileage', 'vehicle_registration', 'x' * 33), ('mileage', 'review_note', ''),
                ('mileage', 'review_note', '\ud800')]:
            candidate = deepcopy(self.trip)
            item = candidate if target == 'trip' else candidate['details'] if target == 'details' else candidate['details']['mileage']
            item[field] = value
            with self.subTest(target=target, field=field, value=repr(value)): self.invalid(candidate)
        candidate = deepcopy(self.trip); candidate['details']['home_site_ref']['revision'] = 2; self.invalid(candidate)

    def test_sites_must_match_person_original_domestic_kind_and_valid_date(self):
        for field, value in (('employee_id', ident(99)), ('status', 'void'), ('revision', 2)):
            sites = deepcopy(self.sites); sites[2][field] = value; self.invalid(sites=sites)
        for field, value in (('kind', 'mobile'), ('kind', 'wide_area'), ('kind', 'home'), ('rate_id', 'tr2026_001'),
                ('timezone', 'Europe/Paris'), ('effective_from', '2026-10-27'), ('effective_to', '2026-10-25')):
            sites = deepcopy(self.sites); sites[2]['details'][field] = value
            with self.subTest(field=field, value=value): self.invalid(sites=sites)
        self.invalid(sites=self.sites + [deepcopy(self.sites[0])])

    def test_closed_route_from_first_workplace_is_supported_without_commute(self):
        legs = self.trip['details']['mileage']['legs']
        legs[0]['from_site_ref'] = reference(self.sites[1]); legs[1]['to_site_ref'] = reference(self.sites[1])
        self.assertTrue(self.result()['can_approve'])
        self.assertEqual(self.result()['totals']['tax_free_minor'], 3000)

    def test_commute_open_journey_base_detour_and_broken_route_are_rejected(self):
        candidate = deepcopy(self.trip); candidate['details']['mileage']['legs'][0]['to_site_ref'] = reference(self.sites[1]); self.invalid(candidate)
        candidate = deepcopy(self.trip); candidate['details']['mileage']['legs'][1]['to_site_ref'] = reference(self.sites[1]); self.invalid(candidate)
        candidate = deepcopy(self.trip); candidate['details']['mileage']['legs'][1]['from_site_ref'] = reference(self.sites[0]); self.invalid(candidate)
        candidate = deepcopy(self.trip); candidate['details']['mileage']['legs'][0]['from_site_ref'] = reference(self.sites[2]); self.invalid(candidate)

    def test_multiple_external_stops_preserve_route_and_round_once(self):
        other = synthetic_site(10, 'external_fixed', self.trip['employee_id']); self.sites.append(other)
        legs = self.trip['details']['mileage']['legs']
        legs.insert(1, dict(id=ident(11), departed_at='2026-10-26T10:00:00+01:00',
            arrived_at='2026-10-26T11:00:00+01:00', from_site_ref=reference(self.sites[2]),
            to_site_ref=reference(other), distance_m=17, evidence_file_id=ident(6)))
        legs[-1]['from_site_ref'] = reference(other)
        for leg in legs: leg['distance_m'] = 17
        result = self.result(); self.assertEqual(result['totals']['mileage_distance_m'], 51)
        self.assertEqual(result['totals']['mileage_allowance_minor'], 2)
        self.assertEqual([row['leg_id'] for row in result['mileage_items']], [leg['id'] for leg in legs])

    def test_time_coverage_overlap_cross_day_year_and_wrong_berlin_offset(self):
        for field, value in (('departed_at', '2026-10-26T07:00:00+01:00'),
                ('returned_at', '2026-10-26T14:00:00+01:00'),
                ('returned_at', '2026-10-27T00:00:00+01:00'),
                ('departed_at', '2026-10-26T08:00:00+02:00'), ('timezone', 'UTC')):
            candidate = deepcopy(self.trip); candidate['details'][field] = value
            with self.subTest(field=field, value=value): self.invalid(candidate)
        for field, value in (('departed_at', '2026-10-26T08:30:00+01:00'),
                ('arrived_at', '2026-10-26T08:00:00+01:00')):
            candidate = deepcopy(self.trip); candidate['details']['mileage']['legs'][0][field] = value; self.invalid(candidate)
        candidate = deepcopy(self.trip); candidate['details']['mileage']['legs'][1]['departed_at'] = '2026-10-26T08:59:00+01:00'; self.invalid(candidate)
        for year in ('2025', '2027'):
            candidate = deepcopy(self.trip)
            for item in [candidate['details'], *candidate['details']['mileage']['legs']]:
                for key in ('departed_at', 'returned_at', 'arrived_at'):
                    if key in item: item[key] = year + item[key][4:]
            self.invalid(candidate)

    def test_dst_gap_rejected_fold_valid_only_with_actual_berlin_offsets(self):
        candidate = deepcopy(self.trip)
        candidate['details']['departed_at'] = '2026-03-29T02:30:00+01:00'
        candidate['details']['returned_at'] = '2026-03-29T05:00:00+02:00'
        self.invalid(candidate)
        candidate, sites = unreleased_journey()
        d = candidate['details']; legs = d['mileage']['legs']
        d['departed_at'] = legs[0]['departed_at'] = '2026-10-25T02:15:00+02:00'
        legs[0]['arrived_at'] = '2026-10-25T02:30:00+02:00'
        legs[1]['departed_at'] = '2026-10-25T02:30:00+01:00'
        d['returned_at'] = legs[1]['arrived_at'] = '2026-10-25T02:45:00+01:00'
        self.assertTrue(calculate([candidate], sites)['can_approve'])

    def test_history_not_added_and_result_references_do_not_mutate_sources(self):
        history = deepcopy(self.trip); history['details']['mileage']['legs'][0]['distance_m'] = 2_000_000
        result = self.result(history_trips=[history])
        self.assertEqual(result['totals']['mileage_distance_m'], 100_000)
        result['mileage_items'][0]['from_site_ref']['id'] = ident(99)
        self.assertEqual(self.trip['details']['mileage']['legs'][0]['from_site_ref']['id'], ident(2))

    def test_rule_provenance_and_real_crlf_copy_are_portable(self):
        self.assertEqual(RULE_HASH, hashlib.sha256(canonical(RULES).encode()).hexdigest())
        source = Path(__file__).with_name('payroll_travel_mileage_2026.py')
        raw = source.read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(RULES['module_sha256'], hashlib.sha256(raw).hexdigest())
        with tempfile.TemporaryDirectory(prefix='unreleased-mileage-crlf-') as directory:
            copied = Path(directory) / source.name; copied.write_bytes(raw.replace(b'\n', b'\r\n'))
            spec = importlib.util.spec_from_file_location('unreleased_mileage_crlf_copy', copied)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            self.assertEqual(module.RULE_HASH, RULE_HASH)
            self.assertEqual(module.calculate([self.trip], self.sites), self.result())


if __name__ == '__main__':
    unittest.main()
