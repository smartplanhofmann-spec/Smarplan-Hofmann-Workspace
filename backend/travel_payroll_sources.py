"""Private, immutable travel classifications consumed by a payroll source case.

TravelCash owns only the tax-free component. Payroll owns taxable cash extras;
meal benefits are non-cash and therefore require a matching net deduction.
"""
import re
from core import Problem
from business_personnel_workflow import _sha


def travel_payroll_source(office,actor,settlement_ref,month):
    from business_travel_allowances import TravelAllowances,validate_record
    from payroll_travel_2026 import _reference
    _reference(settlement_ref)
    if not isinstance(month,str) or not re.fullmatch(r'2026-(0[1-9]|1[0-2])',month):raise Problem(400,'Lohnmonat 2026 erforderlich.')
    api=TravelAllowances(office)
    settlement=api._get('settlement',settlement_ref['id'],settlement_ref['revision'])
    if actor is not None:
        fresh,_=api._employee(actor,settlement['employee_id'],permission='personnel.read',own=False)
        api._read_sources(fresh,settlement)
    if {k:settlement[k] for k in ('id','revision','content_hash')}!=settlement_ref:raise Problem(409,'Exakte unveränderte Reiseabrechnungsquelle erforderlich.')
    validate_record(api,settlement);calc=settlement['calculation'];totals=calc['totals'];scheduled=settlement['details'].get('payroll_month')
    if calc['rule_version'] not in ('de_travel_2026_v2','de_travel_2026_v3'):raise Problem(409,'Historische Reiseversion besitzt noch keinen Lohnquellenvertrag.')
    allocations=[]
    def add(key,kind,amount,chosen):
        if amount and chosen==month:allocations.append(dict(key=settlement['id']+':'+key,month=chosen,kind=kind,amount_minor=amount,source_hash=settlement['content_hash']))
    add('individual','individual_taxable_payroll',totals['individual_taxable_minor'],scheduled)
    add('flat_25','flat_taxable_payroll',totals['flat_taxable_minor'],scheduled)
    for item in calc['days']:add('meal_benefit:'+item['date'],'benefit_in_kind_non_cash',item['benefit_in_kind_minor'],item['date'][:7])
    letter_m=any(d['letter_m'] and d['date'][:7]==month for d in calc['days'])
    result=dict(kind='travel_allowances',schema_version=1,employee_id=settlement['employee_id'],month=month,
        settlement_ref=settlement_ref,rule_version=calc['rule_version'],rule_hash=calc['rule_hash'],allocations=allocations,
        tax_free_external_minor=totals['tax_free_minor'] if scheduled==month or scheduled is None and settlement['details']['period_to'][:7]==month else 0,
        flat_taxable_payroll_minor=sum(a['amount_minor'] for a in allocations if a['kind']=='flat_taxable_payroll'),
        individual_taxable_payroll_minor=sum(a['amount_minor'] for a in allocations if a['kind']=='individual_taxable_payroll'),
        benefit_in_kind_non_cash_minor=sum(a['amount_minor'] for a in allocations if a['kind']=='benefit_in_kind_non_cash'),letter_m=letter_m)
    if not allocations and not letter_m:raise Problem(409,'Reiseabrechnung besitzt für diesen Lohnmonat keine zu verarbeitende Lohnquelle.')
    return dict(result,source_hash=_sha(result))


resolve=travel_payroll_source
