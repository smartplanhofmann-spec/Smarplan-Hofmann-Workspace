#!/usr/bin/env python3
"""Independent reference arithmetic; no product modules, DB, network or tax filing.

All amounts are integer cents. Legal assumptions and scope are in the companion
source review. Decimal cumulative rounding is a chosen technical convention, not
an asserted statutory rounding prescription. Run here to regenerate the JSON.
"""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json


def split(original_gross, original_tax, payments):
    assert original_gross > 0 and 0 <= original_tax <= original_gross
    paid = tax_used = 0
    results = []
    for gross in payments:
        assert 0 < gross <= original_gross - paid
        paid += gross
        target_tax = int((Decimal(paid) * Decimal(original_tax)
                          / Decimal(original_gross)).quantize(
                              Decimal(1), rounding=ROUND_HALF_UP))
        tax = target_tax - tax_used
        net = gross - tax
        assert net >= 0 and tax >= 0 and net + tax == gross
        results.append(dict(net=net, tax=tax, gross=gross))
        tax_used = target_tax
    remaining = dict(net=original_gross - original_tax - (paid - tax_used),
                     tax=original_tax - tax_used, gross=original_gross - paid)
    assert sum(row['net'] for row in results) + remaining['net'] == original_gross - original_tax
    assert sum(row['tax'] for row in results) + remaining['tax'] == original_tax
    assert sum(row['gross'] for row in results) + remaining['gross'] == original_gross
    return results, remaining


def effect(row, direction):
    assert direction in ('receivable', 'payable_prior_full_input_vat')
    sign = 1 if direction == 'receivable' else -1
    return dict(cash=sign * row['gross'], euer_net=sign * row['net'],
                euer_vat=sign * row['tax'],
                new_output_vat=row['tax'] if sign == 1 else 0, new_input_vat=0)


def main():
    cases = []
    rows, rest = split(119000, 19000, [59500, 59500])
    assert rows == [dict(net=50000, tax=9500, gross=59500)] * 2
    assert rest == dict(net=0, tax=0, gross=0)
    cases.append(dict(id='F01', periods=['2026-11', '2027-02'],
                      payments=[effect(row, 'receivable') for row in rows], remaining=rest))

    rows, rest = split(10700, 700, [5350, 5350])
    assert rows == [dict(net=5000, tax=350, gross=5350)] * 2
    cases.append(dict(id='F02', historical_payment=rows[0],
                      payments=[effect(rows[1], 'receivable')], remaining=rest))

    rows, rest = split(11900, 1900, [11900])
    assert rows == [dict(net=10000, tax=1900, gross=11900)]
    full = effect(rows[0], 'payable_prior_full_input_vat')
    assert full == dict(cash=-11900, euer_net=-10000, euer_vat=-1900,
                        new_output_vat=0, new_input_vat=0)
    cases.append(dict(id='F03', historical_input_vat=1900, payments=[full], remaining=rest))

    rows, rest = split(119000, 19000, [23800, 35700, 59500])
    assert rows == [dict(net=20000, tax=3800, gross=23800),
                    dict(net=30000, tax=5700, gross=35700),
                    dict(net=50000, tax=9500, gross=59500)]
    paid = [effect(row, 'payable_prior_full_input_vat') for row in rows[1:]]
    assert sum(row['cash'] for row in paid) == -95200
    assert sum(row['new_input_vat'] for row in paid) == 0
    cases.append(dict(id='F04', historical_input_vat=19000,
                      historical_payment=rows[0], payments=paid, remaining=rest))

    cases.append(dict(id='F05', historical_actual_fa_refund=1900,
                      new_actual_fa_refund=0, new_supplier_payment=full,
                      new_euer_surplus=-11900, combined_period_surplus=1900-11900))
    cases.append(dict(id='F06', historical_actual_fa_refund=0,
                      new_actual_fa_refund=1900, new_supplier_payment=full,
                      new_euer_surplus=1900-11900, combined_period_surplus=1900-11900))
    assert cases[-2]['combined_period_surplus'] == cases[-1]['new_euer_surplus'] == -10000

    rows, rest = split(11900, 1900, [3967, 3967, 3966])
    assert rows == [dict(net=3334, tax=633, gross=3967),
                    dict(net=3333, tax=634, gross=3967),
                    dict(net=3333, tax=633, gross=3966)]
    independent_rounds = [int((Decimal(row['gross']) * 1900 / 11900).quantize(
        Decimal(1), rounding=ROUND_HALF_UP)) for row in rows]
    assert sum(independent_rounds) == 1899
    cases.append(dict(id='F07', historical_payment=rows[0],
                      new_component_consumption=rows[1:], remaining=rest,
                      independently_rounded_tax_cents=independent_rounds,
                      incorrect_independent_tax_total=sum(independent_rounds)))

    rows, rest = split(11900, 1900, [5950, 5950])
    assert rows == [dict(net=5000, tax=950, gross=5950)] * 2
    cases.append(dict(id='F08', historical_year_payment=rows[0],
                      new_payment=effect(rows[1], 'payable_prior_full_input_vat'),
                      new_period_expense=5950, annual_expense_with_history=11900,
                      complete_year_without_history=False))

    cases.append(dict(id='F09', bookkeeping_start='2026-11-01',
                      actual_cash_on_start=effect(dict(net=10000, tax=1900, gross=11900), 'receivable'),
                      actual_cash_day_before_is_historical=True,
                      import_date='2026-11-04', import_changes_cash_date=False))
    cases.append(dict(id='F10', imported_open_receivable=11900, opening_bank_balance=50000,
                      new_cash=0, new_euer=0, new_output_vat=0, new_input_vat=0))

    controls = [
        dict(id='C01', kind='incompatible_historical_rounding',
             historical=dict(net=3333, tax=634, gross=3967),
             actual_remaining=dict(net=6667, tax=1266, gross=7933),
             outcome='Preserve original amounts; block narrow cumulative-contract import for clarification.'),
        dict(id='C02', kind='overconsumption', original_gross=11900, historical_paid=11900,
             attempted_new_payment=1, outcome='No residual capacity; no new effect.'),
        dict(id='C03', kind='missing_historical_vat_entitlement_proof',
             outcome='No supported prior-full-deduction import; do not create a new VAT claim as fallback.'),
        dict(id='C04', kind='real_method_or_vat_regime_change',
             outcome='Outside continuation scope; separate transition assessment required.'),
    ]
    assert controls[0]['actual_remaining']['net'] + controls[0]['historical']['net'] == 10000
    assert controls[0]['actual_remaining']['tax'] + controls[0]['historical']['tax'] == 1900
    assert controls[1]['historical_paid'] + controls[1]['attempted_new_payment'] > controls[1]['original_gross']
    data = dict(unit='EUR cents', purpose='independent_reference_arithmetic_not_product_execution',
                rounding='Decimal cumulative ROUND_HALF_UP; explicit technical assumption',
                scope='ordinary ongoing EÜR / regular cash VAT, lawful full old input VAT deduction',
                numerical_cases=cases, contractual_negative_expectations=controls)
    Path(__file__).with_name('expected-cases.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(cases)} numerical reference cases validated; {len(controls)} negative contract expectations recorded. No product tests executed.')


if __name__ == '__main__':
    main()
