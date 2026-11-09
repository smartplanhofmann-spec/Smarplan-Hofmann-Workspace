import {readFileSync} from 'node:fs';

export const fixture=JSON.parse(readFileSync(process.env.SMARTPLAN_SOURCE5_FIXTURE||new URL('../../../app/test/fixtures/source5_positive_corrections.json',import.meta.url)));
export const copy=value=>structuredClone(value);
export const ref=value=>({id:value.id,revision:value.revision,content_hash:value.content_hash});
export function values(section){
  const d=section.payment.details;
  return {run_ref:section.run.id+'@'+section.run.revision,identity_ref:d.identity_id+'@'+d.identity_revision,
    prior_payment_ref:section.prior_payment.id+'@'+section.prior_payment.revision,standard_case_confirmed:true,
    tax_free_payments_minor:(d.tax_free_payments_minor/100).toFixed(2),tax_free_basis:d.tax_free_basis,
    ...Object.fromEntries(d.payments.flatMap((part,index)=>[
      ['paid_on_'+index,part.paid_on],['amount_'+index,(part.amount_minor/100).toFixed(2)],['reference_'+index,part.payment_reference],
      ['running_'+index,(d.settlement_allocations[index].running_minor/100).toFixed(2)],
      ['bonus_'+index,(d.settlement_allocations[index].one_off_allocations.reduce((sum,p)=>sum+p.net_minor,0)/100).toFixed(2)],
    ]))};
}
