from copy import deepcopy
import base64
from core import canonical
from business_payroll_facts import reference
from business_payroll_multiple_cases import PayrollMultipleCases
from test_business_payroll import rid
import test_payroll_multiple_oneoff_2026 as base
import test_business_payroll_multiple as workflow
c=base.CanonicalMultipleComposition('runTest');c.setUp();f=c.f
original_save=f.save

def certificate(amount):
    doc=f.hr.upload(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],purpose='personnel',owner_visible=False,
        filename='prior-employer-'+str(amount)+'.pdf',media_type='application/pdf',
        content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic prior employer taxable wage cents '+str(amount).encode()+b'\n%%EOF').decode()))
    return dict(id=doc['id'],revision=1,content_hash=doc['content_hash'])

def prior(amount,ref):
    return dict(employer_name='Previous synthetic employer',employer_tax_number='111/222/33333',start='2026-01-01',end='2026-09-30',
        running_taxable_minor=amount,other_paid_minor=0,evidence_ref=ref)

def save(kind,details):
    if kind!='annual_tax_forecast':return original_save(kind,details)
    ref=certificate(2000000);details=deepcopy(details)
    details.update(previous_employers=[prior(2000000,ref)],no_previous_employer_ref=None)
    p=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind=kind,details=details,source_file_ids=[f.original['id'],ref['id']])
    preview=f.annual.preview(f.owner,p);body=p|dict(request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
    return f.annual.save(f.owner,body),body,preview
f.save=save
try:
    source,oldsource=c.source()
    m=workflow.MultipleWorkflow('runTest');m.c=c;m.f=f;m.source=source;m.oldsource=oldsource
    m.api=PayrollMultipleCases(f.office,clock=lambda:f.now)
    case,body=m.case();before=case['plan']
    old=source['annual_tax_forecasts'][0]['annual_tax_forecast'];details=deepcopy(old['details']);ref=certificate(1000000)
    details['previous_employers']=[prior(1000000,ref)]
    p=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='annual_tax_forecast',details=details,source_file_ids=[f.original['id'],ref['id']])
    preview=f.annual.preview(f.owner,p)
    body=p|dict(request_id=rid(),id=old['id'],revision=old['revision'],status='active',confirmed=True,preview_hash=preview['preview_hash'],correction_reason='Corrected actual prior employer certificate')
    new=f.annual.save(f.owner,body);source['annual_tax_forecasts'][0]['annual_tax_forecast']=new
    corrected,_=m.case(id=case['id'],revision=case['revision'],correction_reason='Corrected actual prior employer certificate')
    after=corrected['plan']
    assert canonical(before['running_calculation'])==canonical(after['running_calculation'])
    assert after['net_minor']>before['net_minor']
    print({'initial_net':before['net_minor'],'corrected_net':after['net_minor'],'delta':after['net_minor']-before['net_minor'],
        'unchanged_running':True,'distinct_original_prior_employer_certificates':True})
finally:c.doCleanups()
