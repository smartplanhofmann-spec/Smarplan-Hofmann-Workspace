"""Exact LF/CRLF metadata reproduction for archived v6/v7 one-off plans.

The unchanged native kernels establish every source, amount and decision first.
Only hashes derived from known encodings of three trusted historical modules
and their dependent source hashes may differ. No original is rewritten.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
from itertools import product
from pathlib import Path

from core import Problem,canonical
import payroll_oneoff_2026 as social
import payroll_pap_oneoff_2026 as tax
import payroll_pap_2026 as annual
import payroll_oneoff_composition_2026 as single
import payroll_multiple_oneoff_2026 as multiple


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _encodings(path):
    lf=Path(path).read_bytes().replace(b'\r\n',b'\n')
    return tuple(hashlib.sha256(value).hexdigest() for value in (lf,lf.replace(b'\n',b'\r\n')))


@lru_cache(maxsize=1)
def _trusted_variants():
    values=[]
    for annual_hash,tax_hash,social_hash in product(_encodings(annual.__file__),
            _encodings(tax.__file__),_encodings(social.__file__)):
        pap_hash=_sha(dict(tax.ONEOFF_PAP_PROVENANCE,
            annual_primitive_sha256=annual_hash,module_sha256=tax_hash))
        contribution_hash=_sha(dict(version=social.SOCIAL_ONEOFF_VERSION,
            rules=social.YEAR_RULES,sources=social.SOURCES,module_sha256=social_hash))
        rules_hash=_sha(dict(single.RULES,social_hash=contribution_hash,pap_hash=pap_hash))
        values.append((contribution_hash,pap_hash,rules_hash))
    return tuple(values)


def _rooms(snapshot,receipt,contribution_hash):
    current=snapshot['current_annual_basis'];previous=snapshot['previous_annual_basis']
    current_period=single._last_period(current,'regular',receipt)
    previous_period=single._last_period(previous,'regular',receipt) if previous else None
    current_room=single._room(current,current_period,'regular')
    previous_room=single._room(previous,previous_period,'regular') if previous else None
    # These hashes are metadata of the unchanged room. Its source hash binds
    # the original annual basis and is independent of the module encoding.
    if current_room is not None:current_room=dict(current_room,rules_hash=contribution_hash)
    if previous_room is not None:previous_room=dict(previous_room,rules_hash=contribution_hash)
    return current_period,previous_period,current_room,previous_room


def _single_variant(calculated,snapshot,variant):
    contribution_hash,pap_hash,rules_hash=variant
    result=deepcopy(calculated);result['rules_sha256']=rules_hash
    details=result['one_off_details']
    if 'assignment' not in details:return result
    current_period,previous_period,current_room,previous_room=_rooms(snapshot,details['receipt_date'],contribution_hash)
    tax_profile=snapshot['annual_tax_forecast']['sources']['tax_identity']['sources']['profile']['profile']
    assignment=social.select_one_off_assignment(receipt_date=details['receipt_date'],amount_minor=details['amount_minor'],
        current_room=current_room,previous_room=previous_room,
        current_period_ref=current_period['source_ref'] if current_period else None,
        previous_period_ref=previous_period['source_ref'] if previous_period else None,
        mandatory_statutory_health=tax_profile['health_insurance']=='statutory_mandatory',
        previous_year_employment=previous_period is not None)
    # Encoding cannot change any allocation, period, year, or monetary field.
    if {k:v for k,v in assignment.items() if k!='source_hash'}!={k:v for k,v in details['assignment'].items() if k!='source_hash'}:
        return None
    details['assignment']=assignment
    if 'social' in details:
        period=previous_period if assignment['march_clause'] else current_period
        basis=snapshot['previous_annual_basis'] if assignment['march_clause'] else snapshot['current_annual_basis']
        _,profile=single._assignment_profile(basis,period)
        details['social'].update(rules_hash=contribution_hash,assignment=assignment,
            source_hash=_sha(dict(assignment=assignment,profile=profile)))
    if 'tax' in details:details['tax']['pap_hash']=pap_hash
    return result


def _multiple_variant(calculated,snapshot,variant):
    result=deepcopy(calculated);details=result['multiple_one_off_details']
    if 'social_month_group' in details:
        group=details['social_month_group'];events=group['receipt_events']
        current_period,previous_period,current_room,previous_room=_rooms(snapshot,events[-1]['receipt_date'],variant[0])
        changed=multiple.select_monthly_assignment(receipt_events=events,
            current_room=current_room,previous_room=previous_room,
            current_period_ref=current_period['source_ref'] if current_period else None,
            previous_period_ref=previous_period['source_ref'] if previous_period else None,
            mandatory_statutory_health=True,previous_year_employment=previous_period is not None)
        details['social_month_group']=changed
    if 'single_original_calculation' in details:
        source=dict(schema_version=1,source_contract_version=single.SOURCE_CONTRACT_VERSION,
            rule_version=single.ONEOFF_RULE_VERSION,employee_id=snapshot['employee_id'],month=snapshot['month'],
            running_calculation_case=snapshot['running_calculation_case'],one_off_earning=snapshot['components'][0]['earning'],
            current_annual_basis=snapshot['current_annual_basis'],previous_annual_basis=snapshot['previous_annual_basis'],
            annual_tax_forecast=snapshot['annual_tax_forecasts'][0]['annual_tax_forecast'])
        changed=_single_variant(details['single_original_calculation'],source,variant)
        if changed is None:return None
        details['single_original_calculation']=changed
    return result


def calculation_matches(snapshot,calculated,original):
    if calculated==original:return True
    if (not isinstance(calculated,dict) or not isinstance(original,dict)
            or original.get('rule_version')!=calculated.get('rule_version')):
        return False
    version=calculated.get('rule_version')
    candidate=_single_variant if version==single.ONEOFF_RULE_VERSION else _multiple_variant if version==multiple.MULTIPLE_RULE_VERSION else None
    if candidate is None:return False
    return any(candidate(calculated,snapshot,variant)==original for variant in _trusted_variants())


def bind_single_payment_plan(snapshot,plan,original_calculation):
    """Keep v1 money rules while binding the actual accepted run's encoding."""
    if plan['composition_hash']==_sha(original_calculation):
        return deepcopy(plan)
    calculated=multiple.calculate_multiple_source(snapshot,rule_version=multiple.MULTIPLE_RULE_VERSION,
        source_contract_version=multiple.SOURCE_CONTRACT_VERSION)
    if plan['composition_hash']!=_sha(calculated) or not calculation_matches(snapshot,calculated,original_calculation):
        raise Problem(409,'Zahlungszuordnung benötigt die exakt nachgerechnete angenommene Originalabrechnung.')
    bound=deepcopy(plan);bound.pop('plan_hash')
    bound['composition_hash']=_sha(original_calculation)
    return dict(bound,plan_hash=_sha(bound))
