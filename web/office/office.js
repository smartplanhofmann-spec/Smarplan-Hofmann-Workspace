import {stockReturnsUi,isStockReturn,stockReturnPendingAuthorize} from './stock-returns.js';
import {datedCatalogUi,datedPendingAuthorize,datedPricePicker,priceSelection,datedConsumerCommand,datedConsumerPendingAuthorize} from './catalog-prices.js';
import {accountingOpenItemsUi} from './accounting-open-items.js';
import {oiPendingAuthorize} from './accounting-open-items-contract.js';
import {accountingYearValuesUi} from './accounting-year-values.js';
import {yvPendingAuthorize} from './accounting-year-values-contract.js';
import {catalogImportsUi,catalogPendingAuthorize} from './catalog-imports.js';
import {payrollMultipleCasesPendingAuthorize} from './payroll-multiple-cases.js';
import {historicalAssetsUi} from './accounting-historical-assets.js';
import {assetPendingAuthorize} from './accounting-historical-assets-contract.js';
import {purchaseChangesUi} from './purchase-changes.js';
import {purchaseChangePendingAuthorize} from './purchase-changes.js';
import {accountingOpeningsUi,openingPendingAuthorize} from './accounting-openings.js';
import {bankPendingAuthorize,bankReconciliationUi} from './bank-reconciliation.js';
import {resourceCustodyPendingAuthorize} from './resource-custody.js';
import {resourceCustodyUi} from './resource-custody.js';
import {payrollCashPendingAuthorize} from './payroll-cash.js';
import {payrollFactsPendingAuthorize} from './payroll-facts.js';
import {payrollEntitlementsPendingAuthorize} from './payroll-entitlements.js';
import {payrollTravelTaxPoliciesPendingAuthorize} from './payroll-travel-tax-policies.js';
import {payrollCalculationCasesPendingAuthorize} from './payroll-calculation-cases.js';
import {payrollWageInterruptionsPendingAuthorize} from './payroll-wage-interruptions.js';
import {payrollAnnualPendingAuthorize} from './payroll-annual-basis.js';
import {payrollOneOffCasesPendingAuthorize} from './payroll-oneoff-cases.js';
import {servicePendingAuthorize,serviceUi} from './service.js';
import {companyHandoverUi} from './company-handover.js';
import {privacyCasesUi} from './privacy-cases.js';
import {customFieldsPendingAuthorize,customFieldsUi} from './custom-fields.js';
import {createAccountingEuer,euerRights,euerAuthorize} from './accounting-euer.js';
import {accountingYearPackageUi} from './accounting-year-package.js';
import {createProjectEconomics} from './project-economics.js';
import {renderCustomerWorkspace,customerWorkspaceRights} from './customer-workspace-staff.js';
/* Smartplan Office online browser client. No providers, persistent credentials or service worker. */
import {assetProvenanceUi} from './asset-provenance.js';
import {personnelWorkflowUi} from './personnel-workflow.js';
import {timeTrackingUi} from './time-tracking.js';
import {travelAllowancesUi} from './travel-allowances.js';
import {assistantUi} from './assistant.js';
import {companyEventsUi,companyEventRights,companyEventPendingAuthorize} from './company-events.js';
import {payrollPendingAuthorize,payrollUi} from './payroll.js';
import {renderCompanyOverview} from './company-overview.js';
import {migrationPendingAuthorize,migrationsUi} from './migrations.js';
import {companyHandoverPendingAuthorize} from './company-handover.js';
import {inventoryCountsUi,inventoryCountPendingAuthorize} from './inventory-counts.js';
import {createSales,salesPendingAuthorize} from './sales.js';
import {createCommunicationHistory} from './communication-history.js';
import {projectTasksUi,taskPendingAuthorize} from './project-tasks.js';
import {projectMilestonesUi,milestonePendingAuthorize,milestoneCommandPath} from './project-milestones.js';
import {maintenanceContractsUi,maintenanceContractPendingAuthorize} from './maintenance-contracts.js';
import {documentTimePicker,documentTimeCommand,documentTimeContext,documentTimePendingAuthorize,documentTimeReceipt,documentTimesChanged} from './document-time-sources.js';
export class ApiError extends Error {
  constructor(message, status = 0, requestResolution = null) { super(message); this.name = 'ApiError'; this.status = status; this.requestResolution=status===409&&requestResolution==='not_accepted'?'not_accepted':null; }
}
export class StaleSession extends Error { constructor() { super('Sitzung gewechselt'); this.name = 'StaleSession'; } }
export function requestId() { return crypto.randomUUID().replaceAll('-', ''); }
export function formatMoney(value) {
  if (typeof value !== 'string' || !/^-?\d+(\.\d+)?$/.test(value)) return '—';
  const [whole, fraction = ''] = value.split('.');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${fraction.padEnd(2, '0')} €`;
}
export function formatDate(value, time = false) {
  if (!value) return '—';
  const date = new Date(value.length === 10 ? value + 'T12:00:00' : value);
  if (!Number.isFinite(date.getTime())) return '—';
  return new Intl.DateTimeFormat('de-DE', {dateStyle: 'medium', ...(time ? {timeStyle: 'short'} : {})}).format(date);
}
export function duration(seconds) { return Number.isInteger(seconds) ? `${Math.floor(seconds / 3600)}:${String(Math.floor(seconds % 3600 / 60)).padStart(2, '0')} Std.` : '—'; }
export function formatQuantity(value,unit='') {
  if(typeof value!=='string'||! /^-?\d+(\.\d+)?$/.test(value))return '—';
  const [whole,fraction]=value.split('.'),display=whole.replace(/\B(?=(\d{3})+(?!\d))/g,'.')+(fraction!==undefined?','+fraction:'');
  return display+(unit?' '+({m2:'m²',m3:'m³',piece:'Stk.',h:'Std.'}[unit]||unit):'');
}
export function decimalText(value) {
  const result = String(value).trim().replace(',', '.');
  if (!/^-?\d+(\.\d{1,4})?$/.test(result)) throw new Error('Bitte eine Dezimalzahl mit höchstens vier Nachkommastellen eingeben.');
  return result;
}
export function dateInput(date = new Date()) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`; }
export function localDateTime(value) {
  const d = value ? new Date(value) : new Date();
  return `${dateInput(d)}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}
export function collection(value) { return Array.isArray(value) ? value : value?.items || []; }
const ORGANIZATION_AREAS = [
  ['personnel','Personal'], ['material','Material'], ['planning','Einsatzplanung'],
  ['documents','Belege'], ['finance','Finanzen'],
];
const ORGANIZATION_NEEDS = [
  ['has_employees','Unser Unternehmen beschäftigt Mitarbeiter'],
  ['uses_inventory','Wir verwalten Material und Lagerbestände'],
  ['project_work','Wir arbeiten mit Projekten und Einsatzplanung'],
  ['uses_finance','Wir verwenden die eigenen Finanzfunktionen'],
  ['works_with_tax_advisor','Wir arbeiten mit einem Steuerberater zusammen'],
];
export function organizationMetadata(capabilities) {
  if (!Array.isArray(capabilities?.features) || !capabilities.features.includes('organization_modules')) return null;
  const value=capabilities.organization;
  if (!value || !Number.isSafeInteger(value.revision) || value.revision<0 || typeof value.configured!=='boolean')
    throw new ApiError('Die Unternehmenskonfiguration konnte nicht sicher geladen werden.',502);
  const modules={};
  for (const [name] of ORGANIZATION_AREAS) {
    const item=value.modules?.[name];
    if (!item || typeof item.visible!=='boolean' || typeof item.enabled!=='boolean')
      throw new ApiError('Die Unternehmenskonfiguration konnte nicht sicher geladen werden.',502);
    modules[name]={visible:item.visible,enabled:item.enabled};
  }
  return {revision:value.revision,configured:value.configured,modules};
}
export function organizationSectionAllowed(section, authorized, organization, includeHidden=false) {
  return authorized===true && (includeHidden || organization?.modules?.[section]?.visible!==false);
}
function organizationAreaAuthorized(section,permissions,capabilities) {
  const required={personnel:['time.own','personnel.read'],material:['inventory.read','finance.read'],
    planning:['planning.read'],documents:['documents.read','finance.read'],finance:['finance.read']}[section];
  const module={personnel:'planning',material:'inventory',planning:'planning',documents:'documents',finance:'finance'}[section];
  const allowed=new Set(permissions),supported=new Set(capabilities);
  return !!required&&required.some(permission=>allowed.has(permission))&&
    (supported.has(module)||supported.has('business_'+module));
}
export function organizationHiddenAreas(organization,permissions,capabilities,globalPermissions=permissions) {
  return ORGANIZATION_AREAS.map(([name])=>name).filter(name=>organization?.modules?.[name]?.visible===false&&
    organizationAreaAuthorized(name,projectContext(name).label?permissions:globalPermissions,capabilities));
}
export function organizationModuleEnabled(section, organization) {
  return organization?.modules?.[section]?.enabled!==false;
}
export function organizationCommandArea(path) {
  if(typeof path!=='string')return null;
  if(path.startsWith('/organization')||path.startsWith('/settings/')||path==='/commercial/settings')return null;
  if(/^\/portal\/grants\/[^/]+\/revoke$/.test(path))return null;
  if(path.startsWith('/portal/'))return 'documents';
  if(/^\/customer-workspace\/(?:grants|files)\/[a-f0-9]{32}\/revoke$/.test(path))return null;
  if(/^\/customer-workspace(?:\/|$)/.test(path))return 'documents';
  if(/^\/(employees|absences|shifts|time|personnel|payroll)(?:\/|$)/.test(path))return 'personnel';
  if(/^\/(resources|appointments|planning)(?:\/|$)/.test(path))return 'planning';
  if(/^\/(inventory|purchasing)(?:\/|$)/.test(path)||path==='/budgets'||/^\/projects\/[^/]+\/changes(?:\/|$)/.test(path))return 'material';
  if(/^\/(documents|articles|services|templates|text-blocks|commercial)(?:\/|$)/.test(path))return 'documents';
  if(/^\/adapters\/imports\/[^/]+\/(apply|offer)$/.test(path))return 'documents';
  if(/^\/(finance|accounting|project-economics|receipt-media)(?:\/|$)/.test(path))return 'finance';
  if(path==='/assets/from-delivery'||/^\/assets\/[a-f0-9]{32}\/origin$/.test(path))return 'material';
  return null;
}
export function organizationChange(current, values) {
  if (!Number.isSafeInteger(current?.revision) || current.revision<0)
    throw new Error('Die Unternehmenskonfiguration zuerst neu laden.');
  const needs={},modules={};
  for (const [name] of ORGANIZATION_NEEDS) {
    if (typeof values['needs_'+name]!=='boolean') throw new Error('Bitte den Unternehmensbedarf vollständig angeben.');
    needs[name]=values['needs_'+name];
  }
  for (const [name] of ORGANIZATION_AREAS) {
    const choice=values['visibility_'+name],enabled=values['enabled_'+name];
    if (!['auto','show','hide'].includes(choice) || typeof enabled!=='boolean')
      throw new Error('Bitte die Sichtbarkeit und Aktivierung aller Module angeben.');
    modules[name]={visible:choice==='auto'?null:choice==='show',enabled};
  }
  return {revision:current.revision,needs,modules};
}
// E1a prepares evidenced EUR cash flows; tax classification remains unconfigured.
export function accountingAccess(globalCapabilities,organization,status=null) {
  const permissions=new Set(globalCapabilities?.permissions||[]),supported=new Set(globalCapabilities?.capabilities||[]);
  const available=globalCapabilities?.features?.includes('accounting_prejournal')===true&&supported.has('business_accounting');
  const read=available&&permissions.has('finance.read')&&permissions.has('accounting.read');
  const writable=read&&globalCapabilities.readonly===false&&status?.writes_allowed===true&&organizationModuleEnabled('finance',organization);
  return {available,read,prepare:writable&&permissions.has('accounting.prepare'),admin:writable&&permissions.has('accounting.admin')};
}
export function accountingAmount(value,{zero=false}={}) {
  const text=String(value??'').trim().replace(',','.');
  if(!/^\d+(?:\.\d{1,2})?$/.test(text))throw new Error('Bitte einen EUR-Betrag mit höchstens zwei Nachkommastellen eingeben. Es wird nicht gerundet.');
  const [whole,fraction='']=text.split('.'),cents=BigInt(whole)*100n+BigInt(fraction.padEnd(2,'0'));
  if(cents<(zero?0n:1n)||cents>99999999999n)throw new Error('Der EUR-Betrag muss positiv und höchstens 999999999,99 sein.');
  return `${cents/100n}.${String(cents%100n).padStart(2,'0')}`;
}
function accountingId(value,hash=false) {
  if(typeof value!=='string'||!(hash?/^[0-9a-f]{64}$/:/^[0-9a-f]{32}$/).test(value))throw new ApiError('Quellennachweis unvollständig. Bitte den Stand neu laden.',502);
  return value;
}
function accountingRevision(value,zero=false) {
  if(!Number.isSafeInteger(value)||value<(zero?0:1))throw new ApiError('Die bestätigte Version zuerst neu laden.',502);
  return value;
}
function accountingText(value,label,max,optional=false) {
  const text=String(value??'').trim();
  if((!optional&&!text)||text.length>max)throw new Error(`${label}: ${optional?'höchstens': '1 bis'} ${max} Zeichen eingeben.`);
  if(/[\u0000-\u001f\u007f\ud800-\udfff]/u.test(text))throw new Error(`${label}: einzeiligen Text ohne Steuerzeichen eingeben.`);
  return text;
}
function accountingDay(value) {
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||value.startsWith('0000-'))throw new Error('Bitte den tatsächlichen Geldflusstag angeben.');
  const date=new Date(value+'T00:00:00Z');
  if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==value)throw new Error('Bitte einen gültigen Geldflusstag angeben.');
  return value;
}
function accountingConfirmation(values) { if(values.confirmation!==true)throw new Error('Bitte die geprüften Angaben ausdrücklich bestätigen.'); }
export function accountingAccountData(account,values) {
  accountingConfirmation(values);
  const name=accountingText(values.name,'Kontoname',200);
  if(account) {
    accountingId(account.id);if(typeof values.active!=='boolean')throw new Error('Aktivität des Kontos bestätigen.');
    return {revision:accountingRevision(account.revision),name,active:values.active,confirmation:true};
  }
  const code=accountingText(values.code,'Kontocode',40);
  if(!/^[A-Za-z0-9_-]+$/.test(code)||!['bank','cash','payment_service'].includes(values.kind))throw new Error('Kontocode und Kontoart prüfen.');
  return {code,name,kind:values.kind,confirmation:true};
}
function accountingCashData(account,values) {
  accountingConfirmation(values);
  if(account?.active!==true||account.currency!=='EUR')throw new Error('Bitte ein aktives EUR-Geldkonto auswählen.');
  return {account_id:accountingId(account.id),account_revision:accountingRevision(account.revision),cash_date:accountingDay(values.cash_date),
    evidence_reference:accountingText(values.evidence_reference,'Geldfluss-Nachweisreferenz',200),confirmation:true};
}
export function accountingPaymentData(source,account,values) {
  if(source?.linked_event_id)throw new Error('Diese Zahlung ist bereits verknüpft. Bitte den vorhandenen Geldfluss prüfen.');
  if(source?.currency!=='EUR'||!['receipt','refund'].includes(source.kind)||source.direction!==(source.kind==='refund'?'out':'in'))throw new ApiError('Zahlungsquelle zuerst neu laden.',502);
  accountingAmount(source.amount);
  return {payment_id:accountingId(source.payment_id),source_hash:accountingId(source.source_hash,true),...accountingCashData(account,values)};
}
export function accountingPayoutData(source,account,values) {
  if(source?.payable!==true||source.blocked_reason||source.currency!=='EUR')throw new Error('Dieser Beleg ist für eine neue Auszahlung gesperrt. Bitte den Stand prüfen.');
  const amount=accountingAmount(values.amount),remaining=accountingAmount(source.remaining_amount,{zero:true});
  if(BigInt(amount.replace('.',''))>BigInt(remaining.replace('.','')))throw new Error('Die Auszahlung überschreitet den verbleibenden Betrag.');
  return {receipt_id:accountingId(source.receipt_id),source_hash:accountingId(source.source_hash,true),review_revision:accountingRevision(source.review_revision),
    review_sha256:accountingId(source.review_sha256,true),original_sha256:accountingId(source.original_sha256,true),...accountingCashData(account,values),
    expected_cash_revision:accountingRevision(source.cash_revision,true),amount,reference:accountingText(values.reference,'Verwendungszweck',1000,true)};
}
export function accountingStatus(value) {
  if(value?.profile_status!=='unconfigured'||value.tax_status!=='unconfigured'||value.tax_result_available!==false||value.scope!=='authorized_sources'||typeof value.writes_allowed!=='boolean')throw new ApiError('Der Vorjournalstatus konnte nicht sicher geladen werden.',502);
  return value;
}
export function accountingPage(value,offset=0,events=false) {
  if(!Array.isArray(value?.items)||value.scope!=='authorized_sources'||!Number.isSafeInteger(value.total)||value.total<value.items.length||value.items.length>25||
      !(value.next_offset===null||(Number.isSafeInteger(value.next_offset)&&value.next_offset>offset&&value.next_offset<=100000&&value.next_offset<value.total))||
      (events&&value.tax_result_available!==false))throw new ApiError('Diese Vorjournalliste konnte nicht vollständig geprüft werden. Bitte erneut laden.',502);
  return value;
}

const PROFILE_FIELDS=['legal_form','accounting_method','vat_regime','vat_timing','vat_effective_from','bookkeeping_start'];
const PROFILE_FLAGS=['scope','tax_status','tax_result_available'];
function profileKeys(value,keys) {
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||keys.some(key=>!Object.hasOwn(value,key)))throw new ApiError('Die Profilangaben konnten nicht sicher gelesen werden.',502);
}
function profileFlags(value) {
  if(value.scope!=='organization_profile'||value.tax_status!=='unconfigured'||value.tax_result_available!==false)throw new ApiError('Das Vorbereitungsprofil darf keine Steuerfreigabe behaupten.',502);
}
function profileText(value,label,max) {
  if(typeof value!=='string'||!value.trim()||Array.from(value).length>max||/[\u0000-\u001f\u007f\ud800-\udfff]/u.test(value))throw new Error(`${label}: einzeiligen Text mit 1 bis ${max} Zeichen ohne Steuerzeichen eingeben.`);
  return value;
}
function profileDay(value) {
  if(value===null)return null;
  accountingDay(value);if(value<'1900-01-01'||value>'2200-12-31')throw new Error('Bitte einen gültigen Profilbeginn zwischen 1900 und 2200 angeben.');return value;
}
export function accountingPreparationProfile(value) {
  profileKeys(value,PROFILE_FIELDS);
  if(value.legal_form!=='sole_proprietorship'||value.accounting_method!=='euer'||![null,'small_business','regular'].includes(value.vat_regime)||![null,'accrual','cash'].includes(value.vat_timing)||value.vat_regime!=='regular'&&value.vat_timing!==null||value.vat_regime===null&&value.vat_effective_from!==null)throw new Error('Bitte die unterstützten Profilangaben und ihre Abhängigkeiten prüfen.');
  profileDay(value.vat_effective_from);profileDay(value.bookkeeping_start);return value;
}
export function accountingProfileAccess(capabilities,organization,value=null,online=true) {
  const base=accountingAccess(capabilities,organization,{writes_allowed:true}),permissions=new Set(capabilities?.permissions||[]);
  const available=base.available&&capabilities.features?.includes('accounting_preparation_profile')===true&&capabilities.capabilities?.includes('business_accounting_profile')===true;
  const read=available&&base.read,admin=read&&online&&permissions.has('accounting.admin')&&capabilities.readonly===false&&organizationModuleEnabled('finance',organization)&&(value===null||value.writes_allowed===true);
  return {available,read,admin};
}
export function accountingProfileEntry(value) {
  profileKeys(value,['id','revision','previous_state_hash','profile','reason','evidence_reference','preview_hash','created_by','created_at',...PROFILE_FLAGS]);profileFlags(value);
  accountingId(value.id);accountingRevision(value.revision);accountingId(value.previous_state_hash,true);accountingId(value.preview_hash,true);accountingId(value.created_by);accountingPreparationProfile(value.profile);
  profileText(value.reason,'Begründung',1000);profileText(value.evidence_reference,'Nachweisreferenz',200);
  if(typeof value.created_at!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$/.test(value.created_at)||!Number.isFinite(Date.parse(value.created_at))||new Date(value.created_at).toISOString().replace('.000Z','+00:00')!==value.created_at)throw new ApiError('Der Erfassungszeitpunkt des Profils ist ungültig.',502);
  profileDay(value.created_at.slice(0,10));return value;
}
export function accountingProfileState(value) {
  profileKeys(value,['revision','state_hash','preparation_status','current','writes_allowed',...PROFILE_FLAGS]);profileFlags(value);accountingRevision(value.revision,true);accountingId(value.state_hash,true);
  if(typeof value.writes_allowed!=='boolean'||(value.revision===0?(value.current!==null||value.preparation_status!=='unrecorded'):(value.preparation_status!=='recorded'||accountingProfileEntry(value.current).revision!==value.revision)))throw new ApiError('Der gespeicherte Profilstand ist widersprüchlich.',502);
  return value;
}
export function accountingProfilePage(value,offset=0) {
  profileKeys(value,['items','total','next_offset','scope']);
  if(value.scope!=='organization_profile'||!Array.isArray(value.items)||value.items.length>25||!Number.isSafeInteger(value.total)||value.total<value.items.length||!(value.next_offset===null||Number.isSafeInteger(value.next_offset)&&value.next_offset===offset+value.items.length&&value.next_offset>offset&&value.next_offset<value.total&&value.next_offset<=100000))throw new ApiError('Der Profilverlauf konnte nicht sicher geladen werden.',502);
  const seen=new Set();let previous=Infinity;
  for(const entry of value.items){accountingProfileEntry(entry);if(seen.has(entry.id)||entry.revision>=previous||entry.revision>value.total)throw new ApiError('Die Profilversionen sind nicht eindeutig geordnet.',502);seen.add(entry.id);previous=entry.revision;}
  return value;
}
export function accountingProfilePreviewData(source,values) {
  accountingProfileState(source);
  if(!source.writes_allowed)throw new Error('Neue Profilversionen sind derzeit gesperrt. Bitte den aktuellen Stand laden.');
  const profile=accountingPreparationProfile(Object.fromEntries(PROFILE_FIELDS.map(key=>[key,['vat_regime','vat_timing','vat_effective_from','bookkeeping_start'].includes(key)&&values[key]===''?null:values[key]])));
  return {expected_revision:source.revision,state_hash:source.state_hash,profile:{...profile},reason:profileText(values.reason,'Begründung',1000),evidence_reference:profileText(values.evidence_reference,'Nachweisreferenz',200)};
}
export function accountingProfilePreview(value,body) {
  profileKeys(value,['expected_revision','state_hash','profile','reason','evidence_reference','preview_hash',...PROFILE_FLAGS]);profileFlags(value);accountingRevision(value.expected_revision,true);accountingId(value.state_hash,true);accountingId(value.preview_hash,true);accountingPreparationProfile(value.profile);
  profileText(value.reason,'Begründung',1000);profileText(value.evidence_reference,'Nachweisreferenz',200);
  if(['expected_revision','state_hash','reason','evidence_reference'].some(key=>value[key]!==body[key])||PROFILE_FIELDS.some(key=>value.profile[key]!==body.profile[key]))throw new ApiError('Die Vorschau gehört nicht zu den ausdrücklich eingegebenen Profilangaben.',502);
  return value;
}
export function accountingProfileConfirmData(body,preview,confirmation) {
  if(confirmation!==true)throw new Error('Bitte diese Profilversion ausdrücklich bestätigen.');accountingProfilePreview(preview,body);
  return {...body,profile:{...body.profile},preview_hash:preview.preview_hash,confirmation:true};
}
export async function accountingProfileAuthorize(api,{write=false,online=true}={}) {
  const capabilities=await api.get('/business/capabilities'),organization=organizationMetadata(capabilities);
  if(!accountingProfileAccess(capabilities,organization).read)throw new ApiError('Das Vorbereitungsprofil benötigt aktuelle globale Buchführungs- und Finanzleserechte.',403);
  const source=accountingProfileState(await api.get('/business/accounting/profile'));
  if(write&&!capabilities.permissions.includes('accounting.admin'))throw new ApiError('Eine neue Profilversion benötigt das globale Recht accounting.admin.',403);
  if(write&&!online)throw new ApiError('Die unveränderte Profilanfrage benötigt eine Internetverbindung.',0);
  if(write&&!accountingProfileAccess(capabilities,organization,source,online).admin)throw new ApiError('Neue Profilversionen sind durch den aktuellen Betriebszustand gesperrt.',423);
  return source;
}

export function accountingAllocationAccess(capabilities,organization,value=null,online=true) {
  const permissions=new Set(capabilities?.permissions||[]),accounting=accountingAccess(capabilities,organization);
  const available=accounting.available&&capabilities.features?.includes('accounting_payment_allocation')===true&&capabilities.capabilities?.includes('business_accounting_allocations')===true;
  const read=available&&accounting.read;
  const prepare=read&&online===true&&capabilities.readonly===false&&organizationModuleEnabled('finance',organization)&&permissions.has('accounting.prepare')&&permissions.has('finance.write');
  return {available,read,prepare:prepare&&(value===null||value.writes_allowed===true&&value.eligible===true)};
}
export function accountingAllocationState(value) {
  if(value?.scope!=='authorized_sources'||value.tax_result_available!==false||value.currency!=='EUR'||typeof value.eligible!=='boolean'||typeof value.writes_allowed!=='boolean'||!Array.isArray(value.allocations))throw new ApiError('Der wirksame Zuordnungsstand konnte nicht sicher geladen werden.',502);
  accountingId(value.payment_id);accountingId(value.event_id);accountingId(value.source_hash,true);accountingId(value.state_hash,true);accountingRevision(value.revision,true);
  if(value.customer_id!==null)accountingId(value.customer_id);
  accountingAmount(value.amount);
  for(const field of ['allocated_amount','unallocated_amount'])if(typeof value[field]!=='string'||! /^-?(?:0|[1-9]\d*)\.\d{2}$/.test(value[field]))throw new ApiError('Der wirksame Betrag konnte nicht gelesen werden.',502);
  return value;
}
export function accountingAllocationPreviewData(source,document,values) {
  accountingAllocationState(source);
  if(!source.eligible||!source.writes_allowed)throw new Error('Diese Zahlung ist für eine neue Zuordnung gesperrt. Bitte den Stand neu laden.');
  if(values.customer_confirmation!==true)throw new Error('Bitte den Kunden der gewählten Rechnung ausdrücklich bestätigen.');
  const customer_id=accountingId(document?.customer_id);
  if(source.customer_id!==null&&source.customer_id!==customer_id)throw new Error('Die Rechnung gehört nicht zur bestätigten Kundenbindung.');
  const amount=accountingAmount(values.amount),cents=BigInt(amount.replace('.',''));
  if(cents>BigInt(accountingAmount(source.unallocated_amount,{zero:true}).replace('.',''))||cents>BigInt(accountingAmount(document.open,{zero:true}).replace('.','')))throw new Error('Der Betrag überschreitet den freien Zahlungsbetrag oder den offenen Rechnungsbetrag.');
  return {source_hash:source.source_hash,expected_revision:source.revision,state_hash:source.state_hash,customer_id,
    document_id:accountingId(document.document_id),document_state_hash:accountingId(document.document_state_hash,true),amount,reason:accountingText(values.reason,'Begründung',1000)};
}
export function accountingAllocationPreview(value,body,paymentId,eventId) {
  if(value?.scope!=='authorized_sources'||value.tax_result_available!==false||value.payment_id!==paymentId||value.event_id!==eventId||
      value.document?.document_id!==body.document_id||value.document.document_state_hash!==body.document_state_hash||value.document.customer_id!==body.customer_id||
      ['customer_id','source_hash','expected_revision','state_hash','amount','reason'].some(field=>value[field]!==body[field]))throw new ApiError('Die Vorschau stimmt nicht mit der bestätigten Quelle und Rechnung überein. Bitte neu prüfen.',502);
  accountingId(value.preview_hash,true);accountingId(value.document.payload_sha256,true);accountingId(value.document.pdf_sha256,true);
  const cents=field=>BigInt(accountingAmount(value[field],{zero:true}).replace('.','')),amount=BigInt(body.amount.replace('.',''));
  if(cents('unallocated_before')-amount!==cents('unallocated_after')||cents('open_before')-amount!==cents('open_after'))throw new ApiError('Die Betragsstände der Vorschau stimmen nicht überein.',502);
  return value;
}
export function accountingAllocationAssignData(body,preview,confirmation) {
  if(confirmation!==true)throw new Error('Bitte die geprüfte Vorschau gesondert verbindlich bestätigen.');
  accountingAllocationPreview(preview,body,preview.payment_id,preview.event_id);
  return {...body,preview_hash:preview.preview_hash,confirmation:true};
}

export function componentAccess(capabilities,organization,value=null,online=true) {
  const allocations=accountingAllocationAccess(capabilities,organization,null,online);
  const available=allocations.available&&capabilities.features?.includes('accounting_document_components')===true&&capabilities.capabilities?.includes('business_accounting_components')===true;
  const read=available&&allocations.read;
  return {available,read,prepare:read&&allocations.prepare&&(value===null||value.writes_allowed===true&&value.eligible===true)};
}
function componentCents(value) {
  if(typeof value!=='string'||! /^(?:0|[1-9]\d*)\.\d{2}$/.test(value))throw new ApiError('Die bestätigten Centbeträge konnten nicht sicher gelesen werden.',502);
  return BigInt(value.replace('.',''));
}
function componentEnvelope(value) {
  if(value?.scope!=='authorized_sources'||value.tax_status!=='unconfigured'||value.tax_result_available!==false)throw new ApiError('Der belegte Aufteilungsstand konnte nicht sicher geladen werden.',502);
}
export function componentState(value) {
  componentEnvelope(value);accountingId(value.event_id);accountingId(value.source_hash,true);accountingId(value.state_hash,true);accountingRevision(value.revision,true);
  if(value.currency!=='EUR'||!['customer_receipt','supplier_payout','customer_refund'].includes(value.source_kind)||typeof value.eligible!=='boolean'||typeof value.writes_allowed!=='boolean'||componentCents(value.amount)<=0n||
      componentCents(value.documented_amount)+componentCents(value.undocumented_amount)!==componentCents(value.amount)||componentCents(value.unallocated_amount)>componentCents(value.undocumented_amount))throw new ApiError('Die Betragsstände des Zahlungsnachweises stimmen nicht überein.',502);
  return value;
}
export function componentPortion(value,eventId) {
  accountingId(value?.portion_id,true);accountingId(value.portion_state_hash,true);
  if(value.event_id!==eventId||value.currency!=='EUR'||!['original_allocation','additional_allocation','supplier_payout'].includes(value.kind)||typeof value.eligible!=='boolean'||componentCents(value.amount)<=0n||!Array.isArray(value.groups)||value.groups.length>500)throw new ApiError('Der Beleganteil konnte nicht sicher geladen werden.',502);
  if(value.kind==='supplier_payout') {accountingId(value.receipt_id);accountingId(value.original_sha256,true);accountingId(value.review_sha256,true);accountingRevision(value.review_revision);}
  else {accountingId(value.document_id);accountingId(value.payload_sha256,true);accountingId(value.pdf_sha256,true);}
  const seen=new Set();
  for(const group of value.groups) {
    accountingId(group.group_id,true);if(seen.has(group.group_id))throw new ApiError('Eine Beleggruppe ist doppelt enthalten.',502);seen.add(group.group_id);
    for(const prefix of ['', 'documented_', 'remaining_'])if(componentCents(group[prefix+'net'])+componentCents(group[prefix+'tax'])!==componentCents(group[prefix+'gross']))throw new ApiError('Die Beleggruppensummen stimmen nicht überein.',502);
    for(const field of ['net','tax','gross'])if(componentCents(group['documented_'+field])+componentCents(group['remaining_'+field])!==componentCents(group[field]))throw new ApiError('Die verbleibenden Beleggruppenbeträge stimmen nicht überein.',502);
  }
  return value;
}
export function componentPreviewData(source,portion,groups,reason) {
  componentState(source);componentPortion(portion,source.event_id);
  if(!source.eligible||!source.writes_allowed||!portion.eligible)throw new Error('Dieser Beleganteil ist für eine neue Aufteilung gesperrt. Bitte den Stand neu laden.');
  if(!Array.isArray(groups)||groups.length<1||groups.length>500)throw new Error('Bitte mindestens eine positive Bruttoaufteilung eingeben.');
  let total=0n;const seen=new Set(),selected=groups.map(item=>{
    const group=portion.groups.find(group=>group.group_id===item.group_id);
    if(!group||seen.has(item.group_id))throw new Error('Nur jede angebotene Beleggruppe genau einmal verwenden.');seen.add(item.group_id);
    const amount=accountingAmount(item.amount),cents=componentCents(amount);if(cents>componentCents(group.remaining_gross))throw new Error('Eine Gruppe überschreitet ihren verfügbaren Bruttorest.');total+=cents;
    return {group_id:item.group_id,amount};
  });
  if(total!==componentCents(portion.amount))throw new Error(`Die Gruppensumme muss genau dem festen Beleganteil von ${formatMoney(portion.amount)} entsprechen.`);
  return {source_hash:source.source_hash,expected_revision:source.revision,state_hash:source.state_hash,portion_id:portion.portion_id,portion_state_hash:portion.portion_state_hash,groups:selected,reason:accountingText(reason,'Begründung',1000)};
}
function componentLines(value) {
  componentEnvelope(value);componentPortion(value.portion,value.event_id);
  if(value.amount!==value.portion.amount||!Array.isArray(value.lines)||!value.lines.length||value.lines.length>500)throw new ApiError('Die Belegaufteilung konnte nicht sicher gelesen werden.',502);
  const seen=new Set();let net=0n,tax=0n,gross=0n;
  for(const line of value.lines) {
    const group=value.portion.groups.find(group=>group.group_id===line.group_id);
    if(!group||seen.has(line.group_id))throw new ApiError('Die Vorschau enthält eine unbekannte oder doppelte Gruppe.',502);seen.add(line.group_id);
    const amount=componentCents(line.amount),lineNet=componentCents(line.net),lineTax=componentCents(line.tax);
    if(amount<=0n||lineNet+lineTax!==amount)throw new ApiError('Die Netto-/Steueranteile stimmen nicht mit dem Bruttoanteil überein.',502);
    for(const [field,delta]of [['gross',amount],['net',lineNet],['tax',lineTax]])if(componentCents(line[field+'_before'])!==componentCents(group['documented_'+field])||componentCents(line[field+'_after'])-componentCents(line[field+'_before'])!==delta)throw new ApiError('Die bestätigten Gruppenstände stimmen nicht überein.',502);
    if(componentCents(line.remaining_gross)!==componentCents(group.gross)-componentCents(line.gross_after))throw new ApiError('Der verbleibende Bruttorest stimmt nicht überein.',502);
    net+=lineNet;tax+=lineTax;gross+=amount;
  }
  if(net!==componentCents(value.net)||tax!==componentCents(value.tax)||gross!==componentCents(value.amount)||net+tax!==gross)throw new ApiError('Die Vorschau summiert sich nicht zum festen Beleganteil.',502);
  return value;
}
export function componentPreview(value,body,eventId) {
  componentLines(value);accountingId(value.preview_hash,true);
  if(value.event_id!==eventId||value.source_hash!==body.source_hash||value.expected_revision!==body.expected_revision||value.state_hash!==body.state_hash||value.reason!==body.reason||value.portion.portion_id!==body.portion_id||value.portion.portion_state_hash!==body.portion_state_hash||
      value.lines.length!==body.groups.length||value.lines.some(line=>!body.groups.some(group=>group.group_id===line.group_id&&group.amount===line.amount)))throw new ApiError('Die Vorschau stimmt nicht mit dem gewählten Beleganteil und den eingegebenen Gruppen überein.',502);
  return value;
}
export function componentConfirmData(body,preview,confirmation) {
  if(confirmation!==true)throw new Error('Bitte die geprüfte Belegaufteilung gesondert bestätigen.');
  componentPreview(preview,body,preview.event_id);return {...body,groups:body.groups.map(group=>({...group})),preview_hash:preview.preview_hash,confirmation:true};
}
// One logical confirmation per cash event, even when its invoice changes writer.
// The saved path remains part of OfficeApi's immutable pending operation.
export function componentPendingKey(eventId) { return 'component-confirm-'+accountingId(eventId); }
export function componentPendingOperation(operations,eventId) {
  accountingId(eventId);
  return operations.find(item=>item.path===`/business/accounting/components/events/${eventId}/confirm`||item.path===`/business/accounting/components/v2/events/${eventId}/confirm`)||null;
}
export function capacityAccess(capabilities,organization,value=null,online=true) {
  const refunds=refundAccess(capabilities,organization,null,online),available=refunds.available&&capabilities.features?.includes('accounting_document_component_reuse')===true&&capabilities.capabilities?.includes('business_accounting_capacity')===true;
  const read=available&&refunds.read;
  return {available,read,prepare:read&&refunds.prepare&&(value===null||value.writes_allowed===true&&value.eligible===true)};
}
function capacityMoney(value) {
  if(!value||componentCents(value.net)+componentCents(value.tax)!==componentCents(value.gross))throw new ApiError('Die verfügbaren Netto-/Steuercents stimmen nicht überein.',502);
  return value;
}
function capacityDate(value) { if(value!==null)refundDate(value); }
function capacityAmount(value,segment=true) { capacityMoney(value);capacityDate(value.not_before_date);if(segment&&value.segment_id!==null)accountingId(value.segment_id,true);return value; }
export function capacityState(value) { componentState(value);refundDate(value.cash_date);return value; }
export function capacityPortion(value,eventId) {
  for(const name of ['portion_id','portion_state_hash','payload_sha256','pdf_sha256'])accountingId(value?.[name],true);
  accountingId(value.document_id);if(value.customer_id!==null)accountingId(value.customer_id);if(value.ownership_id!==null)accountingId(value.ownership_id);
  if(value.event_id!==eventId||!['original_allocation','additional_allocation'].includes(value.kind)||value.currency!=='EUR'||componentCents(value.amount)<=0n||typeof value.eligible!=='boolean'||!['c1','c2'].includes(value.writer)||![null,'document_legacy','takeover_and_document','document_current'].includes(value.action)||![null,'clear','unresolved'].includes(value.refund_status)||!Array.isArray(value.groups)||value.groups.length>500)throw new ApiError('Der Beleganteil und seine verfügbaren Beträge konnten nicht sicher gelesen werden.',502);
  if(value.eligible!==(value.action!==null)||(value.action==='document_legacy'&&value.writer!=='c1')||(['takeover_and_document','document_current'].includes(value.action)&&value.writer!=='c2')||(value.ownership_id!==null&&(value.writer!=='c2'||value.ownership_id!==value.document_id))||(value.action==='takeover_and_document'&&value.ownership_id!==null)||(value.action==='document_current'&&value.ownership_id===null))throw new ApiError('Der aktuelle Aufteilungsweg stimmt nicht mit dem Belegstand überein.',502);
  const seen=new Set();
  for(const group of value.groups) {
    accountingId(group.group_id,true);accountingId(group.group_state_hash,true);
    if(seen.has(group.group_id)||!['none','takeover','successor'].includes(group.transition)||typeof group.rate!=='string'||typeof group.category!=='string'||typeof group.reason!=='string')throw new ApiError('Die verfügbaren Beleggruppen konnten nicht sicher gelesen werden.',502);seen.add(group.group_id);
    capacityMoney(group.archive);capacityAmount(group.current_capacity);capacityAmount(group.pending_returns,false);capacityAmount(group.offered_capacity);
    for(const field of ['net','tax','gross']) {
      const current=componentCents(group.current_capacity[field]),pending=componentCents(group.pending_returns[field]),offered=componentCents(group.offered_capacity[field]);
      if(offered!==current+(group.transition==='none'?0n:pending))throw new ApiError('Neue Rücknahmecents und vorhandener Rest wurden nicht getrennt ausgewiesen.',502);
    }
    if(group.transition==='none'&&(group.offered_capacity.segment_id!==group.current_capacity.segment_id||group.offered_capacity.not_before_date!==group.current_capacity.not_before_date))throw new ApiError('Der unveränderte Restabschnitt stimmt nicht überein.',502);
    if(group.transition!=='none'&&group.offered_capacity.segment_id===null)throw new ApiError('Der neue Restabschnitt konnte nicht sicher gelesen werden.',502);
  }
  return value;
}
export function capacityPreviewData(source,portion,groups,reason) {
  capacityState(source);capacityPortion(portion,source.event_id);
  if(source.source_kind!=='customer_receipt'||!source.eligible||!source.writes_allowed||!portion.eligible||!['takeover_and_document','document_current'].includes(portion.action))throw new Error('Diesen Beleganteil zuerst mit seinem aktuellen Aufteilungsweg neu laden.');
  if(portion.action==='takeover_and_document'&&portion.groups.some(group=>group.offered_capacity.not_before_date!==null&&source.cash_date<group.offered_capacity.not_before_date))throw new Error('Der Einnahmentag muss für die erstmalige Übernahme zu allen Rechnungsgruppen passen.');
  if(!Array.isArray(groups)||!groups.length||groups.length>500)throw new Error('Bitte mindestens eine positive Bruttoaufteilung ausdrücklich eingeben.');
  const seen=new Set();let total=0n;
  const selected=groups.map(item=>{
    const group=portion.groups.find(value=>value.group_id===item.group_id);
    if(!group||seen.has(item.group_id))throw new Error('Jede angebotene Beleggruppe nur einmal verwenden.');seen.add(item.group_id);
    const amount=accountingAmount(item.amount),cents=componentCents(amount),capacity=group.offered_capacity;
    if(cents>componentCents(capacity.gross)||capacity.not_before_date!==null&&source.cash_date<capacity.not_before_date)throw new Error('Der Betrag oder Einnahmentag passt nicht zum verfügbaren Rest dieser Gruppe.');total+=cents;
    return {group_id:item.group_id,amount};
  });
  if(total!==componentCents(portion.amount))throw new Error(`Die Gruppensumme muss genau dem ganzen Beleganteil von ${formatMoney(portion.amount)} entsprechen.`);
  return {source_hash:source.source_hash,expected_revision:source.revision,state_hash:source.state_hash,portion_id:portion.portion_id,portion_state_hash:portion.portion_state_hash,action:portion.action,groups:selected,reason:accountingText(reason,'Begründung',1000)};
}
function capacityLines(value) {
  componentEnvelope(value);capacityPortion(value.portion,value.event_id);
  if(!['takeover_and_document','document_current'].includes(value.action)||value.action!==value.portion.action||value.amount!==value.portion.amount||!Array.isArray(value.lines)||!value.lines.length||!Array.isArray(value.capacity_changes))throw new ApiError('Die Wiederbelegung konnte nicht sicher gelesen werden.',502);
  const seen=new Set();let gross=0n,net=0n,tax=0n;
  for(const line of value.lines) {
    const group=value.portion.groups.find(item=>item.group_id===line.group_id);
    if(!group||seen.has(line.group_id)||line.segment_id!==group.offered_capacity.segment_id)throw new ApiError('Eine Wiederbelegung verwendet keinen eindeutigen geprüften Restabschnitt.',502);seen.add(line.group_id);accountingId(line.segment_id,true);
    const amount=componentCents(line.amount),lineNet=componentCents(line.net),lineTax=componentCents(line.tax);
    if(amount<=0n||lineNet+lineTax!==amount)throw new ApiError('Die wiederbelegten Netto-/Steueranteile stimmen nicht überein.',502);
    for(const [field,delta]of [['gross',amount],['net',lineNet],['tax',lineTax]]) {
      if(componentCents(line[field+'_after'])-componentCents(line[field+'_before'])!==delta||componentCents(line['remaining_'+field])+delta!==componentCents(group.offered_capacity[field]))throw new ApiError('Die Restabschnittscents stimmen nicht mit der Aufteilung überein.',502);
      if(group.transition!=='none'&&componentCents(line[field+'_before'])!==0n)throw new ApiError('Ein neuer Restabschnitt muss bei null beginnen.',502);
    }
    for(const suffix of ['before','after'])if(componentCents(line['net_'+suffix])+componentCents(line['tax_'+suffix])!==componentCents(line['gross_'+suffix]))throw new ApiError('Die kumulierten Abschnittscents stimmen nicht überein.',502);
    const basisGross=componentCents(line.gross_before)+componentCents(group.offered_capacity.gross),basisTax=componentCents(line.tax_before)+componentCents(group.offered_capacity.tax),round=consumed=>(2n*consumed*basisTax+basisGross)/(2n*basisGross);
    if(round(componentCents(line.gross_before))!==componentCents(line.tax_before)||round(componentCents(line.gross_after))-componentCents(line.tax_before)!==lineTax)throw new ApiError('Die ausgewiesenen Steueranteile wurden nicht aus den tatsächlichen Abschnittscents berechnet.',502);
    gross+=amount;net+=lineNet;tax+=lineTax;
  }
  if(gross!==componentCents(value.amount)||net!==componentCents(value.net)||tax!==componentCents(value.tax))throw new ApiError('Die Wiederbelegung summiert sich nicht zum ganzen Beleganteil.',502);
  const changed=value.portion.groups.filter(item=>item.transition!=='none'),changes=new Set();
  if(value.capacity_changes.length!==changed.length)throw new ApiError('Die Vorschau zeigt nicht alle übernommenen Beleggruppen.',502);
  for(const change of value.capacity_changes) {
    const group=changed.find(item=>item.group_id===change.group_id);
    if(!group||changes.has(change.group_id)||change.previous_segment_id!==group.current_capacity.segment_id||change.segment_id!==group.offered_capacity.segment_id||change.not_before_date!==group.offered_capacity.not_before_date)throw new ApiError('Der gezeigte Kapazitätswechsel gehört nicht zum geprüften Belegstand.',502);changes.add(change.group_id);
    capacityMoney(change.carry);capacityMoney(change.returned);capacityMoney(change.basis);
    for(const field of ['net','tax','gross'])if(change.carry[field]!==group.current_capacity[field]||change.returned[field]!==group.pending_returns[field]||change.basis[field]!==group.offered_capacity[field]||componentCents(change.carry[field])+componentCents(change.returned[field])!==componentCents(change.basis[field]))throw new ApiError('Übertrag und neu übernommene Rücknahmecents stimmen nicht überein.',502);
  }
  return value;
}
export function capacityPreview(value,body,source) {
  capacityLines(value);accountingId(value.preview_hash,true);
  if(value.event_id!==source.event_id||value.source_hash!==body.source_hash||value.expected_revision!==body.expected_revision||value.state_hash!==body.state_hash||value.action!==body.action||value.reason!==body.reason||value.portion.portion_id!==body.portion_id||value.portion.portion_state_hash!==body.portion_state_hash||value.lines.length!==body.groups.length||value.lines.some(line=>!body.groups.some(group=>group.group_id===line.group_id&&group.amount===line.amount)))throw new ApiError('Die Vorschau gehört nicht zur geprüften Wiederbelegung.',502);
  return value;
}
export function capacityConfirmData(body,preview,source,confirmation) {
  if(confirmation!==true)throw new Error('Bitte die Wiederbelegung und die gezeigten Kapazitätsänderungen gesondert bestätigen.');
  capacityPreview(preview,body,source);return {...body,groups:body.groups.map(item=>({...item})),preview_hash:preview.preview_hash,confirmation:true};
}
export async function componentPendingAuthorize(api,operation) {
  const match=/^\/business\/accounting\/components\/(v2\/)?events\/([0-9a-f]{32})\/confirm$/.exec(operation?.path||'');
  if(!match)throw new ApiError('Der ursprüngliche Aufteilungsweg konnte nicht sicher geprüft werden.',409);
  const source=(match[1]?capacityState:componentState)(await api.get(operation.path.slice(0,-'/confirm'.length)));
  if(source.event_id!==match[2])throw new ApiError('Der aktuelle Zahlungsnachweis gehört nicht zur offenen Bestätigung.',502);
  if(!source.writes_allowed)throw new ApiError('Bestätigungen sind derzeit gesperrt. Die unveränderte Anfrage bleibt offen.',423);
  return source;
}

export function refundAccess(capabilities,organization,value=null,online=true) {
  const components=componentAccess(capabilities,organization,null,online),available=components.available&&capabilities.features?.includes('accounting_refund_origins')===true&&capabilities.capabilities?.includes('business_accounting_refunds')===true;
  const read=available&&components.read;
  return {available,read,prepare:read&&components.prepare&&(value===null||value.writes_allowed===true&&value.eligible===true)};
}
function refundEnvelope(value) { componentEnvelope(value);if(value.capacity_released!==false)throw new ApiError('Der dokumentarische Erstattungsstand konnte nicht sicher gelesen werden.',502); }
function refundDate(value) { if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(Date.parse(value+'T12:00:00Z'))||new Date(value+'T12:00:00Z').toISOString().slice(0,10)!==value)throw new ApiError('Der bestätigte Zahlungstag konnte nicht sicher gelesen werden.',502);return value; }
export function refundState(value) {
  refundEnvelope(value);accountingId(value.event_id);accountingId(value.source_hash,true);accountingId(value.state_hash,true);accountingRevision(value.revision,true);refundDate(value.cash_date);
  if(value.currency!=='EUR'||!['customer_refund','customer_receipt','supplier_payout'].includes(value.source_kind)||typeof value.eligible!=='boolean'||typeof value.writes_allowed!=='boolean'||componentCents(value.amount)<=0n||componentCents(value.origin_documented_amount)+componentCents(value.origin_unresolved_amount)!==componentCents(value.amount)||componentCents(value.unallocated_amount)>componentCents(value.origin_unresolved_amount))throw new ApiError('Die dokumentierten Erstattungsbeträge stimmen nicht überein.',502);
  return value;
}
export function refundPortion(value,eventId) {
  for(const name of ['portion_id','portion_state_hash','payload_sha256','pdf_sha256'])accountingId(value?.[name],true);
  accountingId(value.document_id);if(value.customer_id!==null)accountingId(value.customer_id);
  if(value.event_id!==eventId||value.kind!=='original_refund_allocation'||value.currency!=='EUR'||typeof value.eligible!=='boolean'||componentCents(value.amount)<=0n)throw new ApiError('Der ganze Erstattungsanteil konnte nicht sicher gelesen werden.',502);
  return value;
}
function refundLotKey(value) { return accountingId(value.entry_id)+':'+accountingId(value.group_id,true); }
function refundGroup(value) {
  accountingRevision(value.component_sequence);accountingId(value.origin_event_id);
  if(typeof value.rate!=='string'||!/^\d+(?:\.\d+)?$/.test(value.rate)||typeof value.category!=='string'||typeof value.tax_reason!=='string')throw new ApiError('Die ursprüngliche Beleggruppe konnte nicht sicher gelesen werden.',502);
}
export function refundOrigin(value,portion,cashDate) {
  refundLotKey(value);refundGroup(value);accountingId(value.lot_state_hash,true);refundDate(value.cash_date);
  if(value.currency!=='EUR'||value.document_id!==portion.document_id||value.customer_id!==portion.customer_id||value.cash_date>cashDate||componentCents(value.amount)<=0n)throw new ApiError('Der angebotene Ursprung passt nicht zu Rechnung, Kunde und Erstattungstag.',502);
  for(const prefix of ['', 'returned_', 'remaining_'])if(componentCents(value[prefix+'net'])+componentCents(value[prefix+'tax'])!==componentCents(value[prefix+'amount']))throw new ApiError('Die ursprünglichen Netto-/Steueranteile stimmen nicht überein.',502);
  for(const name of ['amount','net','tax'])if(componentCents(value['returned_'+name])+componentCents(value['remaining_'+name])!==componentCents(value[name]))throw new ApiError('Der verfügbare Ursprungsrest stimmt nicht überein.',502);
  return value;
}
export function refundPreviewData(source,portion,choices,reason) {
  refundState(source);refundPortion(portion,source.event_id);
  if(source.source_kind!=='customer_refund'||!source.eligible||!source.writes_allowed||!portion.eligible)throw new Error('Dieser Erstattungsanteil benötigt eine erneute Prüfung.');
  if(!Array.isArray(choices)||!choices.length||choices.length>500)throw new Error('Bitte mindestens einen Ursprung ausdrücklich mit positivem Betrag wählen.');
  const seen=new Set();let total=0n;
  const origins=choices.map(({origin,amount:input})=>{
    refundOrigin(origin,portion,source.cash_date);const key=refundLotKey(origin);if(seen.has(key))throw new Error('Jede ursprüngliche Aufteilung und Beleggruppe nur einmal wählen.');seen.add(key);
    const amount=accountingAmount(input),cents=componentCents(amount);if(cents>componentCents(origin.remaining_amount))throw new Error('Ein Betrag überschreitet den verfügbaren Rest dieses Ursprungs.');total+=cents;
    return {entry_id:origin.entry_id,group_id:origin.group_id,lot_state_hash:origin.lot_state_hash,amount};
  });
  if(total!==componentCents(portion.amount))throw new Error(`Die Ursprungssumme muss genau dem ganzen Erstattungsanteil von ${formatMoney(portion.amount)} entsprechen.`);
  return {source_hash:source.source_hash,expected_revision:source.revision,state_hash:source.state_hash,portion_id:portion.portion_id,portion_state_hash:portion.portion_state_hash,origins,reason:accountingText(reason,'Begründung',1000)};
}
function refundLines(value) {
  refundEnvelope(value);refundPortion(value.portion,value.event_id);refundDate(value.cash_date);
  if(value.amount!==value.portion.amount||!Array.isArray(value.lines)||!value.lines.length||value.lines.length>500)throw new ApiError('Die Ursprungsbindung konnte nicht sicher gelesen werden.',502);
  let gross=0n,net=0n,tax=0n;const seen=new Set();
  for(const line of value.lines) {
    const key=refundLotKey(line);refundGroup(line);accountingId(line.lot_state_hash,true);refundDate(line.origin_cash_date);
    if(seen.has(key)||line.origin_cash_date>value.cash_date)throw new ApiError('Die Ursprungslinien sind nicht eindeutig oder zeitlich unzulässig.',502);seen.add(key);
    const amount=componentCents(line.amount),lineNet=componentCents(line.net),lineTax=componentCents(line.tax);
    if(amount<=0n||lineNet+lineTax!==amount)throw new ApiError('Die dokumentierten Rücknahmecents stimmen nicht überein.',502);
    for(const [field,delta]of [['gross',amount],['net',lineNet],['tax',lineTax]])if(componentCents(line[field+'_after'])-componentCents(line[field+'_before'])!==delta)throw new ApiError('Die Rücknahmestände stimmen nicht überein.',502);
    for(const suffix of ['before','after'])if(componentCents(line['net_'+suffix])+componentCents(line['tax_'+suffix])!==componentCents(line['gross_'+suffix]))throw new ApiError('Die kumulierten Rücknahmecents stimmen nicht überein.',502);
    if(componentCents(line.remaining_net)+componentCents(line.remaining_tax)!==componentCents(line.remaining_gross))throw new ApiError('Die verbleibenden Ursprungscents stimmen nicht überein.',502);
    gross+=amount;net+=lineNet;tax+=lineTax;
  }
  if(gross!==componentCents(value.amount)||net!==componentCents(value.net)||tax!==componentCents(value.tax))throw new ApiError('Die Ursprungsbindung summiert sich nicht zum ganzen Erstattungsanteil.',502);
  return value;
}
export function refundPreview(value,body,source,choices) {
  refundLines(value);accountingId(value.preview_hash,true);
  if(value.event_id!==source.event_id||value.source_hash!==body.source_hash||value.expected_revision!==body.expected_revision||value.state_hash!==body.state_hash||value.cash_date!==source.cash_date||value.evidence_reference!==source.evidence_reference||value.reference!==source.reference||value.reason!==body.reason||value.portion.portion_id!==body.portion_id||value.portion.portion_state_hash!==body.portion_state_hash||value.lines.length!==body.origins.length)throw new ApiError('Die Vorschau gehört nicht zur geprüften Erstattungsanfrage.',502);
  for(const line of value.lines) {
    const selected=body.origins.find(item=>refundLotKey(item)===refundLotKey(line)),origin=choices.find(item=>refundLotKey(item.origin)===refundLotKey(line))?.origin;
    if(!selected||!origin||line.amount!==selected.amount||line.lot_state_hash!==selected.lot_state_hash||line.origin_event_id!==origin.origin_event_id||line.origin_cash_date!==origin.cash_date||line.origin_evidence_reference!==origin.evidence_reference||line.origin_reference!==origin.reference||['component_sequence','rate','category','tax_reason'].some(name=>line[name]!==origin[name]))throw new ApiError('Die Vorschau hat einen gewählten Ursprung verändert.',502);
    for(const [field,name]of [['gross','amount'],['net','net'],['tax','tax']])if(componentCents(line[field+'_before'])!==componentCents(origin['returned_'+name])||componentCents(line[field+'_after'])+componentCents(line['remaining_'+field])!==componentCents(origin[name]))throw new ApiError('Die Vorschau hat die geprüften Ursprungscents verändert.',502);
  }
  return value;
}
export function refundConfirmData(body,preview,source,choices,confirmation) {
  if(confirmation!==true)throw new Error('Bitte die geprüfte Ursprungsbindung gesondert bestätigen.');
  refundPreview(preview,body,source,choices);return {...body,origins:body.origins.map(item=>({...item})),preview_hash:preview.preview_hash,confirmation:true};
}
export async function refundAuthorize(api,eventId,origins,{versioned=false,selection=false}={}) {
  // The refund state also authorizes every already bound origin, including
  // later project extensions which are absent from the original cash event.
  const bound=refundState(await api.get('/business/accounting/refunds/events/'+accountingId(eventId)));
  if(bound.event_id!==eventId)throw new ApiError('Der aktuelle Ursprungsstand gehört nicht zur Erstattung.',502);
  if(versioned) {
    if(selection&&!bound.writes_allowed)throw new ApiError('Die Erstattung ist für eine neue Bindung gesperrt.',423);
    for(const id of new Set(origins.map(item=>accountingId(item.origin_event_id)))) {
      const source=capacityState(await api.get('/business/accounting/components/v2/events/'+id));
      if(source.event_id!==id)throw new ApiError('Der aktuelle Zahlungsnachweis stimmt nicht mit dem Ursprung überein.',502);
      if(selection&&!source.writes_allowed)throw new ApiError('Die vollständige Zahlungsquelle ist für eine neue Bindung gesperrt.',423);
    }
    return;
  }
  const ids=[...new Set([accountingId(eventId),...origins.map(item=>accountingId(item.origin_event_id))])];
  for(const id of ids){const event=await api.get('/business/accounting/events/'+id);if(event.id!==id)throw new ApiError('Der aktuelle Zahlungsnachweis stimmt nicht mit dem Ursprung überein.',502);}
}
export function refundOriginLabel(value) { return `Dokumentierte Aufteilung ${value.component_sequence} · ${componentGroupLabel({rate:value.rate,category:value.category,reason:value.tax_reason})}`; }
export function refundV2Access(capabilities,organization,value=null,online=true) {
  const capacity=capacityAccess(capabilities,organization,null,online),available=capacity.available&&capabilities.features?.includes('accounting_refund_origins_v2')===true&&capabilities.capabilities?.includes('business_accounting_refunds_v2')===true;
  const read=available&&capacity.read;return {available,read,prepare:read&&capacity.prepare&&(value===null||value.writes_allowed===true&&value.eligible===true)};
}
export function refundPendingKey(eventId) { return 'refund-confirm-'+accountingId(eventId); }
export function refundPendingOperation(operations,eventId) {
  accountingId(eventId);return operations.find(item=>item.path===`/business/accounting/refunds/events/${eventId}/confirm`||item.path===`/business/accounting/refunds/v2/events/${eventId}/confirm`)||null;
}
export function refundV2State(value) { return refundState(value); }
export function refundV2Portion(value,eventId) {
  refundPortion(value,eventId);
  for(const field of ['capacity_ownership_id','ownership_id'])if(value[field]!==null&&accountingId(value[field])!==value.document_id)throw new ApiError('Die Rechnungsübernahme gehört nicht zum Erstattungsanteil.',502);
  const expected=value.capacity_ownership_id===null?['r1','bind_legacy']:value.ownership_id===null?['r2','takeover_and_bind']:['r2','bind_current'];
  if(value.writer!==expected[0]||value.action!==(value.eligible?expected[1]:null)||value.ownership_id!==null&&value.capacity_ownership_id===null)throw new ApiError('Der aktuelle Zuordnungsweg stimmt nicht mit der Rechnung überein.',502);
  return value;
}
export function refundV2LotKey(value) {
  if(!['c1','c2'].includes(value?.origin_version))throw new ApiError('Die Art der ursprünglichen Aufteilung konnte nicht sicher gelesen werden.',502);
  return value.origin_version+':'+refundLotKey(value);
}
export function refundV2Origin(value,portion,cashDate) { refundV2LotKey(value);return refundOrigin(value,portion,cashDate); }
export function refundV2OriginLabel(value) { refundV2LotKey(value);return `${value.origin_version==='c1'?'Ursprüngliche Belegaufteilung':'Aufteilung mit wiederverwendeten Beträgen'} ${value.component_sequence} · ${componentGroupLabel({rate:value.rate,category:value.category,reason:value.tax_reason})}`; }
export function refundV2PreviewData(source,portion,choices,reason) {
  refundV2State(source);refundV2Portion(portion,source.event_id);
  if(source.source_kind!=='customer_refund'||!source.eligible||!source.writes_allowed||!portion.eligible||portion.writer!=='r2')throw new Error('Diesen Erstattungsanteil zuerst mit seinem aktuellen Zuordnungsweg neu laden.');
  if(!Array.isArray(choices)||!choices.length||choices.length>500)throw new Error('Bitte mindestens einen Ursprung ausdrücklich mit positivem Betrag wählen.');
  const seen=new Set();let total=0n;
  const origins=choices.map(({origin,amount:input})=>{
    refundV2Origin(origin,portion,source.cash_date);const key=refundV2LotKey(origin);if(seen.has(key))throw new Error('Jede angebotene ursprüngliche oder wiederverwendete Aufteilung nur einmal wählen.');seen.add(key);
    const amount=accountingAmount(input),cents=componentCents(amount);if(cents>componentCents(origin.remaining_amount))throw new Error('Ein Betrag überschreitet den verfügbaren Rest dieses Ursprungs.');total+=cents;
    return {origin_version:origin.origin_version,entry_id:origin.entry_id,group_id:origin.group_id,lot_state_hash:origin.lot_state_hash,amount};
  });
  if(total!==componentCents(portion.amount))throw new Error(`Die Ursprungssumme muss genau dem ganzen Erstattungsanteil von ${formatMoney(portion.amount)} entsprechen.`);
  return {source_hash:source.source_hash,expected_revision:source.revision,state_hash:source.state_hash,portion_id:portion.portion_id,portion_state_hash:portion.portion_state_hash,action:portion.action,origins,reason:accountingText(reason,'Begründung',1000)};
}
function refundV2Lines(value) {
  refundEnvelope(value);refundV2Portion(value.portion,value.event_id);refundDate(value.cash_date);
  if(!['takeover_and_bind','bind_current'].includes(value.action)||value.action!==value.portion.action||value.amount!==value.portion.amount||!Array.isArray(value.lines)||!value.lines.length||value.lines.length>500)throw new ApiError('Die ganze Ursprungsbindung konnte nicht sicher gelesen werden.',502);
  const seen=new Set();let gross=0n,net=0n,tax=0n;
  for(const line of value.lines) {
    const key=refundV2LotKey(line);refundGroup(line);accountingId(line.lot_state_hash,true);refundDate(line.origin_cash_date);
    if(seen.has(key)||line.origin_cash_date>value.cash_date)throw new ApiError('Die Ursprungslinien sind nicht eindeutig oder zeitlich unzulässig.',502);seen.add(key);
    const amount=componentCents(line.amount),lineNet=componentCents(line.net),lineTax=componentCents(line.tax);
    if(amount<=0n||lineNet+lineTax!==amount)throw new ApiError('Die dokumentierten Rücknahmecents stimmen nicht überein.',502);
    for(const [field,delta]of [['gross',amount],['net',lineNet],['tax',lineTax]])if(componentCents(line[field+'_after'])-componentCents(line[field+'_before'])!==delta)throw new ApiError('Die vollständigen bisherigen Rücknahmestände stimmen nicht überein.',502);
    for(const suffix of ['before','after'])if(componentCents(line['net_'+suffix])+componentCents(line['tax_'+suffix])!==componentCents(line['gross_'+suffix]))throw new ApiError('Die kumulierten Rücknahmecents stimmen nicht überein.',502);
    if(componentCents(line.remaining_net)+componentCents(line.remaining_tax)!==componentCents(line.remaining_gross))throw new ApiError('Der genaue verbleibende Ursprungsrest stimmt nicht überein.',502);
    const basisGross=componentCents(line.gross_after)+componentCents(line.remaining_gross),basisTax=componentCents(line.tax_after)+componentCents(line.remaining_tax),round=consumed=>(2n*consumed*basisTax+basisGross)/(2n*basisGross);
    if(round(componentCents(line.gross_before))!==componentCents(line.tax_before)||round(componentCents(line.gross_after))-componentCents(line.tax_before)!==lineTax)throw new ApiError('Die Rücknahme wurde nicht aus der vollständigen ursprünglichen Lotbasis berechnet.',502);
    gross+=amount;net+=lineNet;tax+=lineTax;
  }
  if(gross!==componentCents(value.amount)||net!==componentCents(value.net)||tax!==componentCents(value.tax))throw new ApiError('Die Ursprungssumme stimmt nicht mit dem ganzen Erstattungsanteil überein.',502);
  return value;
}
export function refundV2Preview(value,body,source,choices) {
  refundV2Lines(value);accountingId(value.preview_hash,true);
  if(value.event_id!==source.event_id||value.source_hash!==body.source_hash||value.expected_revision!==body.expected_revision||value.state_hash!==body.state_hash||value.action!==body.action||value.cash_date!==source.cash_date||value.evidence_reference!==source.evidence_reference||value.reference!==source.reference||value.reason!==body.reason||value.portion.portion_id!==body.portion_id||value.portion.portion_state_hash!==body.portion_state_hash||value.lines.length!==body.origins.length)throw new ApiError('Die Vorschau gehört nicht zur geprüften Erstattungsanfrage.',502);
  for(const line of value.lines) {
    const selected=body.origins.find(item=>refundV2LotKey(item)===refundV2LotKey(line)),origin=choices.find(item=>refundV2LotKey(item.origin)===refundV2LotKey(line))?.origin;
    if(!selected||!origin||line.amount!==selected.amount||line.lot_state_hash!==selected.lot_state_hash||line.origin_event_id!==origin.origin_event_id||line.origin_cash_date!==origin.cash_date||line.origin_evidence_reference!==origin.evidence_reference||line.origin_reference!==origin.reference||['component_sequence','rate','category','tax_reason'].some(name=>line[name]!==origin[name]))throw new ApiError('Die Vorschau hat einen gewählten Ursprung verändert.',502);
    for(const [field,name]of [['gross','amount'],['net','net'],['tax','tax']])if(componentCents(line[field+'_before'])!==componentCents(origin['returned_'+name])||componentCents(line[field+'_after'])+componentCents(line['remaining_'+field])!==componentCents(origin[name]))throw new ApiError('Die Vorschau hat die ursprüngliche Lotbasis oder bisherige Rücknahme verändert.',502);
  }
  return value;
}
export function refundV2ConfirmData(body,preview,source,choices,confirmation) {
  if(confirmation!==true)throw new Error('Bitte die gewählten Ursprünge des ganzen Erstattungsanteils gesondert bestätigen.');
  refundV2Preview(preview,body,source,choices);return {...body,origins:body.origins.map(item=>({...item})),preview_hash:preview.preview_hash,confirmation:true};
}
export async function refundPendingAuthorize(api,operation) {
  const match=/^\/business\/accounting\/refunds\/(v2\/)?events\/([0-9a-f]{32})\/confirm$/.exec(operation?.path||'');
  if(!match)throw new ApiError('Der ursprüngliche Erstattungsweg konnte nicht sicher geprüft werden.',409);
  const source=(match[1]?refundV2State:refundState)(await api.get(operation.path.slice(0,-'/confirm'.length)));
  if(source.event_id!==match[2])throw new ApiError('Die offene Anfrage gehört nicht zum aktuellen Erstattungsnachweis.',502);
  if(!source.writes_allowed)throw new ApiError('Bestätigungen sind derzeit gesperrt. Die unveränderte Anfrage bleibt offen.',423);
  return source;
}
export async function refundV2Authorize(api,eventId,origins,{selection=false}={}) {
  const source=refundV2State(await api.get('/business/accounting/refunds/v2/events/'+accountingId(eventId)));
  if(source.event_id!==eventId)throw new ApiError('Der aktuelle Erstattungsstand gehört nicht zum gewählten Nachweis.',502);
  if(selection&&!source.writes_allowed)throw new ApiError('Neue Ursprungsauswahlen sind derzeit gesperrt.',423);
  for(const id of [...new Set(origins.map(item=>accountingId(item.origin_event_id)))]) {
    const positive=capacityState(await api.get('/business/accounting/components/v2/events/'+id));
    if(positive.event_id!==id)throw new ApiError('Der aktuelle Ursprung gehört nicht zur gewählten Aufteilung.',502);
    if(selection&&!positive.writes_allowed)throw new ApiError('Für einen gewählten Ursprung fehlen aktuelle Schreibrechte.',423);
  }
  return source;
}

function purchaseDecimal(value) {
  const text=decimalText(value),negative=text.startsWith('-'),[whole,fraction='']=text.replace(/^-/,'').split('.');
  return {text,scaled:BigInt(whole+fraction.padEnd(4,'0'))*(negative?-1n:1n)};
}
function purchaseRevision(order) {
  if(!Number.isSafeInteger(order?.source_revision)||order.source_revision<1||
      !Number.isSafeInteger(order?.receipt_revision)||order.receipt_revision<0)
    throw new ApiError('Die Bestellung zuerst neu laden.',502);
  return {source_revision:order.source_revision,expected_receipt_revision:order.receipt_revision};
}
export function purchaseActions(order,capabilities,organization) {
  const permissions=new Set(capabilities.permissions||[]),
    writable=capabilities.readonly===false&&organizationModuleEnabled('material',organization)&&permissions.has('inventory.write');
  return {edit:writable&&order.status==='proposal',approve:writable&&order.status==='proposal'&&permissions.has('finance.approve'),
    confirm:writable&&order.status==='approved'&&permissions.has('finance.approve'),
    receive:writable&&['ordered','partially_received'].includes(order.status)&&permissions.has('finance.write'),
    costs:permissions.has('finance.read')};
}
export function portalAccess(item,capabilities,organization){
  const permissions=new Set(capabilities.permissions||[]),read=item.kind==='offer'&&item.status==='final'&&
    (capabilities.features||[]).includes('offer_portal')&&permissions.has('portal.manage')&&permissions.has('finance.read'),
    write=read&&capabilities.readonly===false&&organizationModuleEnabled('documents',organization);
  return {read,revoke:read,create:write,adopt:write&&permissions.has('finance.write')&&permissions.has('projects.manage')};
}
function portalSource(source){
  if(!source||!/^[a-f0-9]{32}$/.test(source.offer_id||'')||!Number.isSafeInteger(source.source_revision)||source.source_revision<1||
      !/^[a-f0-9]{64}$/.test(source.content_hash||'')||!/^[a-f0-9]{64}$/.test(source.pdf_hash||''))throw new ApiError('Die geprüfte Angebotsfassung zuerst neu laden.',502);
  return {offer_id:source.offer_id,source_revision:source.source_revision,content_hash:source.content_hash,pdf_hash:source.pdf_hash};
}
export function portalGrantData(source,values){
  const recipient_name=String(values.recipient_name||'').trim(),recipient_email=String(values.recipient_email||'').trim();
  if(!recipient_name||recipient_name.length>200||!/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(recipient_email)||recipient_email.length>254||
      !Number.isInteger(values.expires_in_days)||values.expires_in_days<1||values.expires_in_days>30||values.confirmation!==true)
    throw new Error('Empfänger, E-Mail, Zugangsdauer (1–30 Tage) und ausdrückliche Freigabe prüfen.');
  return {...portalSource(source),recipient_name,recipient_email,expires_in_days:values.expires_in_days,confirmation:true};
}
export function portalAdoptionData(source,decision,confirmation){
  const bound=portalSource(source);
  if(!decision||decision.decision!=='accepted'||decision.offer_id!==bound.offer_id||!/^[a-f0-9]{32}$/.test(decision.id||'')||
      decision.content_hash!==bound.content_hash||decision.pdf_hash!==bound.pdf_hash||confirmation!==true)throw new Error('Zuerst die Annahme der unveränderten Angebotsfassung prüfen und ausdrücklich bestätigen.');
  const {offer_id,...fields}=bound;return {...fields,decision_id:decision.id,confirmation:true};
}
export function portalIssuedLink(result,hostname){
  if(!/^[a-f0-9]{32}$/.test(result?.grant?.id||''))throw new ApiError('Die Freigabe konnte nicht sicher gelesen werden. Angebotsportal erneut öffnen.',502);
  if(result?.link_available===false)return null;
  let url;try{url=new URL(result?.portal_url);}catch{throw new ApiError('Der Zugang wurde angelegt, der Link aber nicht sicher bestätigt. Freigabe prüfen und bei Bedarf widerrufen.',502);}
  const fragment=new URLSearchParams(url.hash.slice(1));
  if(result.link_available!==true||url.origin!=='https://'+hostname||url.username||url.password||url.pathname!=='/office/portal.html'||url.search||
      fragment.size!==2||fragment.getAll('grant').length!==1||fragment.getAll('key').length!==1||fragment.get('grant')!==result.grant?.id||
      !/^[a-f0-9]{32}$/.test(fragment.get('grant')||'')||!/^SPPI_[A-Za-z0-9_-]{43,195}$/.test(fragment.get('key')||''))
    throw new ApiError('Der Zugang wurde angelegt, der Link aber nicht sicher bestätigt. Freigabe prüfen und bei Bedarf widerrufen.',502);
  return url.href;
}
function purchaseArticle(item) {
  if(!item||typeof item.id!=='string'||typeof item.name!=='string'||typeof item.unit!=='string')
    throw new ApiError('Die Einkaufsartikel konnten nicht gelesen werden.',502);
  return {id:item.id,revision:item.revision,code:item.code||'',name:item.name,kind:item.kind,unit:item.unit,active:item.active,...(item.price_policy==='dated_catalog'?{price_policy:item.price_policy}:{}),...(item.catalog_price_required?{catalog_price_required:true}:{})};
}
export class PurchaseCatalog {
  constructor({fetcher,enabled=false,projectId=null,items=[],selected=[]}) {
    this.fetcher=fetcher;this.enabled=enabled;this.projectId=projectId||null;this.generation=0;
    this.known=new Map();this.items=[];this.total=0;this.nextOffset=null;this.query='';
    this.fallback=items.filter(item=>item.active!==false&&item.active!==0&&(!item.kind||['material','machine'].includes(item.kind))).map(purchaseArticle);
    for(const item of [...this.fallback,...selected.map(purchaseArticle)])this.known.set(item.id,item);
  }
  setProject(value) { if((value||null)===this.projectId)return;this.projectId=value||null;this.generation++;this.items=[];this.nextOffset=null; }
  choices(selectedId) {
    const result=[...this.items],selected=this.known.get(selectedId);
    if(selected&&!result.some(item=>item.id===selectedId))result.push(selected);
    return result;
  }
  async load(search='',append=false) {
    const text=String(search).trim();append=append&&text===this.query;const offset=append?this.nextOffset:0;
    if(offset===null)return false;
    const generation=++this.generation,limit=25;
    let page;
    if(this.enabled) {
      page=await this.fetcher(query('/business/purchasing/articles',{project_id:this.projectId,query:text,limit,offset}));
      if(generation!==this.generation)return false;
      if(!page||!Array.isArray(page.items)||page.items.length>limit||!Number.isSafeInteger(page.total)||page.total<page.items.length||
          !(page.next_offset===null||(Number.isSafeInteger(page.next_offset)&&page.next_offset>offset&&page.next_offset<page.total)))
        throw new ApiError('Die Einkaufssuche zuerst erneut laden.',502);
    }else{
      const needle=text.toLocaleLowerCase('de-DE'),items=this.fallback.filter(item=>(item.code+' '+item.name).toLocaleLowerCase('de-DE').includes(needle));
      page={items:items.slice(offset,offset+limit),total:items.length,next_offset:offset+limit<items.length?offset+limit:null};
    }
    const items=page.items.map(purchaseArticle);
    if(generation!==this.generation)return false;
    this.items=Array.from(new Map([...(append?this.items:[]),...items].map(item=>[item.id,item])).values());
    for(const item of items)this.known.set(item.id,item);
    this.total=page.total;this.nextOffset=page.next_offset;this.query=text;return true;
  }
}
export function purchaseConfirmationData(order,values) {
  if(order.status!=='approved'||order.confirmation)throw new Error('Zuerst den Bestellvorschlag freigeben und die Bestellung neu laden.');
  if(values.confirmation!==true)throw new Error('Bitte die bereits extern erteilte Bestellung ausdrücklich bestätigen.');
  if((order.items||[]).some(item=>item.catalog_price_snapshot&&item.catalog_price_snapshot.effective_on!==values.ordered_on))throw new Error('Tatsächliches Bestelldatum muss zum ausdrücklich gewählten Katalogpreisstand passen.');
  const order_reference=String(values.order_reference||'').trim();
  if(!order_reference)throw new Error('Bitte eine Bestellreferenz angeben.');
  calendarDay(values.ordered_on);
  return {...purchaseRevision(order),order_reference,ordered_on:values.ordered_on,confirmation:true};
}
export function purchaseReceiptData(order,values) {
  if(!['ordered','partially_received'].includes(order.status)||!order.confirmation)
    throw new Error('Zuerst die extern erteilte Bestellung dokumentieren.');
  const receipt_reference=String(values.receipt_reference||'').trim();
  if(!receipt_reference||!values.location_id)throw new Error('Bitte Lieferscheinreferenz und Ziellager angeben.');
  calendarDay(values.received_on);
  if(values.received_on<order.confirmation.ordered_on)throw new Error('Das Lieferdatum darf nicht vor dem dokumentierten Bestelldatum liegen.');
  const indices=new Set(),lines=[];
  if(!Array.isArray(order.items)||!order.items.length)throw new ApiError('Die Bestellpositionen zuerst neu laden.',502);
  for(const item of order.items) {
    if(!Number.isSafeInteger(item.line_index)||item.line_index<0||indices.has(item.line_index))
      throw new ApiError('Die Bestellpositionen zuerst neu laden.',502);
    indices.add(item.line_index);
    const raw=values['quantity_'+item.line_index],cost=values['cost_'+item.line_index];
    if(raw===undefined||String(raw).trim()==='') {
      if(cost!==undefined&&String(cost).trim()!=='')throw new Error('Bitte zur eingetragenen Kostenangabe auch eine Liefermenge angeben.');
      continue;
    }
    const quantity=purchaseDecimal(raw),remaining=purchaseDecimal(item.remaining_quantity);
    if(quantity.scaled<0n||quantity.scaled>remaining.scaled)throw new Error('Die Liefermenge muss zwischen null und der noch offenen Menge liegen.');
    if(quantity.scaled===0n)continue;
    if(cost===undefined||cost===null||String(cost).trim()==='')throw new Error('Bitte den bestätigten Einstandspreis jeder gelieferten Position eingeben; einen Nullpreis ausdrücklich als 0.');
    const price=purchaseDecimal(cost);
    if(price.scaled<0n)throw new Error('Einstandspreise dürfen nicht negativ sein.');
    lines.push({line_index:item.line_index,quantity:quantity.text,unit_cost_net:price.text});
  }
  if(!lines.length)throw new Error('Bitte mindestens eine tatsächlich gelieferte Menge eingeben.');
  return {...purchaseRevision(order),...(Number.isSafeInteger(order.amendment_revision)?{expected_amendment_revision:order.amendment_revision}:{}),receipt_reference,received_on:values.received_on,location_id:values.location_id,lines};
}
const DAY_MS=86400000;
function calendarDay(value) {
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))throw new Error('Gültiges Kalenderdatum erwartet.');
  const [year,month,day]=value.split('-').map(Number),date=new Date(Date.UTC(year,month-1,day));
  if(year<1900||year>2200||date.toISOString().slice(0,10)!==value)throw new Error('Gültiges Kalenderdatum zwischen 1900 und 2200 erwartet.');
  return date;
}
const utcDate=date=>date.toISOString().slice(0,10);
export function planningRange(mode,anchor,years=3) {
  const day=calendarDay(anchor),year=day.getUTCFullYear(),month=day.getUTCMonth();let from,to;
  if(mode==='week'){from=new Date(day.getTime()-((day.getUTCDay()+6)%7)*DAY_MS);to=new Date(from.getTime()+6*DAY_MS);}
  else if(mode==='month'){from=new Date(Date.UTC(year,month,1));to=new Date(Date.UTC(year,month+1,0));}
  else if(mode==='year'){from=new Date(Date.UTC(year,0,1));to=new Date(Date.UTC(year,11,31));}
  else if(mode==='multi'&&[2,3].includes(years)&&year+years-1<=2200){from=new Date(Date.UTC(year,0,1));to=new Date(Date.UTC(year+years-1,11,31));}
  else throw new Error('Woche, Monat, Jahr oder zwei bis drei Jahre auswählen.');
  if(from.getUTCFullYear()<1900||to.getUTCFullYear()>2200)throw new Error('Dieser Zeitraum liegt außerhalb der Datumsauswahl 1900 bis 2200.');
  return {from:utcDate(from),to:utcDate(to),days:Math.round((to-from)/DAY_MS)+1};
}
export function shiftPlanningAnchor(mode,anchor,direction,years=3) {
  if(![-1,1].includes(direction))throw new Error('Ungültige Zeitraumnavigation.');
  const day=calendarDay(anchor),year=day.getUTCFullYear(),month=day.getUTCMonth();
  const moved=mode==='week'?new Date(day.getTime()+direction*7*DAY_MS):mode==='month'?new Date(Date.UTC(year,month+direction,1)):
    ['year','multi'].includes(mode)?new Date(Date.UTC(year+direction*(mode==='multi'?years:1),0,1)):null;
  if(!moved)throw new Error('Ungültige Planungsansicht.');
  const value=utcDate(moved);planningRange(mode,value,years);return value;
}
export function timelinePlacement(item,range) {
  try {
    const start=calendarDay(item.start_date),end=calendarDay(item.end_date),first=calendarDay(range.from),last=calendarDay(range.to);
    if(end<start||last<first||end<first||start>last)return null;
    const visibleStart=Math.max(start,first),visibleEnd=Math.min(end,last),days=Math.round((last-first)/DAY_MS)+1;
    return {left:(visibleStart-first)/DAY_MS/days*100,width:((visibleEnd-visibleStart)/DAY_MS+1)/days*100,
      clippedStart:start<first,clippedEnd:end>last};
  } catch{return null;}
}
export function planningTicks(mode,range) {
  const first=calendarDay(range.from),last=calendarDay(range.to),daily=['week','month'].includes(mode),ticks=[];
  for(let day=new Date(first);day<=last;day=daily?new Date(day.getTime()+DAY_MS):new Date(Date.UTC(day.getUTCFullYear(),day.getUTCMonth()+1,1))) {
    const end=daily?new Date(day.getTime()+DAY_MS):new Date(Date.UTC(day.getUTCFullYear(),day.getUTCMonth()+1,1));
    ticks.push({date:utcDate(day),left:(day-first)/DAY_MS/range.days*100,width:Math.min((end-day)/DAY_MS,range.days-(day-first)/DAY_MS)/range.days*100,
      label:new Intl.DateTimeFormat('de-DE',{timeZone:'UTC',...(mode==='week'?{weekday:'short',day:'2-digit'}:mode==='month'?{day:'2-digit'}:{month:'short',year:'numeric'})}).format(day)});
  }
  return ticks;
}

export class OfficeApi {
  #token = ''; #generation = 0; #controllers = new Set(); #pending = new Map();
  constructor({fetcher = globalThis.fetch, base = '/api/v1'} = {}) {
    if (base !== '/api/v1') throw new Error('Nur die eigene Office-API ist erlaubt.');
    this.fetcher = fetcher.bind(globalThis); this.base = base;
  }
  get generation() { return this.#generation; }
  get pendingCount() { return this.#pending.size; }
  pendingOperations() { return [...this.#pending.entries()].map(([key,operation])=>({key,path:operation.path})); }
  pendingCommandValues(key, path) {
    const operation=this.#pending.get(key);
    return operation&&operation.path===path?JSON.parse(operation.fingerprint):null;
  }
  retry(key, options = {}) {
    const operation=this.#pending.get(key);
    if(!operation)throw new ApiError('Vorgang ist nicht mehr offen.');
    return this.mutate(key,operation.path,JSON.parse(operation.fingerprint),options);
  }
  setToken(token) {
    if (typeof token !== 'string' || token.length < 20 || token.length > 200) throw new Error('Ungültige Sitzung.');
    this.clear(); this.#token = token;
  }
  clear() {
    this.#generation++;
    this.#controllers.forEach(controller => controller.abort());
    this.#controllers.clear(); this.#pending.clear(); this.#token = '';
  }
  async request(path, {method = 'GET', body, publicRequest = false, binary = false, maxBytes} = {}) {
    if (typeof path !== 'string' || !path.startsWith('/') || path.startsWith('//') || path.includes('#') || /[\r\n]/.test(path)) throw new Error('Ungültiger API-Pfad.');
    const bankJson = /^\/business\/bank\/(?:accounts|import\/preview|statements(?:\/[a-f0-9]{32})?|transactions\/[a-f0-9]{32}\/(?:candidates|history|preview|matches)|reconciliations(?:\/preview|\/[a-f0-9]{32})?)$/.test(path.split('?')[0]);
    const datedJson=/^\/business\/catalog-prices\/(?:sources\/[a-f0-9]{32}\/imports|imports\/[a-f0-9]{32}(?:\/(?:apply|preview))?|prices\/[a-f0-9]{32}\/history|candidates)$/.test(path.split('?')[0]);
    const catalogJson=/^\/business\/adapters\/(?:[a-f0-9]{32}\/import|imports\/[a-f0-9]{32}(?:\/(?:apply|catalog-preview))?)$/.test(path.split('?')[0]);
    maxBytes ??= binary ? 21 * 1024 * 1024 : (bankJson ? 128 : catalogJson||datedJson ? 32 : 4) * 1024 * 1024;
    if (!publicRequest && !this.#token) throw new ApiError('Bitte anmelden.', 401);
    const generation = this.#generation, controller = new AbortController();
    this.#controllers.add(controller);
    const headers = {'Accept': binary ? '*/*' : 'application/json'};
    if (!publicRequest) headers.Authorization = 'Bearer ' + this.#token;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    try {
      const response = await this.fetcher(this.base + path, {method, headers, ...(body !== undefined ? {body: JSON.stringify(body)} : {}),
        signal: controller.signal, credentials: 'omit', redirect: 'error', cache: 'no-store', referrerPolicy: 'no-referrer'});
      if (generation !== this.#generation) throw new StaleSession();
      const advertised = Number(response.headers.get('Content-Length'));
      if (Number.isFinite(advertised) && advertised > maxBytes) {
        await response.body?.cancel();
        throw new ApiError('Antwort ist zu groß. Eine mögliche Übernahme ist noch nicht bestätigt.', 0);
      }
      const reader = response.body?.getReader();
      let data;
      if (reader) {
        let size = 0; const parts = [];
        for (;;) {
          const {done, value} = await reader.read(); if (done) break;
          if (generation !== this.#generation) { await reader.cancel(); throw new StaleSession(); }
          size += value.byteLength;
          if (size > maxBytes) { await reader.cancel(); throw new ApiError('Antwort ist zu groß. Eine mögliche Übernahme ist noch nicht bestätigt.', 0); }
          parts.push(value);
        }
        data = new Uint8Array(size); let offset = 0;
        parts.forEach(part => { data.set(part, offset); offset += part.byteLength; });
      } else {
        data = new Uint8Array(await response.arrayBuffer());
        if (data.byteLength > maxBytes) throw new ApiError('Antwort ist zu groß. Eine mögliche Übernahme ist noch nicht bestätigt.', 0);
      }
      if (generation !== this.#generation) throw new StaleSession();
      if (!response.ok) {
        let message = 'Anfrage fehlgeschlagen.',requestResolution=null;
        try { const error=JSON.parse(new TextDecoder().decode(data));message=error.error||message;if(response.status===409&&error.request_resolution==='not_accepted')requestResolution='not_accepted'; } catch { /* Do not expose HTML/proxy bodies. */ }
        throw new ApiError(message, response.status,requestResolution);
      }
      if (binary) return new Blob([data], {type: response.headers.get('Content-Type') || 'application/octet-stream'});
      try { return JSON.parse(new TextDecoder().decode(data)); } catch { throw new ApiError('Serverantwort ist nicht lesbar.', 502); }
    } catch (error) {
      if (generation !== this.#generation || error.name === 'AbortError') throw new StaleSession();
      if (error instanceof ApiError || error instanceof StaleSession) throw error;
      throw new ApiError('Keine sichere Antwort erhalten. Verbindung prüfen und dieselbe Eingabe erneut senden.');
    } finally { this.#controllers.delete(controller); }
  }
  get(path) { return this.request(path); }
  post(path, body) { return this.request(path, {method: 'POST', body}); }
  binary(path) { return this.request(path, {binary: true}); }
  async mutate(key, path, data, {validate=null,stillCurrent=null} = {}) {
    const fingerprint = JSON.stringify(data), old = this.#pending.get(key), generation = this.#generation;
    if (old && (old.path !== path || old.fingerprint !== fingerprint)) throw new ApiError('Die vorige Antwort ist noch unklar. Bitte zuerst die unveränderte Eingabe erneut senden.');
    const operation = old || {path, fingerprint, body: {...JSON.parse(fingerprint), request_id: requestId()}, validate};
    this.#pending.set(key, operation);
    try {
      if(old&&isStockReturn(key,path,operation.body))await stockReturnPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/catalog-prices/'))await datedPendingAuthorize(this,{key,path});
      if(old&&datedConsumerCommand(key,path,operation.body))await datedConsumerPendingAuthorize(this,{key,path});
      if(old&&documentTimeCommand(key,path,operation.body))await documentTimePendingAuthorize(this,{key,path});
      if(old&&key.startsWith('catalog-'))await catalogPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/assistant/'))await assistantPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/company-events/'))await companyEventPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/payroll/cash/'))await payrollCashPendingAuthorize(this,{key,path});
      if(old&&key.startsWith('purchase-change-')&&/^\/business\/purchasing\/orders\/[a-f0-9]{32}\/(?:change-files|amendments|supplier-returns)$/.test(path))await purchaseChangePendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/accounting/open-items'))await oiPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/accounting/historical-assets'))await assetPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/accounting/year-values'))await yvPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/accounting/opening-balances'))await openingPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/bank/'))await bankPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/resource-custody/'))await resourceCustodyPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/service/cases'))await servicePendingAuthorize(this,{key,path});
      if(old&&/^\/business\/maintenance\/contracts(?:\/[a-f0-9]{32})?$/.test(path))await maintenanceContractPendingAuthorize(this,{key,path});
      if(old&&path==='/business/payroll/facts'&&await payrollFactsPendingAuthorize(this,{key,path})!==true)throw new ApiError('Die offene Lohnanfrage konnte nicht eindeutig autorisiert werden.',403);
      if(old&&path==='/business/payroll/entitlements'&&await payrollEntitlementsPendingAuthorize(this,{key,path})!==true)throw new ApiError('Die offene Lohnanfrage konnte nicht eindeutig autorisiert werden.',403);
      if(old&&path==='/business/payroll/travel-tax-policies'&&await payrollTravelTaxPoliciesPendingAuthorize(this,{key,path})!==true)throw new ApiError('Die offene Lohnanfrage konnte nicht eindeutig autorisiert werden.',403);
      if(old&&path==='/business/payroll/calculation-cases'&&await payrollCalculationCasesPendingAuthorize(this,{key,path})!==true)throw new ApiError('Die offene Lohnanfrage konnte nicht eindeutig autorisiert werden.',403);
      if(old&&path==='/business/payroll/wage-interruptions'&&await payrollWageInterruptionsPendingAuthorize(this,{key,path})!==true)throw new ApiError('Die offene Lohnanfrage konnte nicht eindeutig autorisiert werden.',403);
      if(old&&path==='/business/payroll/annual-facts'&&await payrollAnnualPendingAuthorize(this,{key,path})!==true)throw new ApiError('Die offene Lohnanfrage konnte nicht eindeutig autorisiert werden.',403);
      if(old&&path==='/business/payroll/multiple-one-off-cases'&&await payrollMultipleCasesPendingAuthorize(this,{key,path})!==true)throw new ApiError('Die offene Monatsgruppenanfrage konnte nicht eindeutig autorisiert werden.',403);
      if(old&&path==='/business/payroll/one-off-cases'&&await payrollOneOffCasesPendingAuthorize(this,{key,path})!==true)throw new ApiError('Die offene Einmalbezugsanfrage konnte nicht eindeutig autorisiert werden.',403);
      if(old&&path.startsWith('/business/payroll/')&&!path.startsWith('/business/payroll/cash/')&&!['/business/payroll/facts','/business/payroll/entitlements','/business/payroll/travel-tax-policies','/business/payroll/calculation-cases','/business/payroll/wage-interruptions','/business/payroll/annual-facts','/business/payroll/one-off-cases','/business/payroll/multiple-one-off-cases'].includes(path))await payrollPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/sales/'))await salesPendingAuthorize(this,{key,path});
      if(old&&/^\/projects\/[a-f0-9]{32}\/tasks(?:\/[a-f0-9]{32})?$/.test(path))await taskPendingAuthorize(this,{key,path});
      if(old&&milestoneCommandPath(path))await milestonePendingAuthorize(this,{key,path});
      if(old&&(path==='/business/migrations'||path.startsWith('/business/migrations/')))await migrationPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/custom-fields/'))await customFieldsPendingAuthorize(this,{key,path});
      if(old&&path.startsWith('/business/company-handover/'))await companyHandoverPendingAuthorize(this,{key,path});
      if(old&&(path==='/business/inventory/counts'||path.startsWith('/business/inventory/counts/')))await inventoryCountPendingAuthorize(this,{key,path});
      if(generation!==this.#generation||this.#pending.get(key)!==operation)throw new StaleSession();
      if(stillCurrent&&!stillCurrent())throw new ApiError('Die ursprüngliche Ansicht wurde geschlossen. Der Auftrag bleibt unbestätigt.',0);
      const result = await this.post(path, operation.body);
      if(generation!==this.#generation||this.#pending.get(key)!==operation)throw new StaleSession();
      if(operation.validate)await operation.validate(result,JSON.parse(JSON.stringify(operation.body)));
      if(generation!==this.#generation||this.#pending.get(key)!==operation)throw new StaleSession();
      this.#pending.delete(key); return result;
    } catch (error) {
      const protectedAccounting=path.startsWith('/business/accounting/year-values')||path.startsWith('/business/accounting/open-items')||path.startsWith('/business/company-events/')||path.startsWith('/business/accounting/historical-assets')||datedConsumerCommand(key,path,operation.body)||path.startsWith('/business/catalog-prices/')||key.startsWith('catalog-')||path.startsWith('/business/accounting/opening-balances')||(key.startsWith('purchase-change-')&&/^\/business\/purchasing\/orders\/[a-f0-9]{32}\/(?:change-files|amendments|supplier-returns)$/.test(path))||path.startsWith('/business/bank/')||path.startsWith('/business/resource-custody/')||path.startsWith('/business/service/cases')||path.startsWith('/business/custom-fields/')||path==='/business/migrations'||path.startsWith('/business/migrations/')||path.startsWith('/business/company-handover/')||path.startsWith('/business/sales/')||path==='/business/inventory/counts'||path.startsWith('/business/inventory/counts/')||path.startsWith('/business/assistant/')||path.startsWith('/business/payroll/')||path.startsWith('/business/customer-workspace/')||path.startsWith('/business/personnel/')||path==='/business/accounting/euer/confirm'||path==='/business/finance/receipts'||/^\/business\/finance\/receipts\/[a-f0-9]{32}$/.test(path)||path==='/business/receipt-media'||/^\/business\/receipt-media\/[a-f0-9]{32}\/complete$/.test(path)||path==='/business/project-economics/confirm'||path==='/business/accounting/profile/confirm'||/^\/business\/accounting\/(?:components|refunds)\/(?:v2\/)?events\/[0-9a-f]{32}\/confirm$/.test(path);
      const protectedTask=/^\/projects\/[a-f0-9]{32}\/tasks(?:\/[a-f0-9]{32})?$/.test(path);
      const protectedMaintenance=/^\/business\/maintenance\/contracts(?:\/[a-f0-9]{32})?$/.test(path)&&([403,404].includes(error.status)||old&&error.status===409&&error.requestResolution!=='not_accepted');
      const protectedStockReturn=isStockReturn(key,path,operation.body)&&([403,404].includes(error.status)||old&&error.status===409&&error.requestResolution!=='not_accepted');
      const uncertainAccounting=protectedStockReturn||protectedMaintenance||(protectedAccounting||milestoneCommandPath(path)||documentTimeCommand(key,path,operation.body))&&([403,404].includes(error.status)||error.status===409&&error.requestResolution!=='not_accepted')||protectedTask&&[403,404].includes(error.status);
      if (generation===this.#generation && this.#pending.get(key)===operation && error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 423 && error.status !== 429 && !uncertainAccounting) this.#pending.delete(key);
      throw error;
    }
  }
}

export async function assistantPendingAuthorize(api,operation) {
  const values=api.pendingCommandValues(operation?.key,operation?.path);
  if(!values||!operation.path.startsWith('/business/assistant/'))throw new ApiError('Der ursprüngliche Assistentenauftrag ist nicht mehr verfügbar.',409);
  const id=/^[a-f0-9]{32}$/;
  let project=values.project_id;
  const target=/^\/business\/assistant\/plans\/([a-f0-9]{32})\/(?:approve|reject|execute)$/.exec(operation.path);
  if(target){const source=await api.get('/business/assistant/plans/'+target[1]);project=source.project_id;}
  else if(id.test(values.context_id||'')){const source=await api.get('/business/assistant/contexts/'+values.context_id);project=source.project_id;}
  if(!id.test(project||''))throw new ApiError('Der offene Auftrag hat keine eindeutige Projektbindung.',409);
  const caps=await api.get('/business/capabilities?project_id='+project);
  if(caps.readonly!==false||!caps.features?.includes('assistant_workflow')||!caps.capabilities?.includes('business_assistant')||!caps.permissions?.includes('assistant.use'))throw new ApiError('Aktuelle Projekt- und Assistentenrechte fehlen. Der ursprüngliche Auftrag bleibt offen.',403);
  await api.get('/business/assistant/sources?project_id='+project);
  return project;
}

export function projectContext(section, projectId='') {
  if(section==='projects')return {projectId:projectId||'',label:'Projekt öffnen',all:'Projektübersicht'};
  if(['planning','documents','finance','material','assistant','service'].includes(section))
    return {projectId:projectId||'',label:'Projektfilter',all:'Alle Projekte'};
  return {projectId:'',label:null,all:null};
}
const NAV = [
  ['overview','Übersicht','◈'], ['inquiries','Anfragen','↗'], ['projects','Projekte','▦'], ['contacts','Kontakte','◎'],
  ['planning','Einsatzplanung','▤'], ['documents','Dokumente','▧'], ['finance','Finanzen','€'],
  ['material','Material','▣'], ['personnel','Personal','◷'], ['assistant','Assistent','✧'], ['service','Kundenservice','◉'], ['settings','Einstellungen','⚙']
];

const LABELS = {remainder_cancelled:'Restmenge storniert',draft:'Entwurf',final:'Festgeschrieben',signed:'Unterzeichnet',new:'Neu',in_progress:'In Arbeit',open:'Offen',
  resolved:'Behoben',accepted:'Abgenommen',needs_review:'Prüfen',queued:'In Warteschlange',running:'Wird verarbeitet',failed:'Fehlgeschlagen',
  ready:'Bereit',uploading:'Upload läuft',planned:'Geplant',completed:'Abgeschlossen',paused:'Pausiert',working:'Läuft',stopped:'Beendet',
  reserved:'Reserviert',partial:'Teilweise entnommen',picked:'Entnommen',pending:'Ausstehend',not_sent:'Nicht versendet',unknown:'Unklar',
  proposal:'Bestellvorschlag',approved:'Freigegeben',ordered:'Bestellung dokumentiert',partially_received:'Teillieferung',received:'Vollständig geliefert',
  offer:'Angebot',estimate:'Kostenvoranschlag',order_confirmation:'Auftragsbestätigung',invoice:'Rechnung',advance_invoice:'Abschlagsrechnung',
  cumulative_invoice:'Kumulierte Rechnung',final_invoice:'Schlussrechnung',delivery_note:'Lieferschein',credit_note:'Gutschrift',
  receipt:'Zahlungseingang',refund:'Erstattung',material:'Material',labor:'Lohn',service:'Leistung',machine:'Maschine',
  operational:'Operativ',financial:'Finanziell',personnel:'Personal',restricted:'Geschützt'};
const api = new OfficeApi();
// Only current-session source IDs; command contents remain inside OfficeApi.
const refundPendingSources=new Map();
const state = {financeTab:'payments',accounting:{tab:'events',payments:0,receipts:0,events:0,accounts:0},section:'overview', projectId:'', tab:'overview', user:null, projects:[], permissions:new Set(), globalPermissions:new Set(), capabilities:new Set(), features:new Set(), organization:null, openedHiddenSection:null, readonly:true, planning:{mode:'week',anchor:dateInput(),years:3}, render:0, urls:new Set(), deviceId:'browser-'+requestId()};
let root, main, shell, banner, modal;
let dialogGeneration=0;
const has = permission => state.permissions.has(permission);
const canWrite = (permission,section=state.section) => has(permission) && !state.readonly && organizationModuleEnabled(section,state.organization);
const biz = path => '/business' + path;
const query = (path, values = {}) => path + '?' + new URLSearchParams(Object.entries(values).filter(([,v]) => v !== undefined && v !== null && v !== '')).toString();
const assetOrigins=assetProvenanceUi({el,button,field,form,dialog,panel,rows,row,notice,table,api,biz,query,mutation,action,download,refresh,formatDate,formatQuantity,
  allowed:project=>state.features.has('asset_delivery_provenance')&&has('documents.read')&&has('inventory.read')&&(!state.projectId||state.projectId===project)&&state.projects.some(item=>item.id===project),
  writable:()=>canWrite('documents.write','material')&&canWrite('inventory.write','material'),
  openOrder:id=>purchaseOrderDialog(id)});

const companyHandover=companyHandoverUi({el,button,field,form,dialog,panel,notice,table,api,biz,action,formatDate,
  allowed:()=>state.user?.role==='owner'&&state.features.has('company_handover')&&state.capabilities.has('business_company_handover')&&state.section==='settings',
  stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const privacyCases=privacyCasesUi({el,button,field,form,dialog,panel,notice,rows,row,api,biz,action,
  allowed:()=>has('privacy.manage')&&state.features.has('privacy_cases')&&state.capabilities.has('business_privacy_cases')&&['settings','contacts'].includes(state.section),
  stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const catalogWorkspace=catalogImportsUi({el,button,dialog,closeModal,panel,notice,table,api,formatDate,
  available:()=>state.section==='settings',caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly,organization:state.organization}),
  stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const datedWorkspace=datedCatalogUi({el,button,dialog,closeModal,panel,notice,table,api,formatDate,
  available:()=>state.section==='settings',caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly,organization:state.organization}),
  stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});
function pricePicker(options){return datedPricePicker({api,el,button,notice,stamp:()=>`${api.generation}/${state.render}`,canSelect:()=>has('finance.read')&&state.capabilities.has('business_catalog_prices'),deny:closeModal},options);}

const bankWorkspace=bankReconciliationUi({el,button,field,form,dialog,panel,notice,table,api,biz,action,formatDate,formatMoney,
  available:()=>state.section==='finance',caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly,organization:state.organization}),
  stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const openingWorkspace=accountingOpeningsUi({el,button,field,form,dialog,panel,notice,table,api,biz,action,formatDate,formatMoney,updatePending,
  available:()=>state.section==='finance',caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly,organization:state.organization}),
  stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const yearPackageWorkspace=accountingYearPackageUi({el,button,dialog,notice,table,api,
  available:()=>state.section==='finance',caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions]}),
  stamp:()=>`${api.generation}/${state.render}/${dialogGeneration}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const yearValuesWorkspace=accountingYearValuesUi({el,button,field,form,dialog,panel,notice,table,api,biz,formatDate,formatMoney,updatePending,
  available:()=>['finance','settings'].includes(state.section),caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly,organization:state.organization}),
  stamp:()=>`${api.generation}/${state.render}/${dialogGeneration}`,openProfile:accountingProfileDialog,
  openEuer:()=>{closeModal();state.section='finance';state.financeTab='accounting';state.accounting.tab='euer';return refresh();},
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const historicalWorkspace=historicalAssetsUi({el,button,field,form,dialog,panel,notice,table,api,biz,action,formatDate,formatMoney,updatePending,
  available:()=>state.section==='finance',caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly,organization:state.organization}),
  stamp:()=>`${api.generation}/${state.render}/${dialogGeneration}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const openItemWorkspace=accountingOpenItemsUi({el,button,field,form,dialog,panel,notice,table,api,biz,action,formatDate,formatMoney,updatePending,
  available:()=>state.section==='finance',caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly,organization:state.organization}),
  stamp:()=>`${api.generation}/${state.render}/${dialogGeneration}`,
  openEuer:()=>{closeModal();state.financeTab='accounting';state.accounting.tab='euer';return refresh();},openBank:()=>bankWorkspace.open(),
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const payrollWorkspace=payrollUi({el,button,field,form,dialog,panel,rows,row,notice,table,api,biz,query,mutation,action,refresh,formatDate,formatMoney,
  available:()=>state.features.has('german_payroll_2026')&&state.section==='personnel',
  caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly}),
  organization:()=>state.organization,userId:()=>state.user?.id,stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const travelWorkspace=travelAllowancesUi({el,button,field,form,dialog,panel,rows,row,notice,table,api,formatDate,formatMoney,
  allowed:()=>state.section==='personnel'&&state.features.has('travel_allowances')&&state.capabilities.has('business_travel_allowances')&&(state.globalPermissions.has('personnel.read')||state.globalPermissions.has('time.own')),
  stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const personnelWorkflow=personnelWorkflowUi({el,button,field,form,dialog,panel,rows,row,notice,table,api,biz,query,mutation,action,refresh,formatDate,formatMoney,duration,
  available:()=>state.features.has('personnel_preparation')&&state.section==='personnel',
  payrollAvailable:()=>state.features.has('german_payroll_2026'),openPayroll:employee=>payrollWorkspace.open(employee),
  travelAvailable:()=>state.features.has('travel_allowances')&&state.capabilities.has('business_travel_allowances'),openTravel:employee=>travelWorkspace.open(employee),
  permission:value=>state.globalPermissions.has(value),userId:()=>state.user?.id,
  enabled:()=>!state.readonly&&organizationModuleEnabled('personnel',state.organization),
  stamp:()=>`${api.generation}/${state.render}`,projects:()=>state.projects,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const inventoryCounts=inventoryCountsUi({el,button,field,form,dialog,panel,rows,row,notice,table,api,biz,query,mutation,action,refresh,formatDate,formatMoney,
  caps:()=>({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly,organization:state.organization}),
  stamp:()=>`${api.generation}/${state.render}`});

const assistantWorkspace=assistantUi({el,button,field,form,dialog,closeModal,panel,rows,row,notice,table,api,biz,query,mutation,action,refresh,formatDate,requestId,
  allowed:project=>state.features.has('assistant_workflow')&&has('assistant.use')&&state.projectId===project&&state.projects.some(item=>item.id===project),
  writable:()=>has('assistant.use')&&!state.readonly,
  settings:()=>has('settings.manage')&&!state.readonly,approve:()=>has('assistant.approve')&&!state.readonly,
  actionAllowed:action=>action==='task.create'?has('projects.manage'):action==='offer.draft'?has('finance.read')&&has('finance.write'):action==='supplier.order'?has('inventory.read')&&has('inventory.write')&&has('finance.approve'):has('finance.read')&&has('finance.approve'),
  speechAvailable:()=>state.features.has('assistant_speech')&&state.capabilities.has('business_assistant_speech'),
  userId:()=>state.user?.id,stamp:()=>`${api.generation}/${state.render}`});

const companyEvents=companyEventsUi({el,button,field,form,dialog,closeModal,panel,rows,row,notice,table,api,biz,action,formatDate,requestId,updatePending,
  stamp:()=>`${api.generation}/${state.render}/${dialogGeneration}`,projects:()=>state.projects,userId:()=>state.user?.id,
  openTask:async(project,id)=>{await api.get(`/projects/${project}/tasks/${id}`);closeModal();openProject(project,'tasks');}});

function migrationsAllowed(){return state.user?.role==='owner'&&state.features.has('file_migrations')&&state.capabilities.has('business_migrations')&&['settings.manage','contacts.read','finance.read','documents.read'].every(right=>state.globalPermissions.has(right));}
const fileMigrations=migrationsUi({el,button,field,form,dialog,closeModal,panel,rows,row,notice,table,api,biz,query,action,mutation,
  openProject:async projectId=>{const projects=collection(await api.get('/projects'));if(!projects.some(value=>value.id===projectId))throw new Error('Projektbezug ist nicht mehr freigegeben.');state.projects=projects;closeModal();openProject(projectId);},
  allowed:migrationsAllowed,writable:()=>migrationsAllowed()&&!state.readonly,
  canApply:()=>migrationsAllowed()&&!state.readonly&&state.user?.role==='owner'&&['contacts.write','projects.manage'].every(right=>state.globalPermissions.has(right)),
  stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const purchaseChanges=purchaseChangesUi({el,button,field,form,dialog,closeModal,panel,rows,row,notice,table,api,biz,query,action,mutation,formatDate,
 allowed:()=>state.features.has('purchase_changes')&&state.capabilities.has('business_purchase_changes')&&has('inventory.read'),stamp:()=>`${api.generation}/${state.render}`,openOrder:id=>purchaseOrderDialog(id),
 saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

function resourceCustodyAllowed(){return state.features.has('resource_custody')&&state.capabilities.has('business_resource_custody')&&['planning.read','planning.write'].every(value=>state.globalPermissions.has(value));}
const resourceCustody=resourceCustodyUi({el,button,field,form,dialog,closeModal,panel,rows,row,notice,table,api,biz,query,action,mutation,formatDate,
  allowed:resourceCustodyAllowed,writable:()=>resourceCustodyAllowed()&&!state.readonly&&organizationModuleEnabled('planning',state.organization),stamp:()=>`${api.generation}/${state.render}`,
  saveBlob:(blob,filename)=>{const link=el('a',{href:objectUrl(blob),download:filename,rel:'noopener'});document.body.append(link);link.click();link.remove();}});

const customerService=serviceUi({el,button,field,form,dialog,closeModal,panel,rows,row,notice,table,api,biz,query,action,mutation,formatDate,
  allowed:()=>state.features.has('service_cases')&&state.capabilities.has('business_service')&&has('contacts.read'),owner:()=>state.user?.role==='owner',canCreate:()=>!state.readonly&&(has('documents.write')||state.user?.role==='owner'&&has('contacts.write')),stamp:()=>`${api.generation}/${state.render}`,
  openProject:async projectId=>{const projects=collection(await api.get('/projects'));if(!projects.some(value=>value.id===projectId))throw new Error('Das Fallprojekt ist nicht mehr freigegeben.');state.projects=projects;closeModal();openProject(projectId);},
  openResources:projectId=>resourceCustody.open(projectId),resourcesAllowed:resourceCustodyAllowed,
  openReport:async(reportId,projectId)=>{const source=await api.get(biz('/service-reports/'+reportId));if(source.project_id!==projectId||source.status!=='signed'||!/^[a-f0-9]{64}$/.test(source.pdf_sha256||''))throw new Error('Unterzeichneter Projektnachweis fehlt.');const generation=api.generation,blob=await api.binary(biz('/service-reports/'+reportId+'/pdf')),bytes=await blob.arrayBuffer(),hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');await api.get(biz('/service-reports/'+reportId));if(generation!==api.generation||hash!==source.pdf_sha256)throw new Error('Das Original stimmt nicht mit dem Nachweis überein.');const link=el('a',{href:objectUrl(blob),download:'Servicebericht.pdf',rel:'noopener'});document.body.append(link);link.click();link.remove();}});

function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  Object.entries(attributes).forEach(([key,value]) => {
    if (value === undefined || value === null) return;
    if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'class') node.className = value;
    else if (key.startsWith('aria-') || key.startsWith('data-')) node.setAttribute(key, String(value));
    else if (key in node) node[key] = value;
    else node.setAttribute(key, String(value));
  });
  children.flat(Infinity).forEach(child => { if (child !== null && child !== undefined && child !== false) node.append(child instanceof Node ? child : document.createTextNode(String(child))); });
  return node;
}
function button(label, action, kind = '') { return el('button',{type:'button',class:'button '+kind,onClick:action},label); }
function badge(value) { return el('span',{class:'badge '+(['signed','ready','completed','final','accepted'].includes(value)?'success':value==='failed'?'warn':'')},LABELS[value]||value||'—'); }
function notice(message, kind = '') { return el('div',{class:'notice '+kind,role:kind==='error'?'alert':'status'},message); }
function empty(message) { return el('div',{class:'empty'},message); }
function panel(title, ...children) { return el('section',{class:'panel'},title?el('div',{class:'panel-title'},el('h2',{},title)):null,...children); }
function row(title, subtitle, actions = [], detail = null) { return el('div',{class:'list-row'},el('div',{class:'body'},el('h3',{},title),subtitle?el('p',{},subtitle):null,detail?el('p',{class:'detail'},detail):null),el('div',{class:'actions'},actions)); }
function rows(values, render, message = 'Noch keine Einträge vorhanden.') { return values.length ? el('div',{class:'list'},values.map(render)) : empty(message); }
function options(values, label = item => item.name || item.title || item.id) { return values.map(item => [item.id,label(item)]); }
function select(label, values, value, onChange) { return el('label',{class:'field'},label,el('select',{'aria-label':label,value,onChange:event=>onChange(event.target.value)},values.map(([id,name])=>el('option',{value:id,selected:id===value},name)))); }
function revokeUrls() { state.urls.forEach(url=>URL.revokeObjectURL(url)); state.urls.clear(); }
function objectUrl(blob) { const url=URL.createObjectURL(blob); state.urls.add(url); return url; }
function showError(error, target = main) {
  if (error instanceof StaleSession) return;
  if (error.status===401 && state.user) { endSession(); return; }
  // A fresh retry result replaces its old transient action message. Persistent
  // domain warnings and the separate list of unresolved commands remain.
  target.querySelectorAll(':scope > [data-action-error]').forEach(node=>node.remove());
  const message=notice(error.message||'Vorgang fehlgeschlagen.','error');
  message.dataset.actionError='true';target.prepend(message);updatePending();
}
async function action(function_, target = main) { try { return await function_(); } catch(error) { showError(error,target); } }
function heading(title, description, actions = []) { return el('header',{class:'page-header'},el('div',{},el('p',{class:'eyebrow'},'Smartplan Office'),el('h1',{},title),el('p',{class:'muted'},description)),el('div',{class:'actions'},actions)); }
function field(name,label,type='text',value='',extra={}) { return {name,label,type,value,...extra}; }
function projectField(value=state.projectId) { return field('project_id','Projekt','select',value,{options:[['','Bitte auswählen'],...options(state.projects)],required:true}); }

function form(title, fields, save, {description, submit='Speichern', after=()=>refresh(), key=title, extra, initial={}, readonly=false} = {}) {
  const controls = new Map(), form = el('form',{'data-form':key});
  const error = el('div',{class:'form-error'}), submitButton=el('button',{type:'submit',class:'button primary'},submit);
  const grid=el('div',{class:'form-grid'});
  fields.forEach(spec=> {
    const id='field-'+requestId(); const value=initial[spec.name] ?? spec.value;
    let input;
    if(spec.type==='select'||spec.type==='multi') input=el('select',{id,name:spec.name,multiple:spec.type==='multi',required:!!spec.required},(spec.options||[]).map(([id_,name])=>el('option',{value:id_,selected:Array.isArray(value)?value.includes(id_):id_===value},name)));
    else if(spec.type==='textarea') input=el('textarea',{id,name:spec.name,value:value??'',required:!!spec.required,maxLength:spec.maxLength||10000,rows:spec.rows||3});
    else input=el('input',{id,name:spec.name,type:spec.type==='decimal'?'text':spec.type==='integer'?'number':spec.type,inputMode:spec.type==='decimal'?'decimal':undefined,value:spec.type==='checkbox'?undefined:value??'',checked:spec.type==='checkbox'?!!value:undefined,required:!!spec.required,maxLength:spec.maxLength||2000,step:spec.type==='integer'?1:undefined,min:spec.min,max:spec.max,autoComplete:spec.autoComplete||'off'});
    input.setAttribute('aria-label',spec.label);
    input.disabled=readonly||spec.disabled===true;
    if(spec.help)input.setAttribute('aria-describedby',id+'-help');
    const label=el('label',{class:'field '+(spec.wide||spec.type==='textarea'?'wide ':'')+(spec.type==='checkbox'?'check':''),htmlFor:id},spec.label,input,spec.help?el('small',{id:id+'-help'},spec.help):null);
    grid.append(label); controls.set(spec.name,{input,spec});
  });
  form.append(grid); if(extra) form.append(extra);
  submitButton.disabled=readonly;
  form.append(el('div',{class:'form-actions'},submitButton),error);
  form.addEventListener('submit',async event=> {
    event.preventDefault(); if(submitButton.disabled) return;
    error.replaceChildren(); submitButton.disabled=true;
    try {
      const data={};
      controls.forEach(({input,spec},name)=> {
        let value=spec.type==='checkbox'?input.checked:spec.type==='multi'?Array.from(input.selectedOptions).map(option=>option.value):input.value;
        if(!spec.required&&value===''&&!spec.keepEmpty&&!['text','textarea','email','tel','date'].includes(spec.type)) return;
        if(spec.type==='decimal') value=decimalText(value);
        if(spec.type==='integer') { value=Number(value); if(!Number.isSafeInteger(value)) throw new Error('Ganze Zahl erwartet.'); }
        if(spec.type==='datetime-local') { const date=new Date(value); if(!Number.isFinite(date.getTime())) throw new Error('Gültige Uhrzeit eingeben.'); value=date.toISOString(); }
        data[name]=value;
      });
      const result=await save(data,key);
      if(result!==undefined) { closeModal(); await after(result); }
    } catch(error_) { showError(error_,error); }
    finally { submitButton.disabled=false; }
  });
  const section=panel(title,description?el('p',{class:'muted'},description):null,form);
  section.controls=controls; return section;
}
function dialog(title, content, description = '') {
  closeModal({keepYearValues:content?.matches?.('[data-year-values]')===true,keepOpenItems:content?.matches?.('[data-open-items]')===true,keepWageInterruptions:content?.matches?.('[data-wage-interruptions]')===true,keepAnnualBasis:content?.matches?.('[data-payroll-annual-basis]')===true,keepOneOffCases:content?.matches?.('[data-payroll-oneoff-cases]')===true,keepMultipleCases:content?.matches?.('[data-payroll-multiple-cases]')===true,keepCompanyEvents:content?.matches?.('[data-company-events]')===true}); const previous=document.activeElement;
  const close=button('×',()=>closeModal(),'icon'); close.className='modal-close'; close.setAttribute('aria-label','Dialog schließen');
  const box=el('section',{class:'modal',role:'dialog','aria-modal':'true','aria-label':title,tabIndex:-1},el('div',{class:'modal-head'},el('div',{},el('h2',{},title),description?el('p',{class:'muted'},description):null),close),content);
  modal=el('div',{class:'modal-backdrop'},box); modal.previous=previous;
  modal.addEventListener('keydown',event=> {
    if(event.key==='Escape') closeModal();
    if(event.key==='Tab') {
      const targets=Array.from(box.querySelectorAll('button,input,select,textarea,a[href]')).filter(node=>!node.disabled&&node.tabIndex>=0&&node.getClientRects().length&&!node.closest('[inert],[hidden]'));
      if(!targets.length) { event.preventDefault(); box.focus(); return; }
      if(!targets.includes(document.activeElement)) { event.preventDefault(); (event.shiftKey?targets.at(-1):targets[0]).focus(); }
      else if(event.shiftKey&&document.activeElement===targets[0]) { event.preventDefault(); targets.at(-1).focus(); }
      else if(!event.shiftKey&&document.activeElement===targets.at(-1)) { event.preventDefault(); targets[0].focus(); }
    }
  });
  document.body.append(modal); box.focus(); return box;
}
function closeModal({keepYearValues=false,keepWageInterruptions=false,keepAnnualBasis=false,keepOneOffCases=false,keepMultipleCases=false,keepCompanyEvents=false,keepOpenItems=false}={}) { dialogGeneration++; if(!keepYearValues)yearValuesWorkspace.clear(); if(modal) { if(modal.querySelector('.communication-history'))communicationHistory.clear(modal); if(modal.querySelector('[data-year-package]'))yearPackageWorkspace.clear();if(!keepOpenItems&&modal.querySelector('[data-open-items]'))openItemWorkspace.clear();if(!keepCompanyEvents&&modal.querySelector('[data-company-events]'))companyEvents.clear(); if(modal.querySelector('[data-historical-assets]'))historicalWorkspace.clear();if(modal.querySelector('[data-accounting-openings]'))openingWorkspace.clear();if(modal.querySelector('[data-payroll]'))payrollWorkspace.clear({keepWageInterruptions,keepAnnualBasis,keepOneOffCases,keepMultipleCases});const previous=modal.previous;modal.querySelectorAll('canvas').forEach(canvas=>canvas.disconnect?.());modal.remove();modal=null;previous?.focus(); } }
async function download(path,filename) { const blob=await api.binary(path),url=objectUrl(blob),link=el('a',{href:url,download:filename,rel:'noopener'}); document.body.append(link); link.click(); link.remove(); }
function jsonDownload(value,filename) { const link=el('a',{href:objectUrl(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),download:filename}); document.body.append(link); link.click(); link.remove(); }
function mutation(key,path,data,options) {
  if(state.readonly)throw new ApiError('Der aktuelle Betriebsmodus erlaubt nur das Lesen vorhandener Daten.',409);
  if(!organizationModuleEnabled(organizationCommandArea(path),state.organization))
    throw new ApiError('Dieser Bereich ist fachlich deaktiviert. Neue Vorgänge benötigen die Aktivierung in den Unternehmenseinstellungen.',423);
  const dated=datedConsumerCommand(key,biz(path),data),owner=modal,generation=api.generation,render=state.render;
  const current=()=>owner===modal&&(!owner||owner.isConnected)&&generation===api.generation&&render===state.render&&document.visibilityState!=='hidden';
  const response=api.mutate(key,biz(path),data,options);
  if(!dated)return response;
  return response.then(value=>current()?value:undefined,error=>{if(current())throw error;return undefined;});
}
function accountingRights(status=null) { return accountingAccess({permissions:[...state.globalPermissions],capabilities:[...state.capabilities],features:[...state.features],readonly:state.readonly},state.organization,status); }
function sectionAuthorized(section) {
  const permissions=projectContext(section).label?state.permissions:state.globalPermissions;
  const allowed=permission=>permissions.has(permission);
  if(section==='service')return state.features.has('service_cases')&&state.capabilities.has('business_service')&&allowed('contacts.read');
  if(section==='assistant')return state.features.has('assistant_workflow')&&allowed('assistant.use');
  if(section==='finance'&&accountingRights().read)return true;
  if(ORGANIZATION_AREAS.some(([name])=>name===section))return organizationAreaAuthorized(section,permissions,state.capabilities);
  return ({contacts:allowed('contacts.read'),planning:allowed('planning.read'),finance:allowed('finance.read'),material:allowed('inventory.read')||allowed('finance.read'),
    personnel:allowed('time.own')||allowed('personnel.read'),settings:allowed('settings.manage'),inquiries:state.metadata?.can_read_inquiries===true,documents:allowed('documents.read')||allowed('finance.read')})[section]??true;
}
function sectionAllowed(section) {
  return organizationSectionAllowed(section,sectionAuthorized(section),state.organization);
}
function mayOpenSection(section) {
  if(sectionAllowed(section))return true;
  if(state.openedHiddenSection!==section)return false;
  return organizationSectionAllowed(section,sectionAuthorized(section),state.organization,true);
}

function loginScreen(challenge = null, enrollment = null) {
  privacyCases.clear();travelWorkspace.clear();payrollWorkspace.clear();yearValuesWorkspace.clear();openingWorkspace.clear();catalogWorkspace.clear();historicalWorkspace.clear();datedWorkspace.clear();openItemWorkspace.clear();yearPackageWorkspace.clear();
  refundPendingSources.clear();
  closeModal(); revokeUrls(); state.user=null; root.replaceChildren();
  const card=el('section',{class:'login-card'},el('div',{class:'brand'},el('span',{class:'brand-mark'},'S'),el('div',{},el('strong',{},'smartplan'),el('small',{},'OFFICE'))),el('h1',{},challenge?'Anmeldung bestätigen':'Willkommen im Büro.'),el('p',{class:'muted'},challenge?'Authentifizierungscode oder Wiederherstellungscode eingeben.':'Projekte, Team und Unterlagen an einem Ort.'));
  if(enrollment) card.append(notice('Diesen Schlüssel einmalig in der eigenen Authenticator-App einrichten. Keine Drittanbieter-QR-Webseite verwenden.'),el('p',{class:'secret'},enrollment.secret));
  const fields=challenge?[field('code','Authentifizierungscode','text','',{required:true,maxLength:100,autoComplete:'one-time-code'})]:[
    field('email','E-Mail','email','',{required:true,autoComplete:'username'}),field('password','Passwort','password','',{required:true,autoComplete:'current-password',maxLength:512})];
  const login=form('',fields,async data=> {
    if(!challenge) {
      const result=await api.request('/login',{method:'POST',body:data,publicRequest:true});
      card.querySelector('input[type=password]').value='';
      if(!result.mfa_required||typeof result.challenge!=='string') throw new ApiError('Der Server hat keine sichere MFA-Anmeldung bestätigt.',502);
      loginScreen(result.challenge,result.enrollment); return undefined;
    }
    const result=await api.request('/login/verify',{method:'POST',body:{challenge,code:data.code},publicRequest:true});
    api.setToken(result.token);
    if(result.recovery_codes?.length) {
      card.replaceChildren(el('h1',{},'Wiederherstellungscodes sichern'),notice('Diese Codes werden nur jetzt angezeigt. Geschützt aufbewahren; jeder Code kann nur einmal verwendet werden.','warn'),
        el('div',{class:'recovery-list'},result.recovery_codes.map(code=>el('span',{},code))),button('Ich habe die Codes gesichert',()=>action(startSession,card),'primary'));
    } else await startSession();
    return undefined;
  },{submit:challenge?'Bestätigen':'Weiter',key:'login',after:()=>{}});
  login.className=''; card.append(login);
  if(challenge) card.append(button('Andere Anmeldung',()=>{api.clear();loginScreen();},'link'));
  card.append(el('p',{class:'login-foot'},'Diese Browseransicht arbeitet online. Zugangsdaten werden nicht im Browserspeicher abgelegt. Für dauerhaft gespeicherte Offlinearbeit die native Smartplan-App verwenden.'));
  root.append(el('main',{id:'main-content',class:'login-shell'},card));
}
async function startSession() {
  const generation=api.generation;
  const [user,caps,projects,metadata]=await Promise.all([api.get('/me'),api.get(biz('/capabilities')),api.get('/projects'),api.get(biz('/overview'))]);
  if(generation!==api.generation) throw new StaleSession();
  const organization=organizationMetadata(caps);
  state.user=user;state.metadata=metadata;state.permissions=new Set(caps.permissions||[]);state.globalPermissions=new Set(caps.permissions||[]);state.capabilities=new Set(caps.capabilities||[]);state.features=new Set(caps.features||[]);state.organization=organization;state.openedHiddenSection=null;state.readonly=caps.readonly!==false;state.projects=collection(projects);
  if(!state.projects.some(project=>project.id===state.projectId))state.projectId='';
  state.section='overview'; buildShell(); await refresh();
}
function endSession() { state.financeTab='payments';state.accounting={tab:'events',payments:0,receipts:0,events:0,accounts:0};api.clear();communicationHistory.clear();photoUploads.clear();projectEconomics.clear();assistantWorkspace.clear();companyEvents.clear();accountingEuer.clear();state.render++;state.projects=[];state.projectId='';state.metadata=null;state.employeeId=null;state.newTimeEntryId=null;state.permissions.clear();state.globalPermissions.clear();state.capabilities.clear();state.features.clear();state.organization=null;state.openedHiddenSection=null;state.readonly=true;state.planning={mode:'week',anchor:dateInput(),years:3};loginScreen(); }
function buildShell() {
  root.replaceChildren(); shell=el('div',{class:'shell','data-context-section':state.section,'data-project-context':state.projectId});
  const nav=el('nav',{class:'navigation','aria-label':'Hauptnavigation'},NAV.filter(([id])=>sectionAllowed(id)).map(([id,label,glyph])=>el('button',{type:'button',class:'nav-button','data-section':id,'aria-current':id===state.section?'page':undefined,onClick:()=>navigate(id)},el('span',{class:'nav-glyph','aria-hidden':'true'},glyph),label)));
  const hidden=organizationHiddenAreas(state.organization,state.permissions,state.capabilities,state.globalPermissions);
  if(state.organization?.modules?.finance?.visible===false&&accountingRights().read&&!hidden.includes('finance'))hidden.push('finance');
  if(hidden.length)nav.append(el('details',{},el('summary',{class:'nav-button'},'Weitere Bereiche'),
    NAV.filter(([id])=>hidden.includes(id)).map(([id,label,glyph])=>el('button',{type:'button',class:'nav-button','data-section':id,
      'aria-current':id===state.section?'page':undefined,onClick:()=>navigate(id,{includeHidden:true})},
      el('span',{class:'nav-glyph','aria-hidden':'true'},glyph),label+' öffnen'))));
  const sidebar=el('aside',{class:'sidebar'},el('div',{class:'brand'},el('span',{class:'brand-mark'},'S'),el('div',{},el('strong',{},'smartplan'),el('small',{},'OFFICE'))),nav,el('div',{class:'sidebar-foot'},'Ihr Betrieb. Ein gemeinsamer Stand.',el('p',{class:'caption'},'Online · Daten vom eigenen Office-Server')));
  const scope=projectContext(state.section,state.projectId);
  const projectSelect=scope.label?el('label',{class:'project-context'},el('span',{},scope.label),
    el('select',{class:'project-select','aria-label':scope.label,onChange:event=>{state.projectId=event.target.value;state.tab='overview';refresh();}},
      el('option',{value:''},scope.all),state.projects.map(project=>el('option',{value:project.id,selected:project.id===state.projectId},project.name))))
    :el('span',{class:'workspace-context'},NAV.find(([id])=>id===state.section)?.[1]||'Smartplan Office');
  const menu=button('☰',()=>{shell.classList.toggle('menu-open');updateDrawer();},'icon mobile-menu');menu.setAttribute('aria-label','Navigation öffnen');menu.setAttribute('aria-expanded','false');
  const header=el('header',{class:'topbar'},menu,projectSelect,el('div',{class:'identity'},el('span',{},state.user.email||'Angemeldet'),button('Abmelden',()=>action(async()=>{try{await api.post('/logout',{});}finally{endSession();}}),'small')));
  const pending=button('Antworten offen',()=>pendingDialog(),'small');pending.dataset.pendingIndicator='true';pending.hidden=api.pendingCount===0;header.insertBefore(pending,header.lastChild);
  banner=el('div',{});main=el('main',{id:'main-content',class:'content',tabIndex:-1},el('div',{class:'loading',role:'status'},'Daten werden geladen …'));
  shell.append(sidebar,el('div',{class:'workspace'},header,banner,main));root.append(shell);networkState();updateDrawer();
}
function updateDrawer() {
  if(!shell)return;const sidebar=shell.querySelector('.sidebar'),mobile=matchMedia('(max-width:760px)').matches,open=shell.classList.contains('menu-open');
  if(sidebar){sidebar.inert=mobile&&!open;sidebar.setAttribute('aria-hidden',String(mobile&&!open));}
  shell.querySelector('.mobile-menu')?.setAttribute('aria-expanded',String(mobile&&open));
}
function networkState() { if(!banner)return;banner.replaceChildren(...(navigator.onLine?[]:[notice('Keine Internetverbindung. Browseränderungen werden erst nach bestätigter Serverantwort gespeichert. Dieses Fenster geöffnet lassen.','warn')])); }
function updatePending() { const button_=root?.querySelector('[data-pending-indicator]');if(button_){button_.hidden=api.pendingCount===0;button_.textContent=api.pendingCount+' Antwort'+(api.pendingCount===1?'':'en')+' offen';} }
function operationLabel(path) {
  if(milestoneCommandPath(path))return 'Ursprüngliche Meilensteinänderung bestätigen';
  if(/^\/projects\/[a-f0-9]{32}\/tasks(?:\/[a-f0-9]{32})?$/.test(path))return 'Ursprüngliche Aufgabenänderung bestätigen';
  if(path.startsWith('/business/accounting/open-items/'))return 'Ursprünglichen Altpostenauftrag prüfen';
  if(path===biz('/accounting/year-values/originals'))return 'Ursprüngliches Jahresoriginal speichern';
  if(path===biz('/accounting/year-values/confirm'))return 'Belegte frühere Jahreswerte bestätigen';
  if(path===biz('/accounting/historical-assets/originals'))return 'Historisches Anlagenoriginal speichern';
  if(path===biz('/accounting/historical-assets/confirm'))return 'Historischen Anlagenvortrag bestätigen';
  if(path.startsWith('/business/company-events/'))return 'Unternehmensereignisauftrag unverändert prüfen';
  if(path===biz('/accounting/opening-balances/originals'))return 'Anfangsbestandsoriginal speichern';
  if(path===biz('/accounting/opening-balances/confirm'))return 'Anfangsbestandsfassung bestätigen';
  if(path==='/business/bank/accounts')return 'Bankkontozuordnung speichern';
  if(path==='/business/bank/statements')return 'Kontoauszug übernehmen';
  if(path.startsWith('/business/bank/transactions/'))return 'Bankbuchung abgleichen';
  if(path==='/business/bank/reconciliations')return 'Bankprüfstand dokumentieren';
  if(path.startsWith('/business/resource-custody/'))return 'Betriebsmittelnachweis speichern';
  if(path.startsWith('/business/payroll/cash/'))return 'Belegte Lohnzahlungen übernehmen';
  if(path==='/business/payroll/facts')return 'Belegten Lohnfall speichern';
  if(path.startsWith('/business/payroll/'))return 'Lohnvorgang bestätigen';
  if(path.startsWith('/business/service/cases'))return 'Kundenservicevorgang speichern';
  if(/^\/business\/purchasing\/orders\/[a-f0-9]{32}\/supplier-returns$/.test(path))return 'Lieferantenretoure dokumentieren';
  if(/^\/business\/purchasing\/orders\/[a-f0-9]{32}\/amendments$/.test(path))return 'Vereinbarte Bestellmengen ändern';
  if(/^\/business\/purchasing\/orders\/[a-f0-9]{32}\/change-files$/.test(path))return 'Einkaufsänderungsbeleg speichern';
  if(path.startsWith('/business/assistant/'))return 'Assistentenauftrag unverändert prüfen';
  if(path.startsWith('/business/personnel/'))return 'Personalvorgang unverändert bestätigen';
  if(path==='/business/assets/from-delivery')return 'Geliefertes Gerät mit Herkunft anlegen';
  if(/^\/business\/assets\/[^/]+\/origin$/.test(path))return 'Geräteherkunft verbindlich zuordnen';
  if(/^\/business\/purchasing\/receipts\/[^/]+\/document$/.test(path))return 'Original-Lieferschein zuordnen';
  if(path==='/business/project-economics/confirm')return 'Belegkosten vollständig einordnen';
  if(path==='/business/accounting/euer/confirm')return 'Geprüfte EÜR-Buchung festhalten';
  if(path==='/business/accounting/profile/confirm')return 'Vorbereitungsprofil ausdrücklich speichern';
  if(path.startsWith('/business/accounting/refunds/'))return 'Erstattungsursprung dokumentieren';
  if(path.startsWith('/business/accounting/components/'))return 'Beleganteile dokumentarisch aufteilen';
  if(path.startsWith('/business/accounting/allocations/'))return 'Bestehende Zahlung einer Rechnung zuordnen';
  if(path.startsWith('/business/accounting/accounts'))return 'Geldkonto bestätigen';
  if(path.startsWith('/business/accounting/events/import-payment'))return 'Bestehende Zahlung verknüpfen';
  if(path.startsWith('/business/accounting/events/payout'))return 'Tatsächliche Auszahlung bestätigen';
  if(path.startsWith('/business/portal/')&&path.endsWith('/revoke'))return 'Portalzugang widerrufen';
  if(path.startsWith('/business/portal/')&&path.endsWith('/adopt'))return 'Annahme in Auftragsentwurf übernehmen';
  if(path.startsWith('/business/portal/'))return 'Kundenportalzugang freigeben';
  if(path.endsWith('/finalize'))return 'Beleg festschreiben';
  if(path.endsWith('/sign'))return 'Fassung unterzeichnen';
  if(path.includes('/media'))return 'Foto / Unterlage speichern';
  if(path.includes('/inquiries'))return 'Anfrage bearbeiten';
  if(path.includes('/contacts'))return 'Kontakt speichern';
  if(path.includes('/purchasing')&&path.endsWith('/receipts'))return 'Wareneingang buchen';
  if(path.includes('/purchasing'))return 'Bestellung dokumentieren';
  if(path.includes('/inventory'))return 'Lagerbuchung bestätigen';
  if(path.includes('/time'))return 'Zeitnachweis speichern';
  return 'Begonnenen Vorgang bestätigen';
}
function pendingDialog() {
  dialog('Unbestätigte Antworten',el('div',{class:'stack'},notice('Der Server kann die Eingabe bereits gespeichert haben. Eine Wiederholung verwendet exakt dieselbe Vorgangskennung und denselben Inhalt. Dieses Fenster bis zur Klärung geöffnet lassen.','warn'),
    rows(api.pendingOperations(),item=>row(operationLabel(item.path),'Unveränderte Eingabe im Arbeitsspeicher',[button('Unverändert erneut senden',()=>action(async()=>{
      if((item.path.startsWith(biz('/accounting/allocations/'))||item.path.startsWith(biz('/accounting/components/'))||item.path.startsWith(biz('/accounting/refunds/')))&&!navigator.onLine)throw new ApiError('Die Zahlungszuordnung benötigt eine Internetverbindung. Die unveränderte Anfrage bleibt offen.',0);
      const generation=api.generation,previous=modal,initialRender=state.render;
      if(item.path.startsWith(biz('/accounting/year-values'))){await yvPendingAuthorize(api,item);if(generation!==api.generation||previous!==modal||initialRender!==state.render)return;}
      if(item.path.startsWith(biz('/accounting/historical-assets'))){await assetPendingAuthorize(api,item);if(generation!==api.generation||previous!==modal||initialRender!==state.render)return;}
      if(item.path.startsWith(biz('/accounting/opening-balances'))){await openingPendingAuthorize(api,item);if(generation!==api.generation||previous!==modal||initialRender!==state.render)return;}
      if(item.key.startsWith('euer-original-review-')){await accountingEuer.authorizeReceiptRetry();if(generation!==api.generation||previous!==modal||initialRender!==state.render)return;}
      if(item.path===biz('/accounting/euer/confirm')){await euerAuthorize(api,{write:true,online:navigator.onLine,organization:state.organization});if(generation!==api.generation||previous!==modal||initialRender!==state.render)return;}
      if(item.path===biz('/accounting/profile/confirm')){await accountingProfileAuthorize(api,{write:true,online:navigator.onLine});if(generation!==api.generation||previous!==modal||initialRender!==state.render)return;}
      if(item.path.startsWith(biz('/accounting/components/'))){componentWritable();await componentPendingAuthorize(api,item);if(generation!==api.generation||previous!==modal||initialRender!==state.render)return;componentWritable();}
      if(item.path.startsWith(biz('/accounting/refunds/'))){refundWritable();await refundPendingAuthorize(api,item);if(!item.path.startsWith(biz('/accounting/refunds/v2/'))){const sources=refundPendingSources.get(item.key);if(!sources||sources.generation!==generation)throw new ApiError('Die Ursprungsrechte können für diese offene Anfrage nicht sicher geprüft werden.',409);await refundAuthorizeCurrent(sources.eventId,sources.origins);}if(generation!==api.generation||previous!==modal||initialRender!==state.render)return;refundWritable();}
      let result;try{const pendingBody=api.pendingCommandValues(item.key,item.path),factorTravel=item.path==='/business/payroll/calculation-cases'&&['de_2026_factor_taxfree_travel_month_v10','de_2026_individual_minijob_month_v11'].includes(pendingBody?.rule_version)||item.path==='/business/payroll/runs'&&['regular_standard_factor_taxfree_travel_month','commercial_minijob_individual_month'].includes(pendingBody?.accepted_scope);result=await api.retry(item.key,(factorTravel||isStockReturn(item.key,item.path,pendingBody)||/^\/business\/maintenance\/contracts(?:\/[a-f0-9]{32})?$/.test(item.path))?{stillCurrent:()=>generation===api.generation&&previous===modal&&initialRender===state.render&&document.visibilityState!=='hidden'}:{});}catch(error){if(milestoneCommandPath(item.path)&&(generation!==api.generation||previous!==modal||initialRender!==state.render))return;throw error;}if(generation!==api.generation||previous!==modal||initialRender!==state.render)return;refundPendingSources.delete(item.key);updatePending();
      if(item.path===biz('/portal/grants')){portalGrantResultDialog({id:result.grant.offer_id,project_id:result.grant.project_id,number:result.grant.number,kind:'offer',status:'final'},result);return;}
      closeModal();const render=state.render+1,section=state.section;await refresh();
      if(item.path===biz('/accounting/profile/confirm')&&generation===api.generation&&state.render===render&&state.section===section&&!modal)await accountingProfileDialog();
      if(item.path.startsWith(biz('/accounting/allocations/'))&&item.path.endsWith('/assign')&&generation===api.generation&&state.render===render&&state.section===section&&!modal)await accountingAllocationDialog(result.payment_id,{document:result.document});
      if(item.path.startsWith(biz('/accounting/components/'))&&item.path.endsWith('/confirm')&&generation===api.generation&&state.render===render&&state.section===section&&!modal)await componentDialog(result.event_id);
      if(item.path.startsWith(biz('/accounting/refunds/'))&&item.path.endsWith('/confirm')&&generation===api.generation&&state.render===render&&state.section===section&&!modal)await refundDialog(result.event_id);}),'primary')]))));
}
function navigate(section,{includeHidden=false}={}) {
  state.openedHiddenSection=includeHidden&&sectionAuthorized(section)?section:null;
  if(!mayOpenSection(section))return;
  if(!projectContext(section).label){state.projectId='';state.tab='overview';state.permissions=new Set(state.globalPermissions);}
  closeModal();state.section=section;shell?.classList.remove('menu-open');updateDrawer();root.querySelectorAll('[data-section]').forEach(node=>{if(node.dataset.section===section)node.setAttribute('aria-current','page');else node.removeAttribute('aria-current');});refresh();
}
async function refresh() {
  if(!state.user)return;
  state.projectId=projectContext(state.section,state.projectId).projectId;
  catalogWorkspace.clear();datedWorkspace.clear();
  const version=++state.render,generation=api.generation;communicationHistory.clear();if(modal?.querySelector('.communication-history'))closeModal();revokeUrls();main.replaceChildren(el('div',{class:'loading',role:'status'},'Daten werden geladen …'));
  try {
    const [caps,projects,metadata]=await Promise.all([api.get(biz('/capabilities')),api.get('/projects'),api.get(biz('/overview'))]);
    if(version!==state.render||generation!==api.generation)return;
    const organization=organizationMetadata(caps),organizationChanged=JSON.stringify(state.organization)!==JSON.stringify(organization);
    const navigationChanged=organizationChanged||[...state.globalPermissions].sort().join('|')!==[...(caps.permissions||[])].sort().join('|')||state.metadata?.can_read_inquiries!==metadata.can_read_inquiries||JSON.stringify(state.projects)!==JSON.stringify(collection(projects));
    state.globalPermissions=new Set(caps.permissions||[]);state.capabilities=new Set(caps.capabilities||[]);state.features=new Set(caps.features||[]);state.organization=organization;state.readonly=caps.readonly!==false;state.projects=collection(projects);state.metadata=metadata;
    if((!euerRights({permissions:[...state.globalPermissions],features:[...state.features],capabilities:[...state.capabilities],readonly:state.readonly},state.organization).read&&modal?.querySelector('[data-euer-detail]'))||organizationChanged||(!accountingRights().read&&modal?.querySelector('[data-accounting-detail]'))||(!accountingProfileRights().read&&modal?.querySelector('[data-profile-detail]'))||(!refundRights().read&&modal?.querySelector('[data-refund-detail]'))||(!capacityRights().read&&modal?.querySelector('[data-capacity-detail]'))||(!refundV2Rights().read&&modal?.querySelector('[data-refund-v2-detail]')))closeModal();
    if(state.projectId&&!state.projects.some(project=>project.id===state.projectId)){state.projectId='';state.tab='overview';closeModal();}
    let effective=state.globalPermissions;
    if(state.projectId) {
      const profile=await api.get(['finance','assistant','service'].includes(state.section)?query(biz('/capabilities'),{project_id:state.projectId}):biz(`/projects/${state.projectId}/profile`));
      if(version!==state.render||generation!==api.generation)return;
      effective=new Set(profile.permissions||state.globalPermissions);
    }
    if(navigationChanged||[...effective].sort().join('|')!==[...state.permissions].sort().join('|')||shell?.dataset.contextSection!==state.section||shell?.dataset.projectContext!==state.projectId) {
      state.permissions=new Set(effective);
      if(!mayOpenSection(state.section)){state.section='overview';state.projectId='';state.tab='overview';state.permissions=new Set(state.globalPermissions);state.openedHiddenSection=null;}
      buildShell();
    }
    if(modal?.querySelector('[data-personnel-workflow]'))closeModal();
    if(modal?.querySelector('[data-payroll-facts]'))closeModal();
    if(modal?.querySelector('[data-wage-interruptions]')){payrollWorkspace.clear();closeModal();}
    if(modal?.querySelector('[data-payroll-annual-basis]')){payrollWorkspace.clear();closeModal();}
    if(modal?.querySelector('[data-payroll-oneoff-cases],[data-payroll-multiple-cases]')){payrollWorkspace.clear();closeModal();}
    if(modal?.querySelector('[data-inventory-count],[data-stock-return]'))closeModal();
    if(modal?.querySelector('[data-open-items]')){openItemWorkspace.clear();closeModal();}
    if(modal?.querySelector('[data-year-package],[data-year-export]')){yearPackageWorkspace.clear();closeModal();}
    if(modal?.querySelector('[data-year-values]'))closeModal();
    if(modal?.querySelector('[data-historical-assets]')){historicalWorkspace.clear();closeModal();}
    if(modal?.querySelector('[data-accounting-openings]')){openingWorkspace.clear();closeModal();}
    if(modal?.querySelector('[data-privacy-cases]')){privacyCases.clear();closeModal();}
    if(modal?.querySelector('[data-travel-allowances]')){travelWorkspace.clear();closeModal();}
    if(modal?.querySelector('[data-file-migration]'))closeModal();
    if(modal?.querySelector('[data-service-case],[data-resource-custody],[data-purchase-change]'))closeModal();
    if(modal?.querySelector('[data-project-tasks]'))closeModal();
    if(modal?.querySelector('[data-project-milestones]'))closeModal();
    if(modal?.querySelector('[data-maintenance-contract]'))closeModal();
    if(modal?.querySelector('[data-custom-fields]'))closeModal();
    if(modal?.querySelector('[data-assistant-project]'))closeModal();
    if(modal?.querySelector('[data-company-events]'))closeModal();
    if(!state.features.has('assistant_workflow')||!has('assistant.use'))assistantWorkspace.clear();
    const originDetail=modal?.querySelector('[data-asset-origin-detail]');
    if(originDetail&&!assetOrigins.allowed(originDetail.getAttribute('data-asset-origin-detail')))closeModal();
    const view=await ({overview:overviewView,inquiries:inquiriesView,projects:projectsView,contacts:contactsView,planning:planningView,documents:documentsView,finance:financeView,material:materialView,personnel:personnelView,assistant:assistantView,service:serviceView,settings:settingsView}[state.section]||overviewView)();
    if(version!==state.render||generation!==api.generation)return;
    main.replaceChildren(view);
    if(!organizationModuleEnabled(state.section,state.organization))main.prepend(notice('Dieser Bereich ist fachlich deaktiviert. Vorhandene Daten und Nachweise bleiben entsprechend Ihren Rechten lesbar. Neue Vorgänge sind gesperrt.','warn'));
    if(state.openedHiddenSection===state.section)main.prepend(notice('Dieser Bereich ist in der Hauptnavigation ausgeblendet. Die Einstellung und alle vorhandenen Daten bleiben erhalten.'));
    updatePending();main.focus({preventScroll:true});
  } catch(error) { if(version===state.render&&generation===api.generation) {main.replaceChildren();showError(error);main.append(button('Erneut laden',()=>refresh()));} }
}

async function serviceView(){return el('div',{class:'stack'},heading('Kundenservice','Anliegen, Reklamationen und Wartung mit Zuständigkeit, Wiedervorlage und unveränderlichem Verlauf.'),await customerService.view({project_id:state.projectId||null}));}

async function assistantView(){return el('div',{class:'stack'},heading('Assistent','Belegte Projektquellen, konkrete Aufträge und nachvollziehbare Unternehmensregeln.'),companyEventRights({features:[...state.features],capabilities:[...state.capabilities],permissions:[...state.globalPermissions],readonly:state.readonly}).read?panel('Unternehmensereignisse',el('p',{},'Regeln über betroffene Projekte, belegte Ereignisse und konkrete Freigaben.'),button('Unternehmensereignisse öffnen',()=>action(()=>companyEvents.open()),'primary')):null,await assistantWorkspace.view(state.projectId));}

async function overviewView() {
  const data=await api.get(biz('/overview'));
  const metrics=state.features.has('company_overview')?await api.get(query(biz('/overview/metrics'),{project_id:state.projectId})):null;
  const feed=collection(await api.get(query(biz('/feed'),{project_id:state.projectId})));
  const projects=data.projects||[];
  const content=el('div',{class:'stack'},heading('Guten Tag.','Was heute zählt – aus Ihrem gemeinsamen Projektbestand.',[button('Aktualisieren',()=>refresh())]),
    metrics?renderCompanyOverview(metrics,{el,panel,row,rows,button,notice,formatMoney,formatDate,onProject:openProject,onAccounting:()=>{state.financeTab='accounting';state.accounting.tab='euer';navigate('finance');}}):null,
    el('div',{class:'grid'},panel('Projekte',el('div',{class:'metric'},data.counters?.projects??projects.length),el('p',{class:'metric-sub'},'Für Ihren Zugang freigegeben')),panel('Arbeitsbereich',el('h2',{},'Betriebsübersicht'),el('p',{class:'muted'},'Hier sehen Sie alle für Sie freigegebenen Projekte. Eine einzelne Projektmappe öffnen Sie unter „Projekte“.'),button('Projekte öffnen',()=>navigate('projects'),'primary'))),
    panel('Zuletzt im Betrieb',rows(feed.slice(0,10),item=>row(item.summary||item.message||item.event_type,formatDate(item.created_at,true),[badge(item.visibility||'operational')]),'Noch keine Projektereignisse vorhanden.')),
    panel('Ihre Projekte',rows(projects.slice(0,8),project=>row(project.name,project.customer,[project.status?badge(project.status.name):null,button('Projekt öffnen',()=>openProject(project.id),'small')]))));
  return content;
}
function openProject(id,tab='overview') { state.projectId=id;state.tab=tab;const projectSelect=root.querySelector('.project-select');if(projectSelect)projectSelect.value=id;navigate('projects'); }
async function projectsView() {
  if(state.projectId)return projectView();
  const data=await api.get(biz('/overview')),projects=data.projects||[],statuses=data.statuses||[];
  const group=[{id:'',name:'Noch ohne Status'},...statuses];
  const headerActions=data.can_create_project&&has('projects.manage')?[button('Neues Projekt',()=>action(()=>newProjectDialog()),'primary')]:[];
  const board=el('div',{class:'pipeline'},group.filter(status=>!status.id||status.active).map(status=>el('section',{class:'pipeline-column'},el('h3',{},status.name),
    ...projects.filter(project=>(project.status_id||'')===status.id).map(project=>el('button',{type:'button',class:'pipeline-card',onClick:()=>openProject(project.id)},el('strong',{},project.name),el('small',{},project.customer),el('p',{class:'caption'},project.site_address||'Objektadresse noch offen'))))));
  return el('div',{class:'stack'},heading('Projekte','Eine gemeinsame Projektmappe. Frei planbar, ohne starre Reihenfolge.',headerActions),
    projects.length?board:empty('Noch keine freigegebenen Projekte. Ein Projekt kann aus einer geprüften Anfrage oder direkt angelegt werden.'));
}
async function newProjectDialog(customerId='') {
  const generation=api.generation;
  const customers=collection(await api.get(biz('/contacts'))).filter(item=>item.active&&(item.kinds||[]).includes('customer'));
  if(generation!==api.generation)return;
  if(customerId&&!customers.some(item=>item.id===customerId))throw new Error('Der gewählte Kunde ist nicht mehr verfügbar. Bitte Kontakte neu laden.');
  const content=form('',[field('name','Projektname','text','',{required:true}),
    field('customer_id','Kunde auswählen','select',customerId,{options:[['','Neuen Kunden anlegen'],...options(customers,item=>[item.name,contactAddressSummary(item),item.email].filter(Boolean).join(' · '))],keepEmpty:true}),
    field('customer','Neuer Kunde / Auftraggeber','text','',{required:true})],
    data=>api.mutate('new-project','/projects',{name:data.name,...(data.customer_id?{customer_id:data.customer_id}:{customer:data.customer})}),
    {key:'new-project',submit:'Projekt anlegen',after:async result=>{state.projects=collection(await api.get('/projects'));buildShell();openProject(result.id||result);}});
  const selection=content.controls.get('customer_id').input,newName=content.controls.get('customer').input;
  const toggle=()=>{const existing=!!selection.value;newName.closest('label').hidden=existing;newName.closest('label').style.display=existing?'none':'';newName.required=!existing;newName.disabled=existing;};
  selection.addEventListener('change',toggle);toggle();
  dialog('Neues Projekt',content,'Wählen Sie einen vorhandenen Kunden, um Anschrift und Kontaktdaten weiterzuverwenden. Eine Projektanlage ist noch keine Auftragszusage.');
}
async function projectView() {
  const id=state.projectId,profile=await api.get(biz(`/projects/${id}/profile`));
  const tabs=[['overview','Übersicht'],['tasks','Aufgaben'],...(state.features.has('project_milestones')&&state.capabilities.has('business_project_milestones')&&has('planning.read')?[['milestones','Meilensteine']]:[]),['appointments','Termine'],['documents','Dokumente'],['documentation','Fotos & Doku'],['materials','Material'],...(has('finance.read')?[['costs',state.features.has('project_economics')?'Wirtschaftlichkeit':'Kalkulation']]:[]),['maintenance','Wartung'],...(state.features.has('communication_history')&&has('contacts.read')?[['communication','Kommunikation']]:[]),...(state.features.has('service_cases')&&has('contacts.read')?[['service','Kundenservice']]:[]),...(state.features.has('assistant_workflow')&&has('assistant.use')?[['assistant','Assistent']]:[]),['logbook','Logbuch']];
  if(!tabs.some(([tab])=>tab===state.tab))state.tab='overview';
  const head=heading(profile.name,`${profile.customer||''}${profile.site_address?' · '+profile.site_address:''}`,[button('Alle Projekte',()=>{state.projectId='';root.querySelector('.project-select').value='';refresh();})]);
  const navigation=el('div',{class:'tabs',role:'tablist','aria-label':'Projektmappe'},tabs.map(([tab,label])=>el('button',{type:'button',class:'tab',role:'tab','aria-selected':tab===state.tab,onClick:()=>{state.tab=tab;refresh();}},label)));
  let body;
  if(state.tab==='overview') {
    const dashboard=await api.get(`/projects/${id}/workspace`);
    body=el('div',{class:'grid two'},panel('Projektstand',el('div',{class:'actions'},profile.status?badge(profile.status.name):badge('Ohne Pipeline-Status')),
      el('p',{class:'muted'},profile.description||'Projektbeschreibung noch offen.'),el('p',{},`Projektnummer: ${profile.project_number||'noch nicht vergeben'}`),has('projects.manage')?button('Projektprofil bearbeiten',()=>projectProfileDialog(profile),'small'):null,state.features.has('custom_fields')?button('Zusatzfelder',()=>action(()=>customFields.open('project',id)),'small'):null),
      panel('Nächste Aufgaben',rows(dashboard.open_tasks||[],item=>row(item.title,item.details,[badge(item.status)]),'Keine offenen Aufgaben.')),
      panel('Nächste Termine',rows(dashboard.upcoming_appointments||[],item=>row(item.title,`${formatDate(item.start_at,true)} – ${formatDate(item.end_at,true)}`),'Noch keine Termine geplant.')),
      panel('Projektteam',rows(dashboard.team||[],member=>row(member.email||member.name,member.role),'Noch keine Teammitglieder zugewiesen.')));
  } else if(state.tab==='milestones') body=await projectMilestones.view(id);
  else if(state.tab==='tasks') body=await tasksPanel(id);
  else if(state.tab==='appointments') body=await planningContent(id);
  else if(state.tab==='documents') body=await documentsContent(id);
  else if(state.tab==='documentation') body=await documentationPanel(id);
  else if(state.tab==='materials') body=await materialContent(id);
  else if(state.tab==='costs') body=await costsPanel(id);
  else if(state.tab==='maintenance') body=await maintenancePanel(id);
  else if(state.tab==='assistant') body=await assistantWorkspace.view(id);
  else if(state.tab==='service') body=await customerService.view({project_id:id,customer_id:profile.customer_id});
  else if(state.tab==='communication') body=await communicationHistory.view({project_id:id,...(profile.customer_id?{customer_id:profile.customer_id}:{})});
  else body=await logbookPanel(id);
  return el('div',{class:'stack'},head,navigation,body);
}
async function projectProfileDialog(profile) {
  const statuses=collection(await api.get(biz('/project-statuses')));
  dialog('Projektprofil',form('',[field('project_number','Projektnummer','text',profile.project_number),field('status_id','Projektstatus','select',profile.status_id||'',{options:[['','Ohne Status'],...options(statuses)],keepEmpty:true}),field('site_address','Objektadresse','textarea',profile.site_address),field('description','Beschreibung','textarea',profile.description)],
    (data,key)=>mutation(key,`/projects/${profile.id}/profile`,{...data,status_id:data.status_id||null,revision:profile.revision,workspace_revision:profile.workspace_revision}),{key:'profile-'+profile.id}));
}
async function tasksPanel(id) {
  return projectTasks.view(id);
}
const projectTasks=projectTasksUi({api,el,button,panel,row,rows,notice,form,field,dialog,formatDate,action,refresh,
  writable:()=>!state.readonly,stamp:()=>`${api.generation}/${state.render}/${state.projectId}/${state.section}/${state.tab}/${dialogGeneration}`});
const projectMilestones=projectMilestonesUi({api,el,button,panel,row,rows,notice,form,field,dialog,formatDate,action,refresh,
  stamp:()=>`${api.generation}/${state.render}/${state.projectId}/${state.section}/${state.tab}/${dialogGeneration}`});
async function logbookPanel(id) {
  const feed=collection(await api.get(query(biz('/feed'),{project_id:id})));
  return el('div',{class:'stack'},has('documents.write')?form('Notiz im Projekt',[field('text','Nachricht / Notiz','textarea','',{required:true,maxLength:5000})],(data,key)=>mutation(key,'/feed',{...data,project_id:id}),{key:'message-'+id,submit:'Notiz hinzufügen'}):null,
    panel('Projektlogbuch',rows(feed,item=>row(item.summary,formatDate(item.created_at,true),[badge(item.event_type)]),'Noch keine Logbucheinträge.')));
}
async function inquiriesView() {
  const inquiries=collection(await api.get('/inquiries'));
  return el('div',{class:'stack'},heading('Anfragen','Erst prüfen, dann gezielt in Kunde und Projekt übernehmen.',[button('Anfrage erfassen',()=>inquiryDialog(),'primary')]),
    panel('Posteingang',rows(inquiries,item=>row(item.subject,`${item.sender_name||item.sender_email||'Absender offen'} · ${formatDate(item.received_at,true)}`,[badge(item.status),button('Öffnen',()=>action(()=>inquiryDetail(item.id)),'small')],item.message?.slice(0,180)),'Noch keine Anfragen eingegangen.')));
}
function inquiryDialog() {
  dialog('Neue Anfrage',form('',[field('subject','Betreff','text','',{required:true,maxLength:300}),field('source','Kanal','select','manual',{options:[['manual','Telefon / manuell'],['whatsapp','WhatsApp – manuell übernommen']]}),field('sender_name','Name'),field('sender_email','E-Mail','email'),field('sender_phone','Telefon','tel'),field('message','Anfrage','textarea','',{required:true,maxLength:40000})],
    (data,key)=>api.mutate(key,'/inquiries',{...data,source_account:'office-browser'}),{key:'inquiry-create',submit:'Anfrage speichern'}),'WhatsApp-Nachrichten hier manuell erfassen. Es wird kein Messenger abgerufen oder versendet.');
}
async function inquiryDetail(id) {
  const item=await api.get('/inquiries/'+id),files=await api.get('/inquiries/'+id+'/attachments');
  const content=el('div',{class:'stack'},panel('Anfrage',row(item.subject,item.sender_name||item.sender_email,[badge(item.status)]),el('p',{class:'break-word'},item.message)),
    panel('Originalunterlagen',rows(collection(files.files||files),file=>row(file.filename,`${file.media_type} · ${Math.ceil(file.size/1024)} KB`,[file.status==='ready'?button('Original laden',()=>action(()=>download(`/inquiries/${id}/attachments/${file.id}/content`,file.filename)),'small'):badge(file.status)]),'Keine Originalunterlagen vorhanden.')));
  if(item.project_id)content.append(button('Verknüpftes Projekt öffnen',()=>{closeModal();openProject(item.project_id);},'primary'));
  else content.append(button('Geprüft in Projekt übernehmen',()=>action(()=>convertInquiryDialog(item)),'primary'));
  if(state.features.has('sales_pipeline')&&has('contacts.write'))content.append(button('Verkaufschance erfassen',()=>action(()=>sales.choose(item.customer_id||null,item))));
  dialog(item.subject,content,'Eine Anfrage bestätigt weder Auftrag noch Termin oder Zahlung.');
}
async function convertInquiryDialog(item) {
  const contacts=collection(await api.get(biz('/contacts')));
  dialog('Anfrage übernehmen',form('',[field('project_name','Projektname','text',item.subject,{required:true}),field('customer_id','Bestehender Kontakt','select','',{options:[['','Neuen Kunden anlegen'],...options(contacts)],keepEmpty:true}),field('customer_name','Name des neuen Kunden','text',item.sender_name||''),field('customer_email','E-Mail des neuen Kunden','email',item.sender_email||'')],
    (data,key)=>api.mutate(key,`/inquiries/${item.id}/convert`,{request_id:undefined,revision:item.revision,project_name:data.project_name,...(data.customer_id?{customer_id:data.customer_id}:{customer:{name:data.customer_name,email:data.customer_email||''}})}),
    {key:'convert-'+item.id,submit:'Kunde & Projekt verknüpfen',after:async result=>{state.projects=collection(await api.get('/projects'));buildShell();openProject(result.project.id);}}),'Die Quelle und Originalunterlagen bleiben mit dem neuen Projekt verknüpft.');
}
function contactAddressSummary(contact) {
  return contact.address||(contact.addresses||[]).map(address=>[address.street,[address.postal_code,address.city].filter(Boolean).join(' ')].filter(Boolean).join(', ')).filter(Boolean).join(' / ');
}
async function contactsView() {
  const response=await api.get(biz('/contacts')),contacts=collection(response);
  return el('div',{class:'stack contacts-workspace'},heading('Kontakte','Kunden, Lieferanten und Partner mit nachvollziehbaren Projektbezügen.',[...(response.can_create&&has('contacts.write')?[button('Kontakt anlegen',()=>contactDialog(),'primary')]:[]),...(state.features.has('sales_pipeline')&&has('contacts.read')?[button('Vertriebspipeline',()=>action(()=>sales.open()))]:[])]),
    has('privacy.manage')&&state.features.has('privacy_cases')?panel('Datenschutzfälle',button('Datenschutzfälle öffnen',()=>action(()=>privacyCases.open()),'small')):null,
    panel('Kontaktkartei',rows(contacts,item=>row(item.name,[item.email,item.phone,contactAddressSummary(item)].filter(Boolean).join(' · '),[has('projects.manage')&&item.active&&(item.kinds||[]).includes('customer')?button('Projekt anlegen',()=>action(()=>newProjectDialog(item.id)),'small'):null,state.features.has('custom_fields')?button('Zusatzfelder',()=>action(()=>customFields.open('contact',item.id)),'small'):null,...(item.kinds||[]).map(kind=>badge(({customer:'Kunde',supplier:'Lieferant',partner:'Partner'})[kind])),has('contacts.write')?button('Bearbeiten',()=>action(async()=>contactDialog(await api.get(biz('/contacts/'+item.id)))),'small'):null,state.features.has('communication_history')&&has('contacts.read')?button('Kommunikationsverlauf',()=>action(()=>communicationHistory.open(item.id)),'small'):null,state.features.has('sales_pipeline')&&has('contacts.read')?button('Verkaufschancen',()=>action(()=>sales.open(item.id)),'small'):null,state.features.has('service_cases')&&has('contacts.read')?button('Servicefälle',()=>action(()=>customerService.open({customer_id:item.id})),'small'):null]))));
}
const communicationHistory=createCommunicationHistory({api,biz,el,button,notice,formatDate,action,dialog,openProject,stamp:()=>`${api.generation}/${state.render}`,allowed:()=>state.features.has('communication_history')&&has('contacts.read')});
const sales=createSales({api,biz,el,button,pricePicker,panel,row,rows,notice,empty,form,field,dialog,table,formatDate,action,mutation,refresh,openProject,documentDetail,actorId:()=>state.user?.id,permission:has,allowed:()=>state.features.has('sales_pipeline')&&has('contacts.read'),writable:()=>!state.readonly&&has('contacts.write')});
const customFields=customFieldsUi({api,biz,el,button,field,form,dialog,panel,rows,row,notice,table,mutation,action,enabled:()=>!!state.user&&state.features.has('custom_fields'),admin:()=>has('settings.manage'),writable:()=>!state.readonly,stamp:()=>JSON.stringify([state.user?.id,state.generation,[...state.globalPermissions],[...state.permissions],state.projectId])});
function contactAddressEditor(initial=[]) {
  const container=el('div',{class:'stack'}),list=el('div',{class:'stack'}),records=[];
  function add(value={}) {
    if(records.length>=20)return;
    const node=el('fieldset',{class:'panel stack'}),inputs={},record={node,inputs,id:value.id};
    node.append(el('legend',{},'Kontaktadresse'));
    const purpose=el('select',{'aria-label':'Adresszweck'},[['billing','Rechnungsadresse'],['site','Objektadresse'],['delivery','Lieferadresse'],['other','Weitere Adresse']].map(([id,label])=>el('option',{value:id,selected:id===(value.purpose||'billing')},label)));
    inputs.purpose=purpose;node.append(el('label',{class:'field'},'Adresszweck',purpose));
    const grid=el('div',{class:'form-grid'});
    for(const [name,label,maxLength]of [['label','Adressbezeichnung',200],['street','Straße / Hausnummer',1000],['postal_code','Postleitzahl',30],['city','Ort',200],['country','Land (Ländercode)',2]]){
      const input=el('input',{'aria-label':label,value:value[name]??(name==='country'?'DE':''),maxLength,required:name==='country'});
      inputs[name]=input;grid.append(el('label',{class:'field'},label,input));
    }
    node.append(grid,button('Adresse entfernen',()=>{node.remove();records.splice(records.indexOf(record),1);},'small'));records.push(record);list.append(node);
  }
  for(const address of initial)add(address);
  container.append(el('h3',{},'Strukturierte Adressen'),el('p',{class:'caption'},'Für die Rechnungsadresse Straße, Postleitzahl, Ort und Land getrennt erfassen. Vorhandene weitere Adressen bleiben erhalten.'),list,button('Rechnungsadresse hinzufügen',()=>add(),'small'));
  container.values=()=>records.map(record=>({...record.id?{id:record.id}:{},...Object.fromEntries(Object.entries(record.inputs).map(([name,input])=>[name,name==='country'?input.value.trim().toUpperCase():input.value.trim()]))}));
  return container;
}
function contactDialog(contact=null) {
  const fields=[field('name','Name / Firma','text',contact?.name||'',{required:true}),field('entity_type','Kontakttyp','select',contact?.entity_type||'company',{options:[['company','Unternehmen'],['person','Person']]}),field('kinds','Beziehungen','multi',contact?.kinds||['customer'],{options:[['customer','Kunde'],['supplier','Lieferant'],['partner','Partner']],required:true}),field('contact','Ansprechpartner','text',contact?.contact||''),field('email','E-Mail','email',contact?.email||''),field('phone','Telefon','tel',contact?.phone||''),field('address','Adresse','textarea',contact?.address||''),field('notes','Interne Notizen','textarea',contact?.notes||'')];
  const addresses=contactAddressEditor(contact?.addresses||[]);
  dialog(contact?'Kontakt bearbeiten':'Neuer Kontakt',form('',fields,(data,key)=>mutation(key,'/contacts'+(contact?'/'+contact.id:''),{...data,addresses:addresses.values(),...(contact?{revision:contact.revision}:{})}),{key:'contact-'+(contact?.id||'new'),extra:addresses}));
}

async function planningView() { return el('div',{class:'stack'},heading('Einsatzplanung','Ein gemeinsamer Kalender für Projekte, Team und Ressourcen.'),await planningContent(state.projectId)); }
function planningControls(range) {
  const update=async values=>{
    const proposed={...state.planning,...values};
    try{planningRange(proposed.mode,proposed.anchor,proposed.years);}catch(error){await refresh();showError(error);return;}
    state.planning=proposed;await refresh();
  };
  const {mode,anchor,years}=state.planning;
  const picker=mode==='week'?el('label',{class:'field'},'Woche auswählen',el('input',{type:'date',value:anchor,min:'1900-01-01',max:'2200-12-31',onChange:event=>{try{planningRange(mode,event.target.value,years);update({anchor:event.target.value});}catch(error){showError(error);}}})):
    mode==='month'?el('label',{class:'field'},'Monat auswählen',el('input',{type:'month',value:anchor.slice(0,7),min:'1900-01',max:'2200-12',onChange:event=>{try{const value=event.target.value+'-01';planningRange(mode,value,years);update({anchor:value});}catch(error){showError(error);}}})):
      el('label',{class:'field'},mode==='multi'?'Startjahr':'Planungsjahr',el('input',{type:'number',value:Number(anchor.slice(0,4)),min:1900,max:mode==='multi'?2201-years:2200,step:1,onChange:event=>{
        try{if(!/^\d{4}$/.test(event.target.value))throw new Error('Ein gültiges vierstelliges Jahr eingeben.');const value=event.target.value+'-01-01';planningRange(mode,value,years);update({anchor:value});}catch(error){showError(error);}
      }}));
  return el('div',{class:'planning-toolbar'},select('Planungsansicht',[['week','Woche'],['month','Monat'],['year','Jahr'],['multi','Mehrere Jahre']],mode,value=>update({mode:value})),picker,
    mode==='multi'?select('Zeitraum',[['2','2 Jahre'],['3','3 Jahre']],String(years),value=>update({years:Number(value)})):null,
    el('div',{class:'actions period-navigation'},button('Zurück',()=>action(async()=>update({anchor:shiftPlanningAnchor(mode,anchor,-1,years)})),'small'),button('Heute',()=>update({anchor:dateInput()}),'small'),button('Weiter',()=>action(async()=>update({anchor:shiftPlanningAnchor(mode,anchor,1,years)})),'small')),
    el('p',{class:'planning-range',role:'status'},formatDate(range.from)+' – '+formatDate(range.to)));
}
function projectDatesDialog(item) {
  if(item.can_edit!==true||state.readonly||!organizationModuleEnabled('planning',state.organization))return;
  dialog('Projektzeitraum: '+item.name,form('',[
    field('start_date','Projektbeginn','date',item.start_date||'',{min:'1900-01-01',max:'2200-12-31',help:'Leer lassen, solange der Beginn nicht feststeht.'}),
    field('end_date','Projektende','date',item.end_date||'',{min:'1900-01-01',max:'2200-12-31',help:'Leer lassen, solange das Ende nicht feststeht.'})],(data,key)=>{
      if(data.start_date&&data.end_date&&data.end_date<data.start_date)throw new Error('Das Projektende muss am oder nach dem Beginn liegen.');
      return mutation(key,`/planning/projects/${item.id}/dates`,{revision:item.revision,start_date:data.start_date||null,end_date:data.end_date||null});
    },{key:'project-dates-'+item.id,submit:'Zeitraum speichern'}),'Es werden nur diese Projekttermine geändert. Einzelne Kalendereinsätze behalten ihre eigenen Zeiten.');
}
function projectTimeline(data,range,mode) {
  const items=[...(data.items||[]),...(data.unplanned||[])],ticks=planningTicks(mode,range);
  if(!items.length)return panel('Projektzeiträume',empty('In diesem Zeitraum sind keine freigegebenen Projekte geplant oder ungeplant.'));
  const sheet=el('div',{class:'timeline-sheet'}),grid=el('div',{class:'timeline-gridlines','aria-hidden':'true'});
  sheet.style.minWidth=(220+Math.max(650,ticks.length*(mode==='month'?27:mode==='week'?90:85)))+'px';
  const axis=el('div',{class:'timeline-axis-track'});
  for(const tick of ticks){
    const label=el('span',{class:'timeline-tick'},tick.label);label.style.left=tick.left+'%';label.style.width=tick.width+'%';axis.append(label);
    const line=el('span',{});line.style.left=tick.left+'%';grid.append(line);
  }
  sheet.append(grid,el('div',{class:'timeline-axis'},el('div',{class:'timeline-project-label'},'Projekt'),axis));
  for(const item of items){
    const position=timelinePlacement(item,range),dates=item.start_date&&item.end_date?formatDate(item.start_date)+' – '+formatDate(item.end_date):
      item.start_date?'Beginn '+formatDate(item.start_date)+' · Ende offen':item.end_date?'Beginn offen · Ende '+formatDate(item.end_date):'Beginn und Ende offen';
    const label=el('div',{class:'timeline-project-label'},el('strong',{},item.name),el('small',{},dates),item.status?el('small',{class:'timeline-status'},item.status.name):null,
      item.can_edit===true&&!state.readonly&&organizationModuleEnabled('planning',state.organization)?el('button',{type:'button',class:'button small timeline-edit','aria-label':'Projektzeitraum ändern: '+item.name,onClick:()=>projectDatesDialog(item)},'Zeitraum ändern'):null);
    const track=el('div',{class:'timeline-track'});
    if(position){
      const bar=el('span',{class:'timeline-project-bar'+(position.clippedStart?' clipped-start':'')+(position.clippedEnd?' clipped-end':''),role:'img',
        'aria-label':item.name+': '+dates,'data-start':item.start_date,'data-end':item.end_date,title:item.name+' · '+dates},el('span',{},dates));
      bar.style.left=position.left+'%';bar.style.width=position.width+'%';track.append(bar);
    }else track.append(el('span',{class:'timeline-unplanned'},item.planning_state==='partial'?'Teilweise geplant · '+dates:'Ungeplant · '+dates));
    sheet.append(el('div',{class:'timeline-row','data-project-id':item.id},label,track));
  }
  return panel('Projektzeiträume',el('p',{class:'caption'},'Balken zeigen gespeicherten Projektbeginn und Projektende einschließlich beider Tage. Offene Zeiträume bleiben ungeplant. Die Ansicht lässt sich seitlich scrollen.'),
    el('div',{class:'timeline-scroll',role:'region','aria-label':'Projektzeitleiste '+formatDate(range.from)+' bis '+formatDate(range.to),tabIndex:0},sheet));
}
async function planningContent(projectId='') {
  const enhanced=state.features.has('project_timeline'),mode=enhanced?state.planning.mode:'week',range=planningRange(mode,enhanced?state.planning.anchor:dateInput(),state.planning.years);
  const timeline=enhanced?await api.get(query(biz('/planning/timeline'),{from:range.from,to:range.to,project_id:projectId})):null;
  const controls=el('div',{class:'stack'},enhanced?planningControls(range):null,resourceCustodyAllowed()?button('Betriebsmittel und Nachweise',()=>action(()=>resourceCustody.open(projectId||null))):null);
  if(!['week','month'].includes(mode))return el('div',{class:'stack'},controls,projectTimeline(timeline,range,mode));
  const [calendar,employees,resources]=await Promise.all([api.get(query(biz('/planning/calendar'),{from:range.from,to:range.to,project_id:projectId})),api.get(query(biz('/employees'),{project_id:projectId})),api.get(biz('/resources'))]);
  const appointments=calendar.appointments||[],days=[];
  for(let index=0;index<range.days;index++) {
    const dayId=utcDate(new Date(calendarDay(range.from).getTime()+index*DAY_MS)),day=new Date(dayId+'T12:00:00');
    const column=el('section',{class:'day','aria-label':formatDate(dayId)},el('h3',{},new Intl.DateTimeFormat('de-DE',{weekday:'short',day:'2-digit',month:'2-digit'}).format(day)));
    appointments.filter(item=>dateInput(new Date(item.start_at))===dayId).forEach(item=> {
      const node=el('button',{type:'button',class:'appointment',draggable:canWrite('planning.write','planning'),onClick:()=>appointmentDialog(item,collection(employees),collection(resources))},
        new Intl.DateTimeFormat('de-DE',{hour:'2-digit',minute:'2-digit'}).format(new Date(item.start_at)),el('strong',{},item.title),el('small',{},item.project_name||state.projects.find(p=>p.id===item.project_id)?.name||'Interner Einsatz'));
      node.addEventListener('dragstart',event=>event.dataTransfer.setData('text/plain',item.id));column.append(node);
    });
    if(canWrite('planning.write','planning')) {
      column.addEventListener('dragover',event=>{event.preventDefault();column.classList.add('drag-over');});column.addEventListener('dragleave',()=>column.classList.remove('drag-over'));
      column.addEventListener('drop',event=> {event.preventDefault();column.classList.remove('drag-over');const item=appointments.find(a=>a.id===event.dataTransfer.getData('text/plain'));if(!item)return;
        action(async()=> {const oldStart=new Date(item.start_at),oldEnd=new Date(item.end_at),moved=new Date(day);moved.setHours(oldStart.getHours(),oldStart.getMinutes(),0,0);
          await mutation('move-'+item.id,`/appointments/${item.id}`,{revision:item.revision,project_id:item.project_id,start_at:moved.toISOString(),end_at:new Date(moved.getTime()+oldEnd.getTime()-oldStart.getTime()).toISOString()});await refresh();});});
    }
    days.push(column);
  }
  const calendarGrid=el('div',{class:'calendar'+(mode==='month'?' calendar-month':'')},days);
  if(mode==='month')days[0].style.gridColumnStart=String((calendarDay(range.from).getUTCDay()+6)%7+1);
  const board=panel(mode==='month'?'Monatskalender':'Wochenkalender',el('div',{class:'actions'},canWrite('planning.write','planning')?button('Termin planen',()=>appointmentDialog(null,collection(employees),collection(resources)),'primary'):null),
    el('p',{class:'caption'},'Kalenderzeiten werden in Ihrer Gerätezeitzone angezeigt. Termine lassen sich auch ohne Ziehen per Formular ändern.'),el('div',{class:'table-scroll'},calendarGrid));
  return el('div',{class:'stack'},controls,board,enhanced?projectTimeline(timeline,range,mode):null,panel('Abwesenheiten & Belegungen',rows(calendar.absences||[],item=>row(item.employee_name||'Abwesenheit',`${formatDate(item.start_date)} – ${formatDate(item.end_date)}`,[badge(item.status||'Geplant')]),'Keine Abwesenheiten für diesen Zeitraum gemeldet.')));
}
function appointmentDialog(item,employees,resources) {
  const begin=new Date();begin.setMinutes(0,0,0);const end=new Date(begin);end.setHours(end.getHours()+1);
  const fields=[projectField(item?.project_id||state.projectId),field('title','Termin','text',item?.title||'',{required:true}),field('start_at','Beginn (Gerätezeit)','datetime-local',localDateTime(item?.start_at||begin),{required:true}),field('end_at','Ende (Gerätezeit)','datetime-local',localDateTime(item?.end_at||end),{required:true}),field('employee_ids','Mitarbeitende','multi',item?.employee_ids||[],{options:options(employees)}),field('resource_ids','Fahrzeuge / Werkzeuge','multi',item?.resource_ids||[],{options:options(resources)}),field('details','Details','textarea',item?.details||'')];
  if(!item)fields.push(field('frequency','Wiederholung','select','',{options:[['','Einmalig'],['daily','Täglich'],['weekly','Wöchentlich'],['monthly','Monatlich']]}),field('count','Anzahl Termine','integer',4,{min:1,max:104}));
  dialog(item?'Termin ansehen / ändern':'Termin planen',form('',fields,(data,key)=> {const {frequency,count,...values}=data;return mutation(key,'/appointments'+(item?'/'+item.id:''),{...values,timezone:'Europe/Berlin',...(item?{revision:item.revision}:frequency?{recurrence:{frequency,interval:1,count}}:{})});},{key:'appointment-'+(item?.id||'new'),readonly:!canWrite('planning.write','planning')}),'Ressourcenüberschneidungen werden serverseitig geprüft. Eine Konfliktmeldung wird nicht automatisch übergangen.');
}

async function documentsView() { return el('div',{class:'stack'},heading('Dokumente','Belege und Berichte bleiben mit ihrem Projekt verknüpft.'),await documentsContent(state.projectId)); }
async function documentsContent(projectId='') {
  const workspaceGeneration=api.generation,workspaceRender=state.render,workspaceSection=state.section;
  const workspaceCurrent=()=>api.generation===workspaceGeneration&&state.render===workspaceRender&&state.projectId===projectId&&state.section===workspaceSection;
  let customerWorkspace=null;
  if(projectId&&state.features.has('customer_workspace_portal')){
    const capabilities=await api.get(query(biz('/capabilities'),{project_id:projectId}));
    if(workspaceCurrent()&&customerWorkspaceRights(capabilities,state.organization).read)customerWorkspace=await renderCustomerWorkspace({api,projectId,capabilities,organization:state.organization,isCurrent:workspaceCurrent,onChange:()=>{if(workspaceCurrent())updatePending();}});
  }
  const commercial=has('finance.read')?collection(await api.get(query(biz('/documents'),{project_id:projectId}))):[];
  const signed=projectId?collection(await api.get(query(biz('/service-reports'),{project_id:projectId}))):[];
  return el('div',{class:'stack'},has('finance.read')?panel('Angebote & Belege',canWrite('finance.write','documents')?button('Belegentwurf erstellen',()=>documentDialog(null,projectId),'primary'):null,
    rows(commercial,item=>row(item.title||LABELS[item.kind],`${item.number||'Noch ohne Nummer'} · ${formatDate(item.issue_date)} · ${formatMoney(item.totals?.gross)}`,[badge(item.status),button('Öffnen',()=>action(()=>documentDetail(item.id)),'small')]),'Noch keine eigenen kaufmännischen Belege vorhanden.')):notice('Kaufmännische Belege benötigen eine gesonderte Freigabe. Operative Berichte finden Sie im Projekt.'),
    projectId?panel('Serviceberichte',rows(signed,item=>row(item.title,item.offline_capture?`Offline unterzeichnet: ${formatDate(item.offline_capture.signed_at,true)} (Geräteangabe) · Empfangen: ${formatDate(item.offline_capture.received_at,true)}`:formatDate(item.created_at,true),[badge(item.status),item.status==='signed'?button('PDF',()=>action(()=>download(biz('/service-reports/'+item.id+'/pdf'),'Servicebericht.pdf')),'small'):has('documents.write')?button('Unterzeichnen',()=>signatureDialog(item,'service-reports'),'small'):null]))):empty('Ein Projekt auswählen, um operative Serviceberichte anzuzeigen.'),customerWorkspace);
}
function positionEditor(initial=[]) {
  const container=el('div',{class:'stack'}),list=el('div',{class:'stack'}),records=[],stamp=`${api.generation}/${state.render}`;let catalog=[];
  function current(){return container.isConnected&&stamp===`${api.generation}/${state.render}`&&document.visibilityState!=='hidden'&&has('finance.read');}
  function choices(record){const selected=record.articleSelect.value;record.articleSelect.replaceChildren(el('option',{value:''},'Eigene manuelle Position'),...catalog.map(article=>el('option',{value:article.id,selected:article.id===selected},`${article.code||''} · ${article.name} (${article.unit})${article.price_policy==='dated_catalog'?' · datierter Preis':''}`)));if(selected&&!catalog.some(item=>item.id===selected))record.articleSelect.append(el('option',{value:selected,selected:true},record.original.description||'Gespeicherte Artikelposition'));}
  function add(value={}) {
    if(records.length>=200)return;
    if(value.source_type==='time'){
      const record={sourceTime:true,original:structuredClone(value)},node=el('fieldset',{class:'panel stack'},el('legend',{},'Gebundene Arbeitszeit'),el('p',{},value.description),el('p',{class:'muted'},`${value.source_seconds} Sekunden · ${formatMoney(value.unit_price_net)} / ${value.price_base_quantity} Sekunden · ${value.tax_rate} % USt.`),notice('Die freigegebene Zeit und ihr Originalnachweis bleiben unverändert. Zum erneuten Übernehmen die Position ausdrücklich entfernen.'));
      record.node=node;node.append(button('Zeitposition entfernen',()=>{node.remove();records.splice(records.indexOf(record),1);},'small'));records.push(record);list.append(node);return;
    }
    const controls={},node=el('fieldset',{class:'panel stack'}),record={controls,original:structuredClone(value),article:value.article_id?{id:value.article_id,revision:value.article_revision,unit:value.unit,name:value.description,...(value.catalog_price_snapshot?{price_policy:'dated_catalog'}:{})}:null,changed:false},articleSelect=el('select',{'aria-label':'Preisquelle der Belegposition'});record.articleSelect=articleSelect;
    record.node=node;
    articleSelect.append(el('option',{value:''},'Eigene manuelle Position'));if(value.article_id)articleSelect.append(el('option',{value:value.article_id,selected:true},value.description));
    node.append(el('legend',{},'Belegposition'),el('label',{class:'field'},'Artikel oder eigene Position',articleSelect));
    const grid=el('div',{class:'form-grid'});
    for(const [name,label,defaultValue]of [['description','Beschreibung',''],['quantity','Menge','1'],['unit','Einheit','Stk.'],['unit_price_net','Netto / Einheit','0.00'],['price_base_quantity','Preisbasis / Bezugsmenge','1'],['tax_rate','MwSt. %','19']]){
      const input=el('input',{value:value[name]??defaultValue,required:true,'aria-label':label,inputMode:['quantity','unit_price_net','price_base_quantity','tax_rate'].includes(name)?'decimal':undefined,maxLength:name==='description'?10000:100});controls[name]=input;grid.append(el('label',{class:'field'},label,input));
    }
    controls.kind=el('select',{'aria-label':'Positionsart'},['material','labor','service','machine'].map(type=>el('option',{value:type,selected:type===(value.kind||'service')},LABELS[type])));grid.append(el('label',{class:'field'},'Art',controls.kind));node.append(grid);
    const picker=pricePicker({article:()=>record.article,priceRole:'sales_net',initial:value.catalog_price_snapshot||null,onSelected:item=>{if(item){controls.unit_price_net.value=item.price.price_net;controls.price_base_quantity.value=item.price.price_base_quantity;controls.unit.value=item.price.unit;controls.tax_rate.value=item.price.tax_rate;}}});record.picker=picker;node.append(picker);
    function lockPrice(){const managed=record.article?.price_policy==='dated_catalog';for(const key of ['unit_price_net','price_base_quantity','unit'])controls[key].readOnly=managed;}
    articleSelect.addEventListener('change',()=>{record.changed=true;record.article=catalog.find(item=>item.id===articleSelect.value)||null;picker.reset();if(record.article){const article=record.article;controls.description.value=article.name;controls.unit.value=article.unit;controls.kind.value=article.kind;controls.tax_rate.value=article.tax_rate;controls.price_base_quantity.value=article.price_base_quantity||'1';controls.unit_price_net.value=article.price_policy==='dated_catalog'?'':article.unit_price_net;}else{controls.unit_price_net.value='';controls.price_base_quantity.value='1';}lockPrice();});lockPrice();
    node.append(button('Position entfernen',()=>{node.remove();records.splice(records.indexOf(record),1);},'small'));records.push(record);list.append(node);choices(record);
  }
  initial.forEach(add);if(!initial.length)add();container.append(list,button('Position hinzufügen',()=>add(),'small'));
  container.values=()=>records.map(record=>{
    if(record.sourceTime)return structuredClone(record.original);
    const controls=record.controls,result={...(record.changed?{}:record.original),description:controls.description.value,quantity:decimalText(controls.quantity.value),unit:controls.unit.value,unit_price_net:decimalText(controls.unit_price_net.value),price_base_quantity:decimalText(controls.price_base_quantity.value),tax_rate:decimalText(controls.tax_rate.value),kind:controls.kind.value};
    if(record.changed&&record.original.id)result.id=record.original.id;
    if(record.article){result.article_id=record.article.id;result.article_revision=record.article.revision;if(record.article.price_policy==='dated_catalog'&&(!record.original.id||record.changed||record.picker.dirty)){result.catalog_price_selection=record.picker.selection();delete result.catalog_price_snapshot;}}
    return result;
  });
  container.removeEmpty=()=>{for(const record of [...records])if(!record.sourceTime&&!Object.keys(record.original).length&&!record.article&&Object.entries({description:'',quantity:'1',unit:'Stk.',unit_price_net:'0.00',price_base_quantity:'1',tax_rate:'19',kind:'service'}).every(([key,value])=>record.controls[key].value===value)){record.node.remove();records.splice(records.indexOf(record),1);}};
  if(has('finance.read'))api.get(biz('/articles')).then(response=>{if(!current())return;catalog=collection(response).filter(article=>article.active);for(const record of records){if(record.sourceTime)continue;choices(record);if(!record.original.catalog_price_snapshot&&record.article){const found=catalog.find(item=>item.id===record.article.id);if(found?.price_policy==='dated_catalog'){record.article.price_policy='dated_catalog';record.picker.hidden=false;}}}}).catch(error=>{if(current())container.prepend(notice(error.message,'error'));});
  return container;
}
export function documentConversionTargets(item) {
  if(['advance_invoice','cumulative_invoice'].includes(item.kind)&&item.status!=='final')return [];
  return ({estimate:['offer','order_confirmation'],offer:['order_confirmation','invoice','advance_invoice','delivery_note'],order_confirmation:['delivery_note','invoice','advance_invoice','final_invoice'],delivery_note:['invoice'],advance_invoice:['cumulative_invoice','final_invoice'],cumulative_invoice:['cumulative_invoice','final_invoice']})[item.kind]||[];
}
function documentDialog(item=null,projectId='') {
  const key='document-'+(item?.id||'new'),path='/documents'+(item?'/'+item.id:''),pending=api.pendingCommandValues(key,biz(path));
  let ownerStamp,formPanel,timeDraft=documentTimeCommand(key,biz(path),pending);
  const stamp=()=>`${api.generation}/${state.render}/${dialogGeneration}`;
  const alive=()=>formPanel?.isConnected&&stamp()===ownerStamp&&document.visibilityState!=='hidden';
  async function saved(result){
    const generation=api.generation,render=state.render+1;
    await refresh();
    const current=()=>generation===api.generation&&render===state.render&&!modal;
    if(timeDraft&&current())await documentDetail(result.id,{stillCurrent:current,timeReview:documentTimesChanged(result)});
  }
  if(pending){
    formPanel=el('div',{class:'stack'},notice('Für diesen Beleg ist eine Antwort offen. Es wird ausschließlich der unveränderte Originalauftrag erneut gesendet. Neue Positionen erst nach dessen Klärung erfassen.','warn'),button('Unveränderten Belegauftrag erneut senden',()=>action(async()=>{const result=await api.retry(key,{stillCurrent:alive});if(!alive())return;closeModal();await saved(result);},formPanel),'primary'));
    dialog('Belegantwort klären',formPanel);ownerStamp=stamp();return;
  }
  const editor=positionEditor(item?.positions||[]);
  const fields=[projectField(item?.project_id||projectId||state.projectId),field('kind','Belegart','select',item?.kind||'offer',{options:['estimate','offer','order_confirmation','delivery_note','invoice','advance_invoice','cumulative_invoice','final_invoice'].map(kind=>[kind,LABELS[kind]]),required:true}),field('title','Titel','text',item?.title||'Angebot',{required:true}),field('issue_date','Belegdatum','date',item?.issue_date||dateInput(),{required:true}),field('due_date','Fällig am','date',item?.due_date||dateInput(),{required:true}),field('intro','Einleitung','textarea',item?.intro||''),field('notes','Hinweise','textarea',item?.notes||'')];
  const prior=Array.isArray(item?.previous_document_ids)?item.previous_document_ids:[];
  const times=documentTimePicker({api,el,button,notice,formatDate,stamp,project:()=>formPanel.controls.get('project_id').input.value,positions:()=>editor.values(),onSelect:()=>editor.removeEmpty()});
  function freeze(){times.freeze();formPanel.querySelectorAll('input,select,textarea,button[type="button"]').forEach(input=>input.disabled=true);formPanel.querySelector('button[type="submit"]').textContent='Unveränderten Belegauftrag erneut senden';}
  formPanel=form('',fields,async(data,key)=>{
    if(!alive())return;
    const requestAlive=()=>alive()&&formPanel.controls.get('project_id').input.value===data.project_id;
    const controls=[...formPanel.querySelectorAll('input,select,textarea,button[type="button"]')],disabled=controls.map(input=>input.disabled);
    controls.forEach(input=>input.disabled=true);
    times.busy(true);
    try{
      const old=api.pendingCommandValues(key,biz(path));
      let command=old,selected=[];
      if(!old){
        const selection=await times.prepare();if(!requestAlive())return;selected=selection.selected;
        const positions=editor.values();
        if(positions.some(position=>position.source_type==='time')){await documentTimeContext(api,data.project_id);if(!requestAlive())return;}
        command={...data,positions,...selection.data,...(item?{revision:item.revision,previous_document_ids:[...prior]}:{})};
      }
      const expected={project:command.project_id,identifier:item?.id,revision:item?.revision,selected,existing:command.positions.filter(position=>position.source_type==='time'),rate:command.hourly_rate_net,tax:command.time_tax_rate};
      timeDraft=documentTimeCommand(key,biz(path),command);
      const result=await mutation(key,path,command,{stillCurrent:requestAlive,...(!old&&documentTimeCommand(key,biz(path),command)?{validate:value=>documentTimeReceipt(value,expected)}:{})});
      return requestAlive()?result:undefined;
    }catch(error){if(!alive())return;if(api.pendingCommandValues(key,biz(path)))freeze();throw error;}
    finally{if(alive()&&!api.pendingCommandValues(key,biz(path))){controls.forEach((input,index)=>input.disabled=disabled[index]);times.busy(false);}}
  },{key,extra:el('div',{},prior.length?notice(`${prior.length} Vorbeleg(e) sind durch die Umwandlung verknüpft. Die Positionen müssen die gesamte bisherige Vertragsleistung enthalten. Der Server zieht die bereits berechnete Vertragsbasis ab.`):null,times.element,el('h3',{},'Positionen'),editor),submit:'Entwurf speichern',after:saved});
  if(item){formPanel.controls.get('project_id').input.disabled=true;formPanel.controls.get('kind').input.disabled=true;}
  formPanel.controls.get('project_id').input.addEventListener('change',()=>{void times.load();});
  editor.addEventListener('click',event=>{if(event.target?.textContent==='Zeitposition entfernen')void times.load();});
  dialog(item?'Belegentwurf bearbeiten':'Neuer Belegentwurf',formPanel,'Summen und Steuer berechnet und prüft der Server. Für eine Rechnungskette den neuesten festgeschriebenen Abschlag oder kumulativen Beleg öffnen und in die nächste Rechnung umwandeln.');ownerStamp=stamp();times.start();
}
async function documentDetail(id,{stillCurrent=()=>true,timeReview=false}={}) {
  const item=await api.get(biz('/documents/'+id));
  if(!stillCurrent())return;
  const controls=[button(item.status==='final'?'Original-PDF':'PDF-Vorschau',()=>action(()=>download(biz(`/documents/${id}/${item.status==='final'?'pdf':'preview'}`),(item.number||item.title)+'.pdf')),'small')];
  if(item.status==='draft'&&canWrite('finance.write','documents'))controls.push(button('Bearbeiten',()=>documentDialog(item),'small'));
  if(item.status==='draft'&&canWrite('finance.issue','documents'))controls.push(button('Festschreiben',()=>confirmDialog('Beleg festschreiben','Die geprüfte Fassung wird unveränderlich archiviert und erhält eine Nummer. Es erfolgt kein automatischer Versand.',async()=>{await mutation('finalize-'+id,`/documents/${id}/finalize`,{revision:item.revision});refresh();}),'primary'));
  const targets=documentConversionTargets(item);
  if(canWrite('finance.write','documents'))targets.forEach(kind=>controls.push(button('→ '+LABELS[kind],()=>action(async()=>{const result=await mutation('convert-'+id+'-'+kind,`/documents/${id}/convert`,{revision:item.revision,target_kind:kind});closeModal();await documentDetail(result.id);}), 'small')));
  let portal=null;
  if(item.kind==='offer'&&item.status==='final'){
    if(state.features.has('offer_portal')){const capabilities=await api.get(query(biz('/capabilities'),{project_id:item.project_id}));
      if(portalAccess(item,capabilities,state.organization).read)portal=panel('Kundenportal',button('Kundenportal verwalten',()=>action(()=>portalOfferDialog(item)),'primary'),el('p',{class:'muted'},'Die geprüfte Angebotsfassung gezielt freigeben, Kundenerklärungen einsehen oder Zugänge widerrufen.'));}
    else portal=notice('Dieser Server bietet derzeit keinen erreichbaren Angebotsportalzugang.');
  }
  if(!stillCurrent())return;
  dialog(item.number||item.title,el('div',{class:'stack'},timeReview?notice('Arbeitszeiten wurden während der Übernahme geändert. Der gespeicherte Entwurf enthält den aktuellen Stand. Bitte die Zeitpositionen vor der Festschreibung prüfen.','warn'):null,el('div',{class:'actions'},badge(item.status),...controls),portal,panel('Empfänger',el('h3',{},item.buyer?.name),el('p',{class:'muted'},[item.buyer?.address_line,[item.buyer?.postal_code,item.buyer?.city].filter(Boolean).join(' '),item.buyer?.country].filter(Boolean).flatMap((line,index)=>[index?el('br'):null,line]))),
    panel('Positionen',table(['Beschreibung','Menge','Einheit','Netto'],(item.positions||[]).map(line=>[line.catalog_price_snapshot?`${line.description} · ${line.catalog_price_snapshot.source_name} · ${line.catalog_price_snapshot.price.price_net} EUR / ${line.catalog_price_snapshot.price.price_base_quantity} ${line.unit} · Preisstand ${line.catalog_price_snapshot.effective_on}`:line.description,formatQuantity(line.quantity),line.unit,formatMoney(line.net)]))),
    item.contract_totals?panel('Rechnungskette',el('p',{},'Gesamte Vertragsleistung brutto: '+formatMoney(item.contract_totals.gross)),el('p',{},'Bereits berechnete Vertragsbasis brutto: '+formatMoney(item.previous_issued_gross)),...(item.previous_documents||[]).map(previous=>el('p',{},`Vorbeleg ${previous.number}: ${formatMoney(previous.gross)}`))):null,
    panel(item.contract_totals?'Zusätzlich berechneter Rechnungsbetrag':'Belegsumme',el('p',{},'Netto: '+formatMoney(item.totals?.net)),el('p',{},'Steuer: '+formatMoney(item.totals?.tax)),el('h2',{},'Brutto: '+formatMoney(item.totals?.gross)))));
}
async function portalOfferDialog(item){
  const generation=api.generation,previous=modal,render=state.render;
  const [overview,capabilities]=await Promise.all([api.get(query(biz('/portal/grants'),{offer_id:item.id})),api.get(query(biz('/capabilities'),{project_id:item.project_id}))]);
  if(generation!==api.generation||modal!==previous||render!==state.render)return;
  const access=portalAccess(item,capabilities,state.organization);if(!access.read)throw new ApiError('Keine Freigabe für dieses Angebotsportal.',403);
  const source=overview.source;portalSource(source);
  const decision=overview.decision,adoption=overview.adoption;
  dialog('Kundenportal · '+(item.number||item.title),el('div',{class:'stack'},
    notice('Freigegeben wird ausschließlich dieses finale Angebot. Ein Kundenlink wird manuell weitergegeben; die Anwendung versendet keine Nachricht.'),
    panel('Geprüfte Quelle',el('p',{},`${source.number} · Fassung ${source.source_revision} · ${formatMoney(item.totals?.gross)}`),
      button('Original-PDF prüfen',()=>action(()=>download(biz('/documents/'+item.id+'/pdf'),(source.number||'Angebot')+'.pdf')),'small')),
    access.create&&!collection(overview).some(grant=>grant.status==='active')?button('Kundenzugang freigeben',()=>portalGrantDialog(item,source),'primary'):
      !access.create?notice('Neue Freigaben und Übernahmen sind derzeit gesperrt. Vorhandene Zugänge können bei entsprechender Berechtigung widerrufen werden.'):
        notice('Ein aktiver Zugang besteht bereits. Für einen neuen Link zuerst diesen Zugang ausdrücklich widerrufen.'),
    panel('Kundenzugänge',rows(collection(overview),grant=>row(grant.principal?.name||'Empfänger',`${grant.principal?.email||''} · Erstellt ${formatDate(grant.created_at,true)} · Ablauf ${formatDate(grant.expires_at,true)}`,
      [badge({active:'Aktiv',expired:'Abgelaufen',revoked:'Widerrufen'}[grant.status]||grant.status),access.revoke&&grant.status!=='revoked'?button('Zugang widerrufen',()=>portalRevokeDialog(item,grant),'small'):null]),'Noch kein Kundenportalzugang freigegeben.')),
    decision?panel('Gespeicherte Kundenerklärung',el('h3',{},decision.decision==='accepted'?'Angebot angenommen':'Angebot abgelehnt'),el('p',{},decision.declared_name+' · '+formatDate(decision.created_at,true)),
      el('p',{class:'preserve'},decision.statement_text),adoption?notice('Übernommen in einen Auftragsbestätigungsentwurf am '+formatDate(adoption.created_at,true)+'.'):null,
      adoption?button('Auftragsentwurf öffnen',()=>action(()=>documentDetail(adoption.document_id)),'small'):access.adopt&&decision.decision==='accepted'?
        button('Annahme in Auftragsentwurf übernehmen',()=>portalAdoptDialog(item,source,decision),'primary'):null):panel('Kundenerklärung',empty('Bisher wurde keine Annahme oder Ablehnung dokumentiert.'))));
}
function portalGrantDialog(item,source){
  const generation=api.generation;let editor;
  editor=form('',[field('recipient_name','Vorgesehener Empfänger','text',item.buyer?.contact_name||item.buyer?.name||'',{required:true,maxLength:200}),
    field('recipient_email','E-Mail des vorgesehenen Empfängers','email',item.buyer?.email||'',{required:true,maxLength:254}),
    field('expires_in_days','Zugang gültig für Tage','integer',7,{required:true,min:1,max:30}),
    field('confirmation','Ich habe Angebotsfassung, Kundenbindung, Empfänger und Original-PDF geprüft und gebe diesen Zugang ausdrücklich frei.','checkbox',false,{required:true,wide:true})],
    async(data,key)=>{const result=await mutation(key,'/portal/grants',portalGrantData(source,data));if(generation!==api.generation||!editor.isConnected)return undefined;
      portalIssuedLink(result,location.hostname);return result;},
    {key:'portal-grant-'+item.id,submit:'Kundenzugang verbindlich freigeben',after:result=>portalGrantResultDialog(item,result)});
  dialog('Kundenzugang freigeben',editor,'Die Zugangsdauer ändert nicht die Bedingungen des finalen Angebots. Es erfolgt kein E-Mail-Versand.');
}
function portalGrantResultDialog(item,result){
  const url=portalIssuedLink(result,location.hostname);
  dialog(url?'Kundenlink einmalig sichern':'Freigabe vorhanden – Link nicht erneut verfügbar',el('div',{class:'stack'},
        el('p',{},result.grant.principal?.name+' · '+result.grant.principal?.email),
        url?el('label',{class:'field'},'Kundenlink',el('textarea',{readOnly:true,rows:5,'aria-label':'Kundenlink',value:url})):notice('Die Freigabe ist vorhanden. Ihr Geheimnis wird bei einer Wiederholung nicht erneut ausgegeben. Für einen neuen Link diese Freigabe ausdrücklich widerrufen und anschließend neu freigeben.','warn'),
        el('p',{class:'muted'},'Der Link ermöglicht Zugang zum Angebot bis Ablauf oder Widerruf. Geschützt aufbewahren und ausschließlich dem vorgesehenen Empfänger manuell weitergeben.'),
        el('div',{class:'actions'},button('Freigaben prüfen',()=>action(()=>portalOfferDialog(item)),'primary'),button('Diese Freigabe widerrufen',()=>portalRevokeDialog(item,result.grant),'small'))));
}
function portalRevokeDialog(item,grant){
  const generation=api.generation;let editor;
  editor=form('',[field('reason','Grund für den Widerruf','text','',{required:true,maxLength:500}),field('confirmation','Diesen Zugang und seine bestehenden Kundensitzungen ausdrücklich widerrufen.','checkbox',false,{required:true,wide:true})],
    async(data,key)=>{if(data.confirmation!==true)throw new Error('Widerruf ausdrücklich bestätigen.');
      // Safety operation remains available when the business module is paused.
      const result=await api.mutate(key,biz('/portal/grants/'+grant.id+'/revoke'),data);
      return generation===api.generation&&editor.isConnected?result:undefined;},
    {key:'portal-revoke-'+grant.id,submit:'Kundenzugang widerrufen',after:()=>portalOfferDialog(item)});
  dialog('Kundenzugang widerrufen',editor,grant.principal?.name+' · '+grant.principal?.email);
}
function portalAdoptDialog(item,source,decision){
  const generation=api.generation;let editor;
  editor=form('',[field('confirmation','Ich habe die angenommene Angebotsfassung geprüft und übernehme sie ausdrücklich in einen Auftragsbestätigungsentwurf im bestehenden Projekt.','checkbox',false,{required:true,wide:true})],
    async(data,key)=>{const result=await mutation(key,'/portal/offers/'+item.id+'/adopt',portalAdoptionData(source,decision,data.confirmation));return generation===api.generation&&editor.isConnected?result:undefined;},
    {key:'portal-adopt-'+item.id,submit:'Auftragsentwurf erstellen',after:result=>documentDetail(result.document_id)});
  dialog('Annahme in Auftragsentwurf übernehmen',editor,'Der Zielbeleg bleibt Entwurf. Es entstehen keine Rechnung, Zahlung, Termin- oder Materialbuchung und kein Versand.');
}
function confirmDialog(title,message,confirm) {
  const error=el('div',{}),submit=button('Verbindlich bestätigen',()=>action(async()=>{submit.disabled=true;try{await confirm();closeModal();}finally{submit.disabled=false;}},error),'primary');
  dialog(title,el('div',{},el('p',{},message),el('div',{class:'actions'},button('Abbrechen',()=>closeModal()),submit),error));
}
function table(headers,body) { return el('div',{class:'table-scroll'},el('table',{},el('thead',{},el('tr',{},headers.map(header=>el('th',{},header)))),el('tbody',{},body.map(values=>el('tr',{},values.map(value=>el('td',{},value))))))); }
function accountingTab(label,active,onClick) { return el('button',{type:'button',class:'tab','aria-pressed':active,onClick},label); }
async function financeView() {
  if(!has('finance.read')&&accountingRights().read)state.financeTab='accounting';
  const tabs=el('div',{class:'tabs','aria-label':'Finanzbereiche'},has('finance.read')?accountingTab('Zahlungen & offene Posten',state.financeTab==='payments',()=>{state.financeTab='payments';refresh();}):null,accountingTab('EÜR-Vorbereitung',state.financeTab==='accounting',()=>{state.financeTab='accounting';refresh();}));
  return el('div',{class:'stack'},tabs,bankWorkspace.available()?button('Bankabgleich öffnen',()=>action(()=>bankWorkspace.open())):null,state.financeTab==='accounting'?await accountingContent():await financePaymentsView());
}
async function financePaymentsView() {
  const [open,payments,outbox]=await Promise.all([api.get(query(biz('/finance/open-items'),{project_id:state.projectId})),api.get(biz('/finance/payments')),api.get(biz('/finance/outbox'))]);
  const invoices=collection(open);
  return el('div',{class:'stack'},heading('Finanzen','Bestätigte Zahlungen und offene Posten. Ein Freigabeschritt ersetzt keinen Versandnachweis.',canWrite('finance.write','finance')?[button('Zahlung erfassen',()=>paymentDialog(invoices),'primary')]:[]),
    panel('Offene Posten',rows(invoices,item=>row(`${item.number||item.id} · ${item.buyer?.name||''}`,`Fällig ${formatDate(item.due_date)} · Offen ${formatMoney(item.open)} · Bezahlt ${formatMoney(item.paid)}`,[badge(item.dunning_status||item.status||'open')]),'Keine offenen Posten vorhanden.')),
    panel('Zahlungseingänge',rows(collection(payments),item=>row(formatMoney(item.amount),`${formatDate(item.booking_date)} · ${item.reference||item.source_id}`,[badge(item.kind)]))),
    panel('Versandaufträge',rows(collection(outbox),item=>row(item.recipient||'Empfänger offen',`Mahnlevel ${item.level} · ${formatDate(item.created_at,true)}`,[badge(item.status)]),'Keine freigegebenen Versandaufträge vorhanden.')),
    has('finance.approve')?form('Mahnlauf prüfen',[],async(data,key)=>{const result=await mutation(key,'/finance/dunning/preview',{...data,...(state.projectId?{project_id:state.projectId}:{})});dunningDialog(collection(result));return undefined;},{key:'dunning-preview',submit:'Vorschläge für heute berechnen',description:'Der heutige Serverstichtag gilt. Der Vorschlag löst keine Nachricht und keine Mahnstufenfortschreibung aus.'}):null);
}
function paymentDialog(invoices) {
  dialog('Zahlungseingang erfassen',form('',[field('document_id','Rechnung','select','',{options:[['','Noch nicht zuordnen'],...invoices.map(item=>[item.id,`${item.number||item.id} · ${formatMoney(item.open)}`])]}),field('amount','Betrag EUR','decimal','',{required:true}),field('source_id','Eindeutige Buchungsreferenz','text','',{required:true,help:'Zum Beispiel die unveränderte Referenz des Kontoauszugs.'}),field('booking_date','Buchungsdatum','date',dateInput(),{required:true}),field('reference','Verwendungszweck','text')],(data,key)=>{const {document_id,...values}=data;const amount=decimalText(values.amount);const cents=amount.includes('.')?amount.padEnd(amount.indexOf('.')+3,'0'):amount+'.00';return mutation(key,'/finance/payments',{...values,amount:cents,kind:'receipt',currency:'EUR',allocations:document_id?[{document_id,amount:cents}]:[]});},{key:'payment-new'}),'Nur einen tatsächlich bestätigten Zahlungseingang buchen.');
}
function dunningDialog(items) {
  dialog('Mahnvorschläge',rows(items,item=>row(item.number||item.document_id,`${item.buyer?.name||''} · Offen ${formatMoney(item.open)} · Stufe ${item.level}`,[button('Freigeben',()=>confirmDialog('Mahnung freigeben','Empfänger, Betrag und Text prüfen. Ein Auftrag wird zur Zustellung vorbereitet; diese Ansicht behauptet keine versendete Nachricht.',async()=>{await mutation('dunning-approve-'+item.id,`/finance/dunning/proposals/${item.id}/approve`,{confirmation:true});refresh();}),'small')]),'Aktuell gibt es keine geeigneten Mahnvorschläge.'));
}

async function accountingAction(callback) {
  const generation=api.generation,previous=modal,render=state.render;
  try { return await callback(); }
  catch(error) {
    if(generation!==api.generation||previous!==modal||render!==state.render)return;
    if([403,404].includes(error.status)){closeModal();await refresh();}
    if(generation===api.generation)showError(error);
  }
}
async function accountingSave(editor,generation,key,path,data) {
  try {
    const result=await mutation(key,path,data);
    if(generation!==api.generation||!editor.isConnected)return undefined;
    return result;
  } catch(error) {
    if(generation!==api.generation||!editor.isConnected)return undefined;
    if([403,404].includes(error.status)) {
      closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;
    }
    throw error;
  }
}
const ACCOUNT_KINDS={bank:'Bankkonto',cash:'Barkasse',payment_service:'Zahlungsdienst'};
const ACCOUNTING_BLOCKS={external_cash_evidence:'Gebundener Zahlungsnachweis im EÜR-Journal · keine Lieferantenverbindlichkeit',paid:'Vollständig ausgezahlt',review_changed:'Prüfung nach Auszahlung geändert – Klärung erforderlich',duplicate_original:'Original bereits anderweitig gebunden – Klärung erforderlich'};
export function accountingReceiptSummary(source) {
  const original=`${formatDate(source.issue_date)} · Brutto ${formatMoney(source.gross)}`;
  return source.source_role==='payment_evidence'
    ? original+' · Gebundener Zahlungsnachweis im EÜR-Journal; keine Lieferantenverbindlichkeit'
    : original+` · Ausgezahlt ${formatMoney(source.paid_amount)} · Verbleibend ${formatMoney(source.remaining_amount)}`;
}
const ACCOUNTING_REASONS={tax_profile_unconfigured:'Steuerprofil nicht eingerichtet',refund_origin_unresolved:'Ursprünglicher Erstattungsbezug ungeklärt'};
function accountingPaging(key,page) {
  const offset=state.accounting[key],controls=[];
  if(offset>0)controls.push(button('Vorherige Seite',()=>{state.accounting[key]=Math.max(0,offset-25);refresh();},'small'));
  if(page.next_offset!==null)controls.push(button('Weitere Einträge',()=>{state.accounting[key]=page.next_offset;refresh();},'small'));
  return el('div',{class:'actions'},el('span',{class:'caption'},`${page.items.length?offset+1:0}–${page.items.length?offset+page.items.length:0} von ${page.total} freigegebenen Einträgen`),controls);
}
function accountingDirection(item) { return item.direction==='out'?(item.kind==='refund'?'Erstattung / Abfluss':'Abfluss'):'Zufluss'; }
async function accountingContent() {
  const euerAvailable=state.features.has('accounting_euer')&&state.capabilities.has('business_accounting_euer');
  if(euerAvailable&&state.accounting.tab==='euer')return accountingEuer.render();
  const content=el('div',{class:'stack accounting'},heading('EÜR-Vorbereitung','Belegte Geldflüsse vorbereiten. Keine vollständige EÜR und keine Steuerberechnung.'),
    notice('Nur freigegebene Quellen. Der Projektfilter wird hier nicht angewendet. Diese Ansicht belegt keine vollständige Unternehmenssicht.'));
  const initial=accountingRights();
  if(!initial.available){content.append(notice('Dieser Server bietet das EÜR-Vorjournal noch nicht an. Vorhandene Zahlungen bleiben im Bereich „Zahlungen & offene Posten“ verfügbar.'));return content;}
  if(!initial.read){content.append(notice('Für die EÜR-Vorbereitung sind die globalen Rechte accounting.read und finance.read erforderlich. Projektbezogene Freigaben reichen nicht aus.'));return content;}
  const [rawStatus,accountResponse]=await Promise.all([api.get(biz('/accounting/status')),api.get(biz('/accounting/accounts'))]);
  const status=accountingStatus(rawStatus),rights=accountingRights(status);
  if(!Array.isArray(accountResponse?.items))throw new ApiError('Geldkonten konnten nicht sicher geladen werden.',502);
  const accounts=accountResponse.items;
  content.append(notice(euerAvailable?'Das Vorjournal enthält unveränderte Geldflussnachweise und berechnet keine steuerlichen Summen. Die ausdrückliche fachliche Einordnung und Jahresauswertung stehen unter „Eigene EÜR“.':accountingProfileRights().available?'Steuerprofil: nicht eingerichtet. Ein separat gespeichertes Vorbereitungsprofil dokumentiert nur Angaben. Alle Geldflüsse bleiben steuerlich ungeklärt; es werden keine steuerlichen Summen oder Gewinne berechnet.':'Profil und Steuerstatus: nicht eingerichtet. Alle Geldflüsse bleiben steuerlich ungeklärt. Es werden keine steuerlichen Summen oder Gewinne berechnet.'));
  if(openItemWorkspace.available())content.append(el('div',{class:'actions'},button('Offene Altposten',()=>action(()=>openItemWorkspace.open()),'small')));
  if(yearValuesWorkspace.available())content.append(el('div',{class:'actions'},button('Belegte frühere Jahreswerte',()=>action(()=>yearValuesWorkspace.open()),'small')));
  if(historicalWorkspace.available())content.append(el('div',{class:'actions'},button('Historische Anlagen',()=>action(()=>historicalWorkspace.open()),'small')));
  if(openingWorkspace.available())content.append(el('div',{class:'actions'},button('Anfangsbestände und Liquidität',()=>action(()=>openingWorkspace.open()),'small')));
  if(accountingProfileRights().read)content.append(el('div',{class:'actions'},button('Vorbereitungsprofil',()=>accountingAction(()=>accountingProfileDialog()),'small')));
  if(!status.writes_allowed)content.append(notice('Neue Vorgänge sind im aktuellen Betriebszustand gesperrt. Bestehende Nachweise bleiben lesbar; Betriebsmodus, Finanzmodul und gegebenenfalls Wiederherstellungsabgleich prüfen.','warn'));
  content.append(el('div',{class:'tabs',role:'group','aria-label':'Vorjournalbereiche'},[['events','Vorjournal'],['payments','Kundenzahlungen'],['receipts','Auszahlungen'],['accounts','Geldkonten'],...(euerAvailable?[['euer','Eigene EÜR']]:[])].map(([key,label])=>accountingTab(label,state.accounting.tab===key,()=>{state.accounting.tab=key;refresh();}))));
  const tab=state.accounting.tab,offset=state.accounting[tab];
  if(tab==='accounts') {
    const items=accounts.slice(offset,offset+25),page={items,total:accounts.length,next_offset:offset+25<accounts.length?offset+25:null};
    content.append(panel('Geldkonten',el('p',{class:'muted'},'EUR-Konten dienen der Zuordnung belegter Geldflüsse. Hier wird keine Bankverbindung eingerichtet.'),rights.admin?button('Geldkonto anlegen',()=>accountingAccountDialog(null),'primary'):null,
      rows(items,account=>row(`${account.code} · ${account.name}`,`${ACCOUNT_KINDS[account.kind]||account.kind} · EUR · Version ${account.revision}`,[badge(account.active?'Aktiv':'Inaktiv'),openingWorkspace.available()?button('Anfangsbestand prüfen',()=>action(()=>openingWorkspace.account(account.id)),'small'):null,rights.admin?button('Konto bearbeiten',()=>accountingAccountDialog(account),'small'):null])),accountingPaging(tab,page)));return content;
  }
  const path=tab==='events'?'/accounting/events':`/accounting/sources/${tab}`;
  const page=accountingPage(await api.get(query(biz(path),{limit:25,offset})),offset,tab==='events');
  if(tab==='events')content.append(panel('Vorjournal',rows(page.items,event=>row(`Nr. ${event.sequence} · ${accountingDirection(event)} · ${formatMoney(event.amount)}`,
    `${formatDate(event.cash_date)} · ${event.account.code} / ${event.account.name} (Version ${event.account.revision}) · ${event.evidence_reference}`,
    [badge('Steuerlich ungeklärt'),button('Nachweis ansehen',()=>accountingAction(()=>accountingEventDialog(event.id)),'small')]),'Noch keine Geldflüsse verknüpft oder bestätigt.'),accountingPaging(tab,page)));
  if(tab==='payments')content.append(panel('Vorhandene Kundenzahlungen',el('p',{class:'muted'},'Bestehende bestätigte Zahlungseingänge und Erstattungen übernehmen. Betrag und Richtung stammen unverändert aus der Quelle; es wird keine neue Kundenzahlung angelegt.'),
    !accountingAllocationRights().available?notice('Dieser Server bietet die nachträgliche Rechnungszuordnung noch nicht an. Vorhandene Zahlungsnachweise bleiben lesbar.'):null,
    rows(page.items,source=>row(`${accountingDirection(source)} · ${formatMoney(source.amount)}`,`${formatDate(source.booking_date)} · ${source.reference||source.source_id} · Ursprünglich nicht zugeordnet ${formatMoney(source.unallocated)}`,
      [source.linked_event_id?button('Verknüpften Geldfluss ansehen',()=>accountingAction(()=>accountingEventDialog(source.linked_event_id)),'small'):rights.prepare?button('Bestehende Zahlung verknüpfen',()=>accountingCashDialog('payment',source,accounts),'primary'):badge('Noch nicht verknüpft'),source.linked_event_id&&source.kind==='receipt'&&accountingAllocationRights().read?button(accountingAllocationRights().prepare?'Rechnung zuordnen':'Zuordnungen ansehen',()=>accountingAction(()=>accountingAllocationDialog(source.payment_id)),'small'):null],`${source.allocations.length} ursprüngliche Rechnungszuordnung${source.allocations.length===1?'':'en'}. Der ursprüngliche Zahlungsnachweis bleibt unverändert; zusätzliche Zuordnungen werden getrennt angezeigt.`),'Keine freigegebenen bestätigten Kundenzahlungen vorhanden.'),accountingPaging(tab,page)));
  if(tab==='receipts')content.append(panel('Auszahlungen auf geprüfte Eingangsbelege',el('p',{class:'muted'},'Bereits tatsächlich geleistete Teil- oder Restzahlungen mit Beleg und Konto bestätigen. Diese Aktion löst keine Überweisung aus.'),
    rows(page.items,source=>row(`${source.vendor} · ${source.invoice_number}`,accountingReceiptSummary(source),
      [button('Original ansehen',()=>accountingAction(()=>download(biz(`/finance/receipts/${source.receipt_id}/original`),source.filename)),'small'),rights.prepare&&source.payable?button('Auszahlung bestätigen',()=>accountingCashDialog('receipt',source,accounts),'primary'):null,badge(ACCOUNTING_BLOCKS[source.blocked_reason]||(source.payable?'Zur Bestätigung verfügbar':'Gesperrt'))],`Prüfversion ${source.review_revision} · Auszahlungsstand ${source.cash_revision}`),'Keine freigegebenen geprüften EUR-Eingangsbelege vorhanden.'),accountingPaging(tab,page)));
  return content;
}
const PROFILE_NOTICE='Dieses Vorbereitungsprofil dokumentiert Ihre ausdrücklich bestätigten Angaben. Es richtet keine Steuerregeln ein, ordnet keine Geldflüsse ein und berechnet keine EÜR oder Steuern. Unbekannte Angaben dürfen offen bleiben.';
const PROFILE_PENDING_KEY='accounting-profile-confirm';
function accountingProfileRights(source=null) { return accountingProfileAccess({permissions:[...state.globalPermissions],features:[...state.features],capabilities:[...state.capabilities],readonly:state.readonly},state.organization,source,navigator.onLine); }
function accountingProfileContext() { const generation=api.generation,render=state.render,previous=modal;return ()=>generation===api.generation&&render===state.render&&previous===modal; }
function accountingProfileFacts(profile) {
  accountingPreparationProfile(profile);
  return el('div',{class:'stack break-word'},el('p',{},'Unternehmensform: Einzelunternehmen'),el('p',{},'Buchführungsform: Einnahmenüberschussrechnung (EÜR)'),
    el('p',{},`Umsatzsteuerregelung: ${{small_business:'Kleinunternehmerregelung laut Angabe',regular:'Regelbesteuerung laut Angabe'}[profile.vat_regime]||'Noch ungeklärt'}`),
    el('p',{},`Besteuerungszeitpunkt: ${{accrual:'Sollbesteuerung laut Angabe',cash:'Istbesteuerung laut Angabe'}[profile.vat_timing]||'Noch ungeklärt'}`),
    el('p',{},`Umsatzsteuer gilt laut Angabe ab: ${profile.vat_effective_from?formatDate(profile.vat_effective_from):'Noch ungeklärt'}`),
    el('p',{},`Buchführung beginnt laut Angabe am: ${profile.bookkeeping_start?formatDate(profile.bookkeeping_start):'Noch ungeklärt'}`));
}
function accountingProfileRecord(entry) {
  accountingProfileEntry(entry);
  return panel('Gespeicherte Profilversion '+entry.revision,accountingProfileFacts(entry.profile),el('p',{class:'break-word'},`Begründung: ${entry.reason}`),el('p',{class:'break-word'},`Nachweisreferenz: ${entry.evidence_reference}`),el('p',{class:'caption'},`Ausdrücklich gespeichert am ${formatDate(entry.created_at,true)}. Diese Version bleibt unverändert.`));
}
async function accountingProfileDialog({offset=0,entryId=null}={}) {
  const current=accountingProfileContext(),source=await accountingProfileAuthorize(api),history=accountingProfilePage(await api.get(query(biz('/accounting/profile/history'),{limit:25,offset})),offset);
  if(!current())return;if(history.total!==source.revision)throw new ApiError('Der Profilstand wurde zwischenzeitlich erweitert. Bitte erneut laden.',409);
  const content=el('div',{class:'stack accounting break-word','data-accounting-detail':'true','data-profile-detail':'true'},notice(PROFILE_NOTICE));
  if(entryId) {
    const entry=history.items.find(item=>item.id===entryId);if(!entry)throw new ApiError('Die gesuchte Profilversion ist auf dieser Seite nicht mehr enthalten. Bitte den Verlauf neu laden.',409);
    content.append(accountingProfileRecord(entry),button('Zurück zum Profilverlauf',()=>accountingAction(()=>accountingProfileDialog({offset})),'small'));
  } else {
    const pending=api.pendingOperations().some(item=>item.path===biz('/accounting/profile/confirm'));
    content.append(source.current?accountingProfileRecord(source.current):notice('Noch keine Profilversion gespeichert. Das Öffnen dieser Ansicht legt keine Angaben an.'),
      !source.writes_allowed?notice('Neue Profilversionen sind derzeit gesperrt. Bereits gespeicherte Angaben bleiben entsprechend Ihren Leserechten verfügbar.','warn'):null,
      pending?notice('Eine Antwort zur Profilbestätigung ist offen. Unter „Antworten offen“ zuerst die unveränderte Anfrage wiederholen.','warn'):null,
      accountingProfileRights(source).admin&&!pending?button('Neue Profilversion vorbereiten',()=>accountingAction(()=>accountingProfileInput()),'primary'):null,
      panel('Profilverlauf',rows(history.items,entry=>row('Version '+entry.revision,`${formatDate(entry.created_at,true)} · ${entry.reason}`,[button('Profilversion ansehen',()=>accountingAction(()=>accountingProfileDialog({offset,entryId:entry.id})),'small')],entry.evidence_reference),'Noch keine ausdrücklich bestätigte Profilversion.'),allocationPagination(history,offset,next=>accountingProfileDialog({offset:next}))));
  }
  dialog(entryId?'Gespeicherte Profilversion':'Vorbereitungsprofil',content);
}
async function accountingProfileInput() {
  const current=accountingProfileContext(),source=await accountingProfileAuthorize(api,{write:true,online:navigator.onLine});if(!current())return;
  if(api.pendingOperations().some(item=>item.path===biz('/accounting/profile/confirm')))throw new ApiError('Zuerst die offene Profilantwort unverändert wiederholen.',409);
  const generation=api.generation,render=state.render,profile=source.current?.profile||{legal_form:'sole_proprietorship',accounting_method:'euer',vat_regime:null,vat_timing:null,vat_effective_from:null,bookkeeping_start:null};
  const fields=[field('legal_form','Unternehmensform','select',profile.legal_form,{required:true,options:[['sole_proprietorship','Einzelunternehmen']]}),field('accounting_method','Buchführungsform','select',profile.accounting_method,{required:true,options:[['euer','Einnahmenüberschussrechnung (EÜR)']]}),
    field('vat_regime','Umsatzsteuerregelung','select',profile.vat_regime||'',{keepEmpty:true,options:[['','Noch ungeklärt'],['small_business','Kleinunternehmerregelung laut Angabe'],['regular','Regelbesteuerung laut Angabe']]}),
    field('vat_timing','Besteuerungszeitpunkt','select',profile.vat_timing||'',{keepEmpty:true,options:[['','Noch ungeklärt'],['accrual','Sollbesteuerung laut Angabe'],['cash','Istbesteuerung laut Angabe']],help:'Soll oder Ist nur bei erklärter Regelbesteuerung wählen. Eine Auswahl aktiviert keine Steuerberechnung.'}),
    field('vat_effective_from','Umsatzsteuer gilt laut Angabe ab','date',profile.vat_effective_from||'',{min:'1900-01-01',max:'2200-12-31',help:'Leer lassen, solange der Beginn unbekannt ist. Ein Datum benötigt eine angegebene Umsatzsteuerregelung.'}),
    field('bookkeeping_start','Buchführung beginnt laut Angabe am','date',profile.bookkeeping_start||'',{min:'1900-01-01',max:'2200-12-31',help:'Leer lassen, solange der Beginn unbekannt ist. Es wird kein Beginn aus vorhandenen Zahlungen abgeleitet.'}),
    field('reason','Begründung','text','',{required:true,maxLength:1000,wide:true}),field('evidence_reference','Nachweisreferenz','text','',{required:true,maxLength:200,wide:true,help:'Zum Beispiel eine ausdrücklich bestätigte Inhaberangabe oder ein eigener Nachweis. Die Referenz behauptet keinen geprüften Behördenbeleg.'})];
  const editor=form('',fields,async values=>{
    const body=accountingProfilePreviewData(source,values);
    try {
      await accountingProfileAuthorize(api,{write:true,online:navigator.onLine});if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;
      const preview=accountingProfilePreview(await api.post(biz('/accounting/profile/preview'),body),body);if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;
      await accountingProfileAuthorize(api,{write:true,online:navigator.onLine});if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;
      accountingProfileConfirm(source,body,preview);return undefined;
    }catch(error){if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;if([403,404,423].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}throw error;}
  },{key:'accounting-profile-preview',submit:'Profilangaben unverbindlich prüfen',description:source.current?`Neue Version auf Grundlage der gespeicherten Version ${source.revision}. Grund und Nachweis für diese neue Bestätigung ausdrücklich angeben.`:'Einzelunternehmen und EÜR sind ungespeicherte Vorschläge. Umsatzsteuer und beide Beginnangaben sind unbekannt. Erst die gesonderte Bestätigung speichert Ihre Angaben.',extra:notice(PROFILE_NOTICE)});
  editor.dataset.accountingDetail='true';editor.dataset.profileDetail='true';dialog('Profilangaben vorbereiten',editor);
}
function accountingProfileConfirm(source,body,preview) {
  const generation=api.generation,render=state.render,editor=form('',[field('confirmation','Ich bestätige diese Profilangaben einschließlich der ausdrücklich offenen Angaben.','checkbox',false,{required:true})],async values=>{
    const data=accountingProfileConfirmData(body,preview,values.confirmation);
    try{await accountingProfileAuthorize(api,{write:true,online:navigator.onLine});}catch(error){if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;if([403,404,423].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}throw error;}
    if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;
    const result=await accountingSave(editor,generation,PROFILE_PENDING_KEY,'/accounting/profile/confirm',data);return render===state.render?result:undefined;
  },{key:PROFILE_PENDING_KEY,submit:'Profilversion verbindlich speichern',description:`Geplante Profilversion ${source.revision+1}. Erst diese Bestätigung speichert die gezeigten Angaben. Eine Vorschau allein erzeugt keine Version.`,
    extra:el('div',{class:'stack break-word'},accountingProfileFacts(preview.profile),el('p',{},`Begründung: ${preview.reason}`),el('p',{},`Nachweisreferenz: ${preview.evidence_reference}`),notice(PROFILE_NOTICE)),
    after:async()=>{const render=state.render+1,section=state.section;await refresh();if(generation===api.generation&&state.render===render&&state.section===section&&!modal)await accountingProfileDialog();}});
  editor.dataset.accountingDetail='true';editor.dataset.profileDetail='true';dialog('Profilangaben prüfen',editor);
}
function accountingAccountDialog(account) {
  const generation=api.generation;
  const fields=account?[field('name','Kontoname','text',account.name,{required:true,maxLength:200}),field('active','Konto für neue Geldflüsse aktiv','checkbox',account.active)]:[
    field('code','Stabiler Kontocode','text','',{required:true,maxLength:40,help:'Buchstaben, Ziffern, Bindestrich oder Unterstrich. Später unveränderlich.'}),field('name','Kontoname','text','',{required:true,maxLength:200}),field('kind','Kontoart','select','bank',{options:Object.entries(ACCOUNT_KINDS),required:true})];
  fields.push(field('confirmation','Ich bestätige diese Kontofassung.','checkbox',false,{required:true}));
  const editor=form('',fields,async(values,key)=>{
    return accountingSave(editor,generation,key,account?`/accounting/accounts/${account.id}`:'/accounting/accounts',accountingAccountData(account,values));
  },{key:account?'accounting-account-'+account.id:'accounting-account-new',submit:account?'Kontofassung speichern':'Geldkonto anlegen',description:account?`${account.code} · ${ACCOUNT_KINDS[account.kind]} · EUR · Version ${account.revision}. Änderungen gelten für neue Vorgänge. Historische Geldflüsse behalten ihre bestätigte Kontofassung.`:'Keine Bankanbindung. Das Konto wird aktiv mit Währung EUR angelegt.'});
  editor.dataset.accountingDetail='true';
  dialog(account?'Geldkonto bearbeiten':'Geldkonto anlegen',editor);
}
function accountingSourceDetails(kind,source) {
  const content=el('div',{class:'stack break-word'},el('p',{},kind==='payment'?`${accountingDirection(source)} · ${formatMoney(source.amount)} · Ursprüngliches Buchungsdatum ${formatDate(source.booking_date)} · ${source.reference||source.source_id}`:
    `${source.vendor} · ${source.invoice_number} · Brutto ${formatMoney(source.gross)} · Prüfversion ${source.review_revision}`));
  if(kind==='receipt')content.append(button('Original ansehen',()=>accountingAction(()=>download(biz(`/finance/receipts/${source.receipt_id}/original`),source.filename)),'small'),el('p',{class:'caption'},`Original SHA-256: ${source.original_sha256} · Prüfung SHA-256: ${source.review_sha256}`));
  else content.append(rows(source.allocations,allocation=>row(allocation.number,`Zugeordnet ${formatMoney(allocation.amount)}`,[button('Rechnungs-PDF ansehen',()=>accountingAction(()=>download(biz(`/documents/${allocation.document_id}/pdf`),`${allocation.number}.pdf`)),'small')]),'Keine Rechnungszuordnung vorhanden.'),el('p',{},`Ursprünglich nicht zugeordnet: ${formatMoney(source.unallocated)}`));
  return content;
}
function accountingCashDialog(kind,source,accounts) {
  const active=accounts.filter(account=>account.active&&account.currency==='EUR'),generation=api.generation;
  if(!active.length){dialog('Aktives Geldkonto erforderlich',notice('Zuerst unter „Geldkonten“ ein aktives EUR-Konto durch eine Person mit accounting.admin einrichten lassen.'));return;}
  const fields=[field('account_id','Geldkonto','select','',{options:[['','Bitte ausdrücklich auswählen'],...active.map(account=>[account.id,`${account.code} · ${account.name} · Version ${account.revision}`])],required:true}),
    field('cash_date','Tatsächlicher Geldflusstag','date','',{required:true}),field('evidence_reference','Geldfluss-Nachweisreferenz','text','',{required:true,maxLength:200,help:'Stabile Referenz dieses tatsächlichen Geldflusses auf dem gewählten Konto. Je Konto nur einmal verwendbar.'})];
  if(kind==='receipt')fields.push(field('amount','Tatsächlich ausgezahlter Betrag EUR','decimal','',{required:true,help:`Verbleibend ${formatMoney(source.remaining_amount)}. Höchstens zwei Nachkommastellen; keine Rundung.`}),field('reference','Verwendungszweck','text','',{maxLength:1000}));
  fields.push(field('confirmation',kind==='payment'?'Ich habe Quelle, Konto, Geldflusstag und Nachweis geprüft.':'Ich bestätige den tatsächlich geleisteten Geldabfluss mit diesem Beleg und Konto.','checkbox',false,{required:true}));
  const editor=form('',fields,async(values,key)=>{
    const account=active.find(item=>item.id===values.account_id),data=kind==='payment'?accountingPaymentData(source,account,values):accountingPayoutData(source,account,values);
    return accountingSave(editor,generation,key,kind==='payment'?'/accounting/events/import-payment':'/accounting/events/payout',data);
  },{key:`accounting-${kind}-${kind==='payment'?source.payment_id:source.receipt_id}`,submit:kind==='payment'?'Geprüfte Zahlung verknüpfen':'Tatsächliche Auszahlung bestätigen',
    description:'Nur bestätigte Geldflüsse erfassen. Eine verlorene Antwort unter „Antworten offen“ unverändert wiederholen. Diese Wiederholung bewahrt die ursprüngliche Kontofassung und Prüfversion. Ein neuer Vorgang benötigt die aktuellen Fassungen.',
    extra:accountingSourceDetails(kind,source)});
  editor.dataset.accountingDetail='true';
  dialog(kind==='payment'?'Bestehende Zahlung verknüpfen':'Auszahlung bestätigen',editor);
}
async function accountingEventDialog(id) {
  const generation=api.generation,render=state.render,previous=modal,event=await api.get(biz(`/accounting/events/${id}`));
  if(generation!==api.generation||render!==state.render||previous!==modal)return;
  if(event.classification_status!=='unclassified'||!Array.isArray(event.unresolved_reasons))throw new ApiError('Geldflussnachweis konnte nicht sicher geladen werden.',502);
  dialog(`Geldfluss Nr. ${event.sequence}`,el('div',{class:'stack','data-accounting-detail':'true'},notice('Steuerlich ungeklärt. Dieser Nachweis ist kein Steuerergebnis.'),
    el('p',{},`${accountingDirection(event)} · ${formatMoney(event.amount)} · ${formatDate(event.cash_date)}`),el('p',{},`Konto: ${event.account.code} / ${event.account.name} · Version ${event.account.revision}`),
    el('p',{},`Nachweisreferenz: ${event.evidence_reference}`),event.reference?el('p',{},`Verwendungszweck: ${event.reference}`):null,
    el('p',{},event.unresolved_reasons.map(reason=>ACCOUNTING_REASONS[reason]||reason).join(' · ')),
    event.source.kind==='payment'?notice('Ursprünglicher Zahlungsnachweis: Die damalige Zahlung und ihre Rechnungszuordnungen bleiben unverändert. Spätere Zuordnungen sind getrennt dokumentiert.'):null,
    event.source.kind==='payment'&&accountingAllocationRights().read?button('Wirksame Zuordnungen ansehen',()=>accountingAction(()=>accountingAllocationDialog(event.source.id)),'small'):null,
    componentRights().read?button(componentRights().prepare&&event.source.snapshot.kind!=='refund'?'Beleganteile aufteilen':'Aufteilungen ansehen',()=>accountingAction(()=>componentDialog(event.id)),'small'):null,
    event.source.snapshot.kind==='refund'&&refundRights().read?button(refundRights().prepare?'Erstattungsursprung zuordnen':'Ursprungsbindungen ansehen',()=>accountingAction(()=>refundDialog(event.id)),'small'):null,
    panel('Bestätigte Quellfassung',accountingSourceDetails(event.source.kind,event.source.snapshot),el('p',{class:'caption'},`Quelle SHA-256: ${event.source.source_hash}`)),
    el('p',{class:'caption'},`Erfasst ${formatDate(event.created_at,true)}. Spätere Konto- oder Prüfänderungen ändern diesen Nachweis nicht.`)));
}

const ALLOCATION_BLOCKS={unsupported_payment:'Nur übernommene Zahlungseingänge können zugeordnet werden.',unsupported_source_documents:'Die ursprünglichen Rechnungsarten unterstützen keine zusätzliche Zuordnung.',missing_customer:'Der ursprünglichen Rechnung fehlt eine eindeutige Kundenbindung.',mixed_customers:'Die Quelle enthält unterschiedliche Kunden und benötigt Klärung.',fully_allocated:'Die Zahlung ist vollständig zugeordnet.',overallocated:'Die historischen Zuordnungen überschreiten die Zahlung und benötigen Klärung.'};
function accountingAllocationRights(source=null) {
  return accountingAllocationAccess({permissions:[...state.globalPermissions],features:[...state.features],capabilities:[...state.capabilities],readonly:state.readonly},state.organization,source,navigator.onLine);
}
function accountingAllocationWritable(source) {
  if(!accountingAllocationRights(source).prepare)throw new ApiError('Eine neue Zuordnung benötigt Internet, aktuelle globale Accounting-/Finanzschreibrechte und einen freigegebenen Finanzbetrieb.',423);
}
function allocationPath(id,suffix='') { return `/accounting/allocations/payments/${accountingId(id)}${suffix}`; }
function allocationPagination(page,offset,load) {
  return el('div',{class:'actions'},el('span',{class:'caption'},`${page.items.length?offset+1:0}–${page.items.length?offset+page.items.length:0} von ${page.total} freigegebenen Einträgen`),
    offset>0?button('Vorherige Seite',()=>accountingAction(()=>load(Math.max(0,offset-25))),'small'):null,
    page.next_offset!==null?button('Weitere Einträge',()=>accountingAction(()=>load(page.next_offset)),'small'):null);
}
async function accountingAllocationDialog(id,{offset=0,document=null}={}) {
  const generation=api.generation,render=state.render,previous=modal;
  if(!accountingAllocationRights().read)throw new ApiError('Dieser Server oder Ihre aktuellen globalen Rechte erlauben keine Zahlungszuordnung.',403);
  const [rawState,rawHistory,open]=await Promise.all([api.get(biz(allocationPath(id))),api.get(query(biz(allocationPath(id,'/history')),{limit:25,offset})),document?api.get(query(biz('/finance/open-items'),{project_id:document.project_id})):Promise.resolve(null)]);
  if(generation!==api.generation||render!==state.render||previous!==modal)return;
  const source=accountingAllocationState(rawState),history=accountingPage(rawHistory,offset),rights=accountingAllocationRights(source),pending=api.pendingOperations().some(item=>item.path===biz(allocationPath(id,'/assign')));
  const content=el('div',{class:'stack accounting break-word','data-accounting-detail':'true'},notice('Aktueller Zuordnungsstand. Der ursprüngliche Zahlungsnachweis bleibt unverändert. Zusätzliche Zuordnungen erzeugen keine neue Zahlung und kein Steuerergebnis.'),
    panel('Wirksamer Stand',el('p',{},`Zahlung ${formatMoney(source.amount)} · Zugeordnet ${formatMoney(source.allocated_amount)} · Frei ${formatMoney(source.unallocated_amount)}`),
      el('p',{},`Zusatzzuordnungen: ${source.revision} · ${source.customer_id?'Kundenbindung bestätigt':'Noch keine Kundenbindung. Den Kunden der Zielrechnung ausdrücklich bestätigen.'}`),
      source.eligible?null:notice(ALLOCATION_BLOCKS[source.blocked_reason]||'Neue Zuordnungen sind für diese Quelle gesperrt.','warn'),
      !source.writes_allowed?notice('Neue Zuordnungen sind durch aktuelle Rechte oder den Betriebszustand gesperrt. Die freigegebene Historie bleibt lesbar.','warn'):null,
      pending?notice('Für diese Zahlung ist eine Zuordnungsantwort offen. Unter „Antworten offen“ exakt die ursprüngliche Anfrage wiederholen, bevor ein neuer Vorgang beginnt.','warn'):null,
      rights.prepare&&!pending?button('Rechnung auswählen',()=>accountingAction(()=>accountingAllocationCandidates(source)),'primary'):null,
      button('Ursprünglichen Zahlungsnachweis ansehen',()=>accountingAction(()=>accountingEventDialog(source.event_id)),'small')),
    panel('Bestätigte Zusatzzuordnungen',rows(history.items,entry=>row(`${entry.document.number} · ${formatMoney(entry.amount)}`,`${entry.document.buyer_name} · ${formatDate(entry.created_at,true)} · ${entry.reason}`,
      [button('Rechnungs-PDF ansehen',()=>accountingAction(()=>download(biz(`/documents/${entry.document.document_id}/pdf`),`${entry.document.number}.pdf`)),'small')],`Bestätigter damaliger Stand: frei ${formatMoney(entry.unallocated_after)} · Rechnung offen ${formatMoney(entry.open_after)} · Version ${entry.revision}`),'Noch keine Zusatzzuordnung bestätigt.'),allocationPagination(history,offset,next=>accountingAllocationDialog(id,{offset:next,document}))));
  if(document) {
    if(!Array.isArray(open?.items))throw new ApiError('Der aktuelle Rechnungsstand konnte nicht geladen werden.',502);
    const current=open.items.find(item=>item.id===document.document_id||item.document_id===document.document_id);
    content.insertBefore(panel('Aktueller Rechnungsstand',current?el('p',{},`${current.number} · Bezahlt ${formatMoney(current.paid)} · Offen ${formatMoney(current.open)}`):notice('Die Rechnung ist im aktuellen offenen-Posten-Stand nicht mehr enthalten. Bitte den Beleg prüfen.')),content.children[2]);
  }
  dialog('Zahlung zuordnen',content);
}
async function accountingAllocationCandidates(source,offset=0) {
  accountingAllocationWritable(source);
  const generation=api.generation,render=state.render,previous=modal,page=accountingPage(await api.get(query(biz(allocationPath(source.payment_id,'/candidates')),{limit:25,offset})),offset);
  if(generation!==api.generation||render!==state.render||previous!==modal)return;
  dialog('Zielrechnung auswählen',el('div',{class:'stack accounting break-word','data-accounting-detail':'true'},notice(`Freier Zahlungsbetrag ${formatMoney(source.unallocated_amount)}. Nur passende finale Rechnungen mit aktuellen Schreibrechten werden angeboten. Den Rechnungskunden im nächsten Schritt ausdrücklich prüfen.`),
    rows(page.items,document=>row(document.number,`${document.buyer_name} · Offen ${formatMoney(document.open)} · Brutto ${formatMoney(document.gross)}`,
      [button('Diese Rechnung wählen',()=>accountingAllocationInput(source,document),'primary'),button('Rechnungs-PDF ansehen',()=>accountingAction(()=>download(biz(`/documents/${document.document_id}/pdf`),`${document.number}.pdf`)),'small')],'Kundenbindung aus der gewählten Rechnung'),'Keine berechtigte passende Rechnung mit positivem offenem Betrag vorhanden.'),
    allocationPagination(page,offset,next=>accountingAllocationCandidates(source,next)),button('Zurück zum wirksamen Stand',()=>accountingAction(()=>accountingAllocationDialog(source.payment_id)),'small')));
}
function accountingAllocationInput(source,document) {
  const generation=api.generation;
  const editor=form('',[field('amount','Zuordnungsbetrag EUR','decimal','',{required:true,help:`Zahlung frei ${formatMoney(source.unallocated_amount)} · Rechnung offen ${formatMoney(document.open)}. Keine Rundung.`}),
    field('reason','Begründung der Zuordnung','text','',{required:true,maxLength:1000}),
    field('customer_confirmation',`Ich bestätige ${document.buyer_name} als Kunden dieser Rechnung und dieser Zahlung.`,'checkbox',false,{required:true})],async values=>{
      accountingAllocationWritable(source);
      const body=accountingAllocationPreviewData(source,document,values);
      try {
        // Preview is a side-effect-free POST: no request ID and no pending command.
        const result=await api.post(biz(allocationPath(source.payment_id,'/preview')),body);
        if(generation!==api.generation||!editor.isConnected)return undefined;
        const preview=accountingAllocationPreview(result,body,source.payment_id,source.event_id);
        accountingAllocationConfirm(source,body,preview);return undefined;
      } catch(error) {
        if(generation!==api.generation||!editor.isConnected)return undefined;
        if([403,404].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}
        throw error;
      }
    },{key:'accounting-allocation-preview-'+source.payment_id,submit:'Unverbindliche Vorschau prüfen',description:`Rechnung ${document.number} · ${document.buyer_name}. Die Vorschau speichert keine Zuordnung. Der Kunde stammt aus der gewählten Rechnung; ein Verwendungszweck ersetzt keine Kundenbindung.`,
      extra:button('Aktuellen Stand neu laden',()=>accountingAction(()=>accountingAllocationDialog(source.payment_id)),'small')});
  editor.dataset.accountingDetail='true';dialog('Zuordnung vorbereiten',editor);
}
function accountingAllocationConfirm(source,body,preview) {
  const generation=api.generation;
  const editor=form('',[field('confirmation','Ich bestätige diese Zuordnung zur angezeigten Rechnung und zum bestätigten Kunden.','checkbox',false,{required:true})],async(values,key)=>{
      accountingAllocationWritable(source);
      return accountingSave(editor,generation,key,allocationPath(source.payment_id,'/assign'),accountingAllocationAssignData(body,preview,values.confirmation));
    },{key:'accounting-allocation-'+source.payment_id,submit:'Zuordnung verbindlich bestätigen',description:'Diese Bestätigung ordnet eine bereits vorhandene Zahlung zu. Bei verloren gegangener Antwort exakt dieselbe Vorschau wiederholen. Veränderte offene Posten erfordern für einen neuen Vorgang eine neue Vorschau.',
      extra:el('div',{class:'stack break-word'},panel('Geprüfte Vorschau',el('p',{},`${preview.document.number} · ${preview.document.buyer_name}`),el('p',{},`Bestätigter Kunde: ${preview.document.buyer_name}`),el('p',{},`Zuordnung ${formatMoney(preview.amount)} · ${preview.reason}`),
        el('p',{},`Zahlung frei: ${formatMoney(preview.unallocated_before)} → ${formatMoney(preview.unallocated_after)}`),el('p',{},`Rechnung offen: ${formatMoney(preview.open_before)} → ${formatMoney(preview.open_after)}`)),
        button('Aktuellen Stand neu laden',()=>accountingAction(()=>accountingAllocationDialog(source.payment_id)),'small')),
      after:async result=>{const render=state.render+1,section=state.section;await refresh();if(generation===api.generation&&state.render===render&&state.section===section&&!modal)await accountingAllocationDialog(source.payment_id,{document:result.document});}});
  editor.dataset.accountingDetail='true';dialog('Zuordnung prüfen',editor);
}

const COMPONENT_BLOCKS={refund_origin_unresolved:'Der Ursprung dieser Erstattung ist noch ungeklärt. Ihre Aufteilung folgt in einem eigenen Schritt.',source_customer_unresolved:'Die Kundenbindung der Zahlungsquelle muss zuerst geklärt werden.',unsupported_document:'Dieser Beleg unterstützt derzeit keine dokumentarische Aufteilung.',review_changed:'Die Belegprüfung wurde nach der Auszahlung geändert. Neue Aufteilungen benötigen eine Klärung.',group_capacity_exceeded:'Der ganze Beleganteil passt nicht mehr in die verfügbaren Gruppenreste.',unallocated:'Der Zahlungsrest ist noch keiner Rechnung zugeordnet.',fully_documented:'Alle verfügbaren Beleganteile sind dokumentiert.'};
function componentRights(source=null) { return componentAccess({permissions:[...state.globalPermissions],features:[...state.features],capabilities:[...state.capabilities],readonly:state.readonly},state.organization,source,navigator.onLine); }
function componentWritable(source) { if(!componentRights(source).prepare)throw new ApiError('Eine neue Aufteilung benötigt Internet, aktuelle globale Accounting-/Finanzschreibrechte und einen freigegebenen Finanzbetrieb.',423); }
function componentPath(id,suffix='') { return `/accounting/components/events/${accountingId(id)}${suffix}`; }
export function componentGroupLabel(group) {
  if(group.rate===null)return 'Geprüfte Gesamtsummen';
  const category={S:'Standardbesteuerung laut Beleg',Z:'Nullsatz laut Beleg',E:'Steuerbefreiung laut Beleg',AE:'Steuerschuldnerschaft laut Beleg'}[group.category]||('Belegkategorie '+group.category);
  return `${String(group.rate).replace('.',',')} % · ${category}${group.reason?' · '+group.reason:''}`;
}
function componentTaxLabel(portion) { return portion.kind==='supplier_payout'?'Ausgewiesener Steueranteil laut Prüfung':'Ausgewiesener Steueranteil laut Rechnung'; }
function componentOriginal(event,portion) {
  return button(portion.kind==='supplier_payout'?'Belegoriginal ansehen':'Rechnungs-PDF ansehen',()=>accountingAction(()=>download(portion.kind==='supplier_payout'?biz(`/finance/receipts/${portion.receipt_id}/original`):biz(`/documents/${portion.document_id}/pdf`),portion.kind==='supplier_payout'?event.source.snapshot.filename||'Belegoriginal':`${portion.number}.pdf`)),'small');
}
function componentRecord(value,event) {
  componentLines(value);
  return el('div',{class:'stack accounting break-word'},panel(value.portion.number||'Geprüfter Beleg',el('p',{},value.portion.party_name),el('p',{},`Fester Beleganteil: ${formatMoney(value.amount)} · ${value.reason}`),componentOriginal(event,value.portion)),
    panel('Dokumentarische Beträge',el('p',{},`Belegter Nettoanteil: ${formatMoney(value.net)}`),el('p',{},`${componentTaxLabel(value.portion)}: ${formatMoney(value.tax)}`),el('p',{},`Bruttoanteil: ${formatMoney(value.amount)}`)),
    panel('Aufteilung nach Beleggruppen',rows(value.lines,line=>{
      const group=value.portion.groups.find(item=>item.group_id===line.group_id);
      return row(componentGroupLabel(group),`Netto ${formatMoney(line.net)} · Ausgewiesener Steueranteil ${formatMoney(line.tax)} · Brutto ${formatMoney(line.amount)}`,[],`Dokumentierter Gruppenbetrag: ${formatMoney(line.gross_before)} → ${formatMoney(line.gross_after)} · Verbleibend ${formatMoney(line.remaining_gross)}`);
    })),notice('Steuerliche Einordnung offen. Diese Beleganteile sind kein Steuerergebnis. Bereits bestätigte Teilbeträge bleiben unverändert; Rundungscent werden so berücksichtigt, dass die Summe zum Beleg passt.'));
}
async function componentDialog(eventId,{offset=0,entryId=null,legacy=false}={}) {
  const generation=api.generation,render=state.render,previous=modal;
  if(!componentRights().read)throw new ApiError('Dieser Server oder Ihre aktuellen globalen Rechte erlauben keine Belegaufteilung.',403);
  const [rawState,rawHistory,event]=await Promise.all([api.get(biz(componentPath(eventId))),api.get(query(biz(componentPath(eventId,'/history')),{limit:25,offset})),api.get(biz(`/accounting/events/${eventId}`))]);
  if(generation!==api.generation||render!==state.render||previous!==modal)return;
  const source=componentState(rawState),history=accountingPage(rawHistory,offset),rights=componentRights(source);
  if(source.event_id!==eventId||event.id!==eventId||history.items.some(item=>item.event_id!==eventId))throw new ApiError('Der Zahlungsnachweis passt nicht zum Aufteilungsstand.',502);
  if(!legacy&&source.source_kind==='customer_receipt'&&capacityRights().read)return capacityDialog(eventId,{legacyOffset:offset,legacyHistory:history,event});
  const content=el('div',{class:'stack accounting break-word','data-accounting-detail':'true'},notice('Dokumentarische Beleganteile. Der ursprüngliche Zahlungsnachweis bleibt unverändert; es entsteht keine neue Zahlung, Rechnungszuordnung oder Steuerbuchung.'));
  if(entryId) {
    const entry=history.items.find(item=>item.id===entryId);
    if(!entry)throw new ApiError('Die Historie wurde erweitert. Bitte den Eintrag in der aktuellen Liste erneut öffnen.',409);
    content.append(componentRecord(entry,event),el('p',{class:'caption'},`Bestätigt ${formatDate(entry.created_at,true)}. Diese damalige Aufteilung bleibt unverändert.`),button('Zurück zu den Aufteilungen',()=>accountingAction(()=>componentDialog(eventId,{offset})),'small'));
  } else {
    const pending=componentPendingOperation(api.pendingOperations(),eventId);
    content.append(panel('Dokumentierter Stand',el('p',{},`Zahlungsbetrag ${formatMoney(source.amount)} · Dokumentiert ${formatMoney(source.documented_amount)} · Noch ungeklärt ${formatMoney(source.undocumented_amount)}`),el('p',{},`Davon ohne Rechnungszuordnung: ${formatMoney(source.unallocated_amount)}`),
      !source.eligible?notice(COMPONENT_BLOCKS[source.blocked_reason]||'Neue Aufteilungen sind für diesen Zahlungsnachweis gesperrt.'):null,
      !source.writes_allowed?notice('Neue Aufteilungen sind durch aktuelle Rechte oder den Betriebszustand gesperrt. Vorhandene Nachweise bleiben lesbar.','warn'):null,
      pending?notice('Eine Bestätigungsantwort ist offen. Unter „Antworten offen“ unverändert wiederholen, bevor ein neuer Vorgang beginnt.','warn'):null,
      rights.prepare&&!pending?button('Beleganteil auswählen',()=>accountingAction(()=>componentPortions(source,event)),'primary'):null,
      button('Ursprünglichen Zahlungsnachweis ansehen',()=>accountingAction(()=>accountingEventDialog(eventId)),'small')),
      panel('Bestätigte Aufteilungen',rows(history.items,entry=>row(`${entry.portion.number||'Geprüfter Beleg'} · ${formatMoney(entry.amount)}`,`${entry.portion.party_name} · ${formatDate(entry.created_at,true)} · ${entry.reason}`,
        [button('Aufteilung ansehen',()=>accountingAction(()=>componentDialog(eventId,{offset,entryId:entry.id})),'small')],`Netto ${formatMoney(entry.net)} · ${componentTaxLabel(entry.portion)} ${formatMoney(entry.tax)}`),'Noch keine Belegaufteilung bestätigt.'),allocationPagination(history,offset,next=>componentDialog(eventId,{offset:next}))));
  }
  dialog(entryId?'Bestätigte Belegaufteilung':'Beleganteile',content);
}
async function componentPortions(source,event,offset=0) {
  componentWritable(source);const generation=api.generation,render=state.render,previous=modal;
  const page=accountingPage(await api.get(query(biz(componentPath(source.event_id,'/portions')),{limit:25,offset})),offset);
  if(generation!==api.generation||render!==state.render||previous!==modal)return;
  for(const portion of page.items)componentPortion(portion,source.event_id);
  dialog('Beleganteil auswählen',el('div',{class:'stack accounting break-word','data-accounting-detail':'true'},notice('Eine Aufteilung umfasst immer den ganzen ausgewählten Beleganteil. Nicht zugeordnete oder ungeklärte Reste werden nicht automatisch verteilt.'),
    rows(page.items,portion=>row(`${portion.number||'Geprüfter Beleg'} · ${formatMoney(portion.amount)}`,portion.party_name,
      [componentOriginal(event,portion),portion.eligible?button('Diesen Beleganteil aufteilen',()=>componentInput(source,event,portion),'primary'):null],portion.eligible?`${portion.groups.length} belegte Gruppe${portion.groups.length===1?'':'n'}`:COMPONENT_BLOCKS[portion.blocked_reason]||'Dieser Beleganteil benötigt eine Klärung.'),'Keine noch offenen Beleganteile vorhanden.'),
    allocationPagination(page,offset,next=>componentPortions(source,event,next)),button('Zurück zu den Aufteilungen',()=>accountingAction(()=>componentDialog(source.event_id)),'small')));
}
function componentInput(source,event,portion) {
  const generation=api.generation,render=state.render;
  const fields=portion.groups.map((group,index)=>field('group_'+index,componentGroupLabel(group)+' – Bruttoanteil EUR','decimal',portion.groups.length===1?portion.amount:'',{
    wide:true,help:`Laut Beleg: netto ${formatMoney(group.net)} + ausgewiesene Steuer ${formatMoney(group.tax)} = brutto ${formatMoney(group.gross)}. Verfügbarer Bruttorest ${formatMoney(group.remaining_gross)}. Nicht verwendete Gruppen leer lassen.`}));
  fields.push(field('reason','Begründung der Aufteilung','text','',{required:true,maxLength:1000,wide:true}));
  const editor=form('',fields,async values=>{
    componentWritable(source);
    const groups=portion.groups.flatMap((group,index)=>values['group_'+index]===undefined||String(values['group_'+index]).trim()===''?[]:[{group_id:group.group_id,amount:values['group_'+index]}]);
    const body=componentPreviewData(source,portion,groups,values.reason);
    try {
      const result=await api.post(biz(componentPath(source.event_id,'/preview')),body);
      if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;
      componentConfirm(source,event,body,componentPreview(result,body,source.event_id));return undefined;
    } catch(error) {
      if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;
      if([403,404].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}
      throw error;
    }
  },{key:'component-preview-'+source.event_id,submit:'Unverbindliche Vorschau prüfen',description:`${portion.number||'Geprüfter Beleg'} · ${portion.party_name}. Fester ganzer Beleganteil: ${formatMoney(portion.amount)}. Die Gruppensumme muss genau diesem Betrag entsprechen. Bei mehreren Gruppen wird nichts automatisch verteilt.`,
    extra:el('div',{class:'actions'},componentOriginal(event,portion),button('Aktuellen Stand neu laden',()=>accountingAction(()=>componentDialog(source.event_id)),'small'))});
  editor.dataset.accountingDetail='true';dialog('Beleganteil aufteilen',editor);
}
function componentConfirm(source,event,body,preview) {
  const generation=api.generation,render=state.render;
  const editor=form('',[field('confirmation','Ich bestätige diese dokumentarische Netto-/Steueraufteilung des ganzen Beleganteils.','checkbox',false,{required:true})],async(values,key)=>{
    componentWritable(source);const result=await accountingSave(editor,generation,key,componentPath(source.event_id,'/confirm'),componentConfirmData(body,preview,values.confirmation));
    return render===state.render?result:undefined;
  },{key:componentPendingKey(source.event_id),submit:'Belegaufteilung verbindlich bestätigen',description:'Die Vorschau speichert noch keine Aufteilung. Bei einer verlorenen Bestätigungsantwort dieselbe Anfrage unverändert wiederholen. Für einen neuen Vorgang müssen die verfügbaren Gruppenreste frisch geprüft werden.',
    extra:el('div',{class:'stack'},componentRecord(preview,event),button('Aktuellen Stand neu laden',()=>accountingAction(()=>componentDialog(source.event_id)),'small')),
    after:async()=>{const render=state.render+1,section=state.section;await refresh();if(generation===api.generation&&state.render===render&&state.section===section&&!modal)await componentDialog(source.event_id);}});
  editor.dataset.accountingDetail='true';dialog('Belegaufteilung prüfen',editor);
}

const REFUND_BLOCKS={not_customer_refund:'Dieser Zahlungsnachweis ist keine Kundenerstattung.',source_customer_unresolved:'Die ursprüngliche Kundenbindung der Erstattung ist noch ungeklärt.',unsupported_document:'Diese ursprüngliche Rechnung unterstützt derzeit keine Ursprungsbindung.',unallocated:'Dieser Erstattungsrest ist noch keiner Rechnung zugeordnet.',fully_documented:'Alle ursprünglichen Erstattungsanteile sind gebunden.'};
const REFUND_NOTICE='Dokumentarische Ursprungsbindung. Keine neue Zahlung, Rechnungszuordnung oder Steuerbuchung. Gruppenkapazität wird noch nicht wieder freigegeben. Steuerliche Einordnung offen; kein Steuerergebnis.';
const CAPACITY_BLOCKS={...COMPONENT_BLOCKS,not_customer_receipt:'Dieser Zahlungsnachweis ist keine Kundeneinnahme.',source_access_required:'Für zusätzliche freigegebene Beträge fehlen vollständige Quellenrechte.',receipt_before_capacity:'Der Einnahmentag liegt vor dem zulässigen Datum dieser Restbeträge.',legacy_writer_required:'Diese Rechnung verwendet weiterhin ihre ursprüngliche Belegaufteilung.',refund_origin_unresolved:'Mindestens eine zugeordnete Erstattung ist noch nicht vollständig geklärt. Zusätzliche Rücknahmecents bleiben gesperrt.'};
const CAPACITY_NOTICE='Dokumentarische Belegaufteilung mit ausdrücklich wiederverwendeten Beträgen. Keine neue Zahlung oder Rechnungszuordnung. Steuerliche Einordnung offen; kein Steuerergebnis. Für die hier neu aufgeteilten Zahlungsanteile ist die Zuordnung späterer Erstattungen noch nicht verfügbar.';
function capacityNotice() { return refundV2Rights().available?'Dokumentarische Belegaufteilung mit ausdrücklich wiederverwendeten Beträgen. Keine neue Zahlung oder Rechnungszuordnung. Steuerliche Einordnung offen; kein Steuerergebnis. Passende Erstattungen können diesen Zahlungsanteilen ausdrücklich zugeordnet und anschließend erneut als Restbeträge übernommen werden.':CAPACITY_NOTICE; }
function capacityRights(source=null) { return capacityAccess({permissions:[...state.globalPermissions],features:[...state.features],capabilities:[...state.capabilities],readonly:state.readonly},state.organization,source,navigator.onLine); }
function capacityWritable(source=null) { if(!capacityRights(source).prepare)throw new ApiError('Eine Wiederbelegung benötigt Internet, aktuelle globale Accounting-/Finanzschreibrechte und einen freigegebenen Finanzbetrieb.',423); }
function capacityPath(id,suffix='') { return `/accounting/components/v2/events/${accountingId(id)}${suffix}`; }
function capacityContext() { const generation=api.generation,render=state.render,previous=modal;return ()=>generation===api.generation&&render===state.render&&previous===modal&&capacityRights().read; }
function capacitySummary(value) { return `netto ${formatMoney(value.net)} · ausgewiesene Steuer ${formatMoney(value.tax)} · brutto ${formatMoney(value.gross)}`; }
async function capacityAuthorize(eventId) { const source=capacityState(await api.get(biz(capacityPath(eventId))));if(source.event_id!==eventId)throw new ApiError('Der aktuelle Zahlungsnachweis stimmt nicht überein.',502);return source; }
function capacityOriginal(eventId,portion) { return button('Rechnungs-PDF ansehen',()=>accountingAction(async()=>{const current=capacityContext();await capacityAuthorize(eventId);if(current())await download(biz(`/documents/${portion.document_id}/pdf`),`${portion.number}.pdf`); }),'small'); }
function capacityRecord(value) {
  capacityLines(value);
  return el('div',{class:'stack accounting break-word'},panel(value.portion.number,el('p',{},value.portion.party_name),el('p',{},`Ganzer Beleganteil: ${formatMoney(value.amount)} · ${value.reason}`),capacityOriginal(value.event_id,value.portion)),
    panel('Dokumentierte Wiederbelegung',el('p',{},`Nettoanteil ${formatMoney(value.net)}`),el('p',{},`Ausgewiesener Steueranteil ${formatMoney(value.tax)}`),el('p',{},`Bruttoanteil ${formatMoney(value.amount)}`)),
    panel('Aufteilung aus tatsächlichen Restbeträgen',rows(value.lines,line=>row(componentGroupLabel(value.portion.groups.find(item=>item.group_id===line.group_id)),`Netto ${formatMoney(line.net)} · Ausgewiesene Steuer ${formatMoney(line.tax)} · Brutto ${formatMoney(line.amount)}`,[],`Verbleibend netto ${formatMoney(line.remaining_net)} · Steuer ${formatMoney(line.remaining_tax)} · brutto ${formatMoney(line.remaining_gross)}`))),
    panel('Mit dieser Bestätigung übernommene Beträge',rows(value.capacity_changes,change=>row(componentGroupLabel(value.portion.groups.find(item=>item.group_id===change.group_id)),`Vorhandener Rest: ${capacitySummary(change.carry)}`,[],`Neu aus bestätigten Erstattungen: ${capacitySummary(change.returned)}. Zusammen ${capacitySummary(change.basis)}.${change.not_before_date?' Verwendbar ab '+formatDate(change.not_before_date)+'.':''}`),'Keine zusätzlichen Erstattungsbeträge übernommen; der vorhandene Rest wird weiter verwendet.')),
    value.action==='takeover_and_document'?notice('Diese Bestätigung übernimmt alle Gruppen der Rechnung gemeinsam in die Aufteilung mit wiederverwendbaren Restbeträgen. Frühere Aufteilungen bleiben unverändert.'):null,notice(capacityNotice()));
}
async function capacityDialog(eventId,{offset=0,legacyOffset=0,entryId=null,legacyHistory=null,event=null}={}) {
  if(!capacityRights().read)throw new ApiError('Dieser Server oder Ihre aktuellen globalen Rechte erlauben keine Wiederbelegung.',403);
  const current=capacityContext(),[rawState,rawHistory,oldHistory,cash]=await Promise.all([api.get(biz(capacityPath(eventId))),api.get(query(biz(capacityPath(eventId,'/history')),{limit:25,offset})),legacyHistory||api.get(query(biz(componentPath(eventId,'/history')),{limit:25,offset:legacyOffset})),event||api.get(biz(`/accounting/events/${eventId}`))]);
  if(!current())return;const source=capacityState(rawState),history=accountingPage(rawHistory,offset),old=accountingPage(oldHistory,legacyOffset);
  if(source.event_id!==eventId||cash.id!==eventId||[...history.items,...old.items].some(item=>item.event_id!==eventId))throw new ApiError('Die Aufteilungsnachweise gehören nicht zur ausgewählten Einnahme.',502);
  for(const entry of history.items)capacityLines(entry);for(const entry of old.items)componentLines(entry);
  await capacityAuthorize(eventId);if(!current())return;
  const content=el('div',{class:'stack accounting break-word','data-accounting-detail':'true','data-capacity-detail':'true'},notice(capacityNotice()));
  if(entryId) {
    const entry=history.items.find(item=>item.id===entryId);if(!entry)throw new ApiError('Die Historie wurde erweitert. Bitte den Eintrag erneut auswählen.',409);
    content.append(capacityRecord(entry),el('p',{class:'caption'},`Bestätigt ${formatDate(entry.created_at,true)}. Diese damaligen Abschnittscents bleiben unverändert.`),button('Zurück zu den Aufteilungen',()=>accountingAction(()=>capacityDialog(eventId,{offset,legacyOffset})),'small'));
  } else {
    const pending=componentPendingOperation(api.pendingOperations(),eventId),rights=capacityRights(source);
    content.append(panel('Dokumentierter Stand',el('p',{},`Zahlungsbetrag ${formatMoney(source.amount)} · Dokumentiert ${formatMoney(source.documented_amount)} · Noch ungeklärt ${formatMoney(source.undocumented_amount)}`),el('p',{},`Davon ohne Rechnungszuordnung: ${formatMoney(source.unallocated_amount)}`),
      !source.eligible?notice(CAPACITY_BLOCKS[source.blocked_reason]||'Neue Aufteilungen sind derzeit gesperrt.'):null,!source.writes_allowed?notice('Neue Bestätigungen sind derzeit gesperrt. Freigegebene Historie bleibt lesbar.','warn'):null,
      pending?notice('Eine Bestätigungsantwort ist offen. Unter „Antworten offen“ zuerst dieselbe unveränderte Anfrage an ihrem ursprünglichen Aufteilungsweg wiederholen.','warn'):null,
      rights.prepare&&!pending?button('Beleganteil auswählen',()=>accountingAction(()=>capacityPortions(source,cash)),'primary'):null,
      button('Ursprünglichen Zahlungsnachweis ansehen',()=>accountingAction(()=>accountingEventDialog(eventId)),'small')),
      panel('Aufteilungen mit wiederverwendbaren Beträgen',rows(history.items,entry=>row(`${entry.portion.number} · ${formatMoney(entry.amount)}`,`${entry.portion.party_name} · ${formatDate(entry.created_at,true)} · ${entry.reason}`,[button('Wiederbelegung ansehen',()=>accountingAction(()=>capacityDialog(eventId,{offset,legacyOffset,entryId:entry.id})),'small')],`Netto ${formatMoney(entry.net)} · Ausgewiesene Steuer ${formatMoney(entry.tax)}`),'Noch keine Wiederbelegung bestätigt.'),allocationPagination(history,offset,next=>capacityDialog(eventId,{offset:next,legacyOffset}))),
      panel('Frühere Belegaufteilungen',rows(old.items,entry=>row(`${entry.portion.number} · ${formatMoney(entry.amount)}`,`${entry.portion.party_name} · ${formatDate(entry.created_at,true)} · ${entry.reason}`,[button('Aufteilung ansehen',()=>accountingAction(()=>componentDialog(eventId,{offset:legacyOffset,entryId:entry.id,legacy:true})),'small')],`Netto ${formatMoney(entry.net)} · Ausgewiesene Steuer ${formatMoney(entry.tax)}`),'Noch keine Belegaufteilung bestätigt.'),allocationPagination(old,legacyOffset,next=>capacityDialog(eventId,{offset,legacyOffset:next}))));
  }
  dialog(entryId?'Bestätigte Wiederbelegung':'Beleganteile',content);
}
async function capacityPortions(source,event,offset=0) {
  capacityWritable(source);const current=capacityContext(),page=accountingPage(await api.get(query(biz(capacityPath(source.event_id,'/portions')),{limit:25,offset})),offset);
  await capacityAuthorize(source.event_id);if(!current())return;capacityWritable(source);
  for(const portion of page.items)capacityPortion(portion,source.event_id);
  dialog('Beleganteil auswählen',el('div',{class:'stack accounting break-word','data-accounting-detail':'true','data-capacity-detail':'true'},notice('Jeder ganze Beleganteil verwendet den aktuell angebotenen Aufteilungsweg seiner Rechnung. Eine offene Bestätigungsantwort muss zuerst unverändert geklärt werden.'),
    rows(page.items,portion=>row(`${portion.number} · ${formatMoney(portion.amount)}`,portion.party_name,[capacityOriginal(source.event_id,portion),portion.eligible?button(portion.action==='document_legacy'?'Diesen Beleganteil aufteilen':portion.action==='takeover_and_document'?'Restbeträge übernehmen und aufteilen':'Verfügbare Restbeträge aufteilen',()=>accountingAction(()=>portion.action==='document_legacy'?capacityLegacyInput(source,event,portion):capacityInput(source,event,portion)),'primary'):null],
      [portion.action==='document_legacy'?'Ursprüngliche Belegaufteilung':portion.action==='takeover_and_document'?'Erstmalige gemeinsame Übernahme aller Rechnungsgruppen':portion.action==='document_current'?'Bereits übernommene Rechnung':CAPACITY_BLOCKS[portion.blocked_reason]||'Klärung erforderlich',portion.pending_blocked_reason?CAPACITY_BLOCKS[portion.pending_blocked_reason]:null].filter(Boolean).join(' · ')),'Keine noch offenen Beleganteile vorhanden.'),
    allocationPagination(page,offset,next=>capacityPortions(source,event,next)),button('Zurück zu den Aufteilungen',()=>accountingAction(()=>componentDialog(source.event_id)),'small')));
}
async function capacityLegacyInput(source,event,portion) {
  capacityWritable(source);const current=capacityContext(),legacy=componentState(await api.get(biz(componentPath(source.event_id))));let selected=null,offset=0;
  for(;;){const page=accountingPage(await api.get(query(biz(componentPath(source.event_id,'/portions')),{limit:100,offset})),offset);selected=page.items.find(item=>item.portion_id===portion.portion_id);if(selected||page.next_offset===null)break;offset=page.next_offset;if(!current())return;}
  await capacityAuthorize(source.event_id);if(!current())return;
  if(!selected)throw new ApiError('Dieser Beleganteil wurde inzwischen dokumentiert oder verändert. Bitte neu laden.',409);
  componentPortion(selected,source.event_id);componentWritable(legacy);componentInput(legacy,event,selected);
}
function capacityInput(source,event,portion) {
  capacityWritable(source);const generation=api.generation,render=state.render,available=portion.groups.filter(group=>componentCents(group.offered_capacity.gross)>0n&&(group.offered_capacity.not_before_date===null||source.cash_date>=group.offered_capacity.not_before_date));
  const fields=available.map((group,index)=>field('group_'+index,componentGroupLabel(group)+' – Bruttoanteil EUR','decimal','',{wide:true,help:`Originalrechnung: ${capacitySummary(group.archive)}. Bereits verfügbar: ${capacitySummary(group.current_capacity)}. Noch nicht übernommen aus Erstattungen: ${capacitySummary(group.pending_returns)}. Für diese Bestätigung angeboten: ${capacitySummary(group.offered_capacity)}.${group.offered_capacity.not_before_date?' Verwendbar ab '+formatDate(group.offered_capacity.not_before_date)+'.':''}`}));
  fields.push(field('reason','Begründung der Wiederbelegung','text','',{required:true,maxLength:1000,wide:true}));
  const editor=form('',fields,async values=>{
    capacityWritable(source);const groups=available.flatMap((group,index)=>values['group_'+index]===undefined||String(values['group_'+index]).trim()===''?[]:[{group_id:group.group_id,amount:values['group_'+index]}]),body=capacityPreviewData(source,portion,groups,values.reason);
    try {
      await capacityAuthorize(source.event_id);if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;capacityWritable(source);
      const result=await api.post(biz(capacityPath(source.event_id,'/preview')),body);if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;
      await capacityAuthorize(source.event_id);if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;capacityWritable(source);capacityConfirm(source,body,capacityPreview(result,body,source));return undefined;
    }catch(error){if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;if([403,404].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}throw error;}
  },{key:'capacity-preview-'+source.event_id,submit:'Wiederbelegung unverbindlich prüfen',description:`${portion.number} · ${portion.party_name}. Ganzer Beleganteil ${formatMoney(portion.amount)}. Beträge ausdrücklich eingeben; es wird nichts automatisch verteilt.`,extra:el('div',{class:'stack'},portion.pending_blocked_reason?notice(CAPACITY_BLOCKS[portion.pending_blocked_reason]||'Zusätzliche Erstattungsbeträge bleiben gesperrt.','warn'):null,capacityOriginal(source.event_id,portion),notice(capacityNotice()),button('Aktuellen Stand neu laden',()=>accountingAction(()=>componentDialog(source.event_id)),'small'))});
  editor.dataset.accountingDetail='true';editor.dataset.capacityDetail='true';dialog('Restbeträge aufteilen',editor);
}
function capacityConfirm(source,body,preview) {
  const generation=api.generation,render=state.render,editor=form('',[field('confirmation','Ich bestätige die ganze Wiederbelegung und alle gezeigten Kapazitätsänderungen.','checkbox',false,{required:true})],async(values,key)=>{
    capacityWritable(source);const data=capacityConfirmData(body,preview,source,values.confirmation);
    try{await capacityAuthorize(source.event_id);}catch(error){if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;if([403,404].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}throw error;}
    if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;capacityWritable(source);const result=await accountingSave(editor,generation,key,capacityPath(source.event_id,'/confirm'),data);return render===state.render?result:undefined;
  },{key:componentPendingKey(source.event_id),submit:'Wiederbelegung verbindlich bestätigen',description:'Erst diese Bestätigung speichert die ganze Aufteilung und die gezeigten Übernahmen gemeinsam. Bei unklarer Antwort zuerst dieselbe Anfrage unverändert wiederholen.',extra:el('div',{class:'stack'},capacityRecord(preview),button('Aktuellen Stand neu laden',()=>accountingAction(()=>componentDialog(source.event_id)),'small')),
    after:async()=>{const render=state.render+1,section=state.section;await refresh();if(generation===api.generation&&state.render===render&&state.section===section&&!modal&&capacityRights().read)await componentDialog(source.event_id);}});
  editor.dataset.accountingDetail='true';editor.dataset.capacityDetail='true';dialog('Wiederbelegung prüfen',editor);
}
function refundRights(source=null) { return refundAccess({permissions:[...state.globalPermissions],features:[...state.features],capabilities:[...state.capabilities],readonly:state.readonly},state.organization,source,navigator.onLine); }
function refundWritable(source=null) { if(!refundRights(source).prepare)throw new ApiError('Eine neue Ursprungsbindung benötigt Internet, aktuelle globale Accounting-/Finanzschreibrechte und einen freigegebenen Finanzbetrieb.',423); }
function refundPath(id,suffix='') { return `/accounting/refunds/events/${accountingId(id)}${suffix}`; }
function refundContext() { const generation=api.generation,render=state.render,previous=modal;return ()=>generation===api.generation&&render===state.render&&previous===modal&&refundRights().read; }
function refundAuthorizeCurrent(eventId,origins,selection=false) { return refundAuthorize(api,eventId,origins,{versioned:refundV2Rights().available,selection}); }
function refundReferences(value,line=false) { return `${formatDate(value[line?'origin_cash_date':'cash_date'])} · Zahlungsnachweis: ${value[line?'origin_evidence_reference':'evidence_reference']} · Verwendungszweck: ${value[line?'origin_reference':'reference']||'ohne Angabe'}`; }
async function refundOriginal(eventId,portion,origins) { const current=refundContext();await refundAuthorizeCurrent(eventId,origins);if(current())await download(biz(`/documents/${portion.document_id}/pdf`),`${portion.number}.pdf`); }
function refundRecord(value) {
  refundLines(value);
  return el('div',{class:'stack accounting break-word'},panel(value.portion.number,el('p',{},value.portion.party_name),el('p',{},refundReferences(value)),el('p',{},`Ganzer Erstattungsanteil: ${formatMoney(value.amount)} · ${value.reason}`)),
    panel('Dokumentierte Rücknahme',el('p',{},`Nettoanteil: ${formatMoney(value.net)}`),el('p',{},`Ausgewiesener Steueranteil: ${formatMoney(value.tax)}`),el('p',{},`Bruttoanteil: ${formatMoney(value.amount)}`)),
    panel('Ausdrücklich gewählte Ursprünge',rows(value.lines,line=>row(refundOriginLabel(line),refundReferences(line,true),[],
      `Rücknahme: netto ${formatMoney(line.net)} · ausgewiesene Steuer ${formatMoney(line.tax)} · brutto ${formatMoney(line.amount)}. Bisher zurückgenommen ${formatMoney(line.gross_before)} → ${formatMoney(line.gross_after)}. Verbleibend netto ${formatMoney(line.remaining_net)} · Steuer ${formatMoney(line.remaining_tax)} · brutto ${formatMoney(line.remaining_gross)}.`))),notice(REFUND_NOTICE),
    button('Rechnungs-PDF ansehen',()=>accountingAction(()=>refundOriginal(value.event_id,value.portion,value.lines)),'small'));
}
async function refundDialog(eventId,{offset=0,entryId=null,legacy=false}={}) {
  if(!refundRights().read)throw new ApiError('Dieser Server oder Ihre aktuellen globalen Rechte erlauben keine Erstattungsursprünge.',403);
  const current=refundContext(),[rawState,rawHistory]=await Promise.all([api.get(biz(refundPath(eventId))),api.get(query(biz(refundPath(eventId,'/history')),{limit:25,offset}))]);
  if(!current())return;const source=refundState(rawState),history=accountingPage(rawHistory,offset);
  if(source.event_id!==eventId||history.items.some(item=>item.event_id!==eventId))throw new ApiError('Der Erstattungsstand gehört nicht zum gewählten Zahlungsnachweis.',502);
  if(!legacy&&refundV2Rights().read)return refundV2Dialog(eventId,{legacyOffset:offset,legacyHistory:history});
  for(const entry of history.items)refundLines(entry);
  await refundAuthorizeCurrent(eventId,history.items.flatMap(item=>item.lines));if(!current())return;
  const content=el('div',{class:'stack accounting break-word','data-accounting-detail':'true','data-refund-detail':'true'},notice(REFUND_NOTICE));
  if(entryId) {
    const entry=history.items.find(item=>item.id===entryId);if(!entry)throw new ApiError('Die Historie wurde erweitert. Bitte den Eintrag in der aktuellen Liste erneut öffnen.',409);
    content.append(refundRecord(entry),el('p',{class:'caption'},`Bestätigt ${formatDate(entry.created_at,true)}. Die damaligen Beträge bleiben unverändert.`),button('Zurück zu den Ursprungsbindungen',()=>accountingAction(()=>refundDialog(eventId,{offset})),'small'));
  } else {
    const pending=refundPendingOperation(api.pendingOperations(),eventId),rights=refundRights(source);
    content.append(panel('Dokumentierter Ursprungsstand',el('p',{},refundReferences(source)),el('p',{},`Erstattung ${formatMoney(source.amount)} · Ursprung dokumentiert ${formatMoney(source.origin_documented_amount)} · Noch ungeklärt ${formatMoney(source.origin_unresolved_amount)}`),el('p',{},`Davon ohne ursprüngliche Rechnungszuordnung: ${formatMoney(source.unallocated_amount)}`),
      !source.eligible?notice(REFUND_BLOCKS[source.blocked_reason]||'Die Erstattung benötigt eine Klärung.'):null,!source.writes_allowed?notice('Neue Bindungen sind durch aktuelle Rechte oder den Betriebszustand gesperrt. Freigegebene Historie bleibt lesbar.','warn'):null,
      pending?notice('Eine Bestätigungsantwort ist offen. Unter „Antworten offen“ dieselbe unveränderte Anfrage wiederholen. Gespeicherte Ursprungseinzelheiten werden hier nicht erneut angezeigt.','warn'):null,
      rights.prepare&&!pending?button('Erstattungsanteil auswählen',()=>accountingAction(()=>refundPortions(source)),'primary'):null,
      button('Ursprünglichen Zahlungsnachweis ansehen',()=>accountingAction(()=>accountingEventDialog(eventId)),'small')),
      panel('Bestätigte Ursprungsbindungen',rows(history.items,entry=>row(`${entry.portion.number} · ${formatMoney(entry.amount)}`,`${entry.portion.party_name} · ${formatDate(entry.created_at,true)} · ${entry.reason}`,[button('Ursprungsbindung ansehen',()=>accountingAction(()=>refundDialog(eventId,{offset,entryId:entry.id})),'small')],`Netto ${formatMoney(entry.net)} · Ausgewiesener Steueranteil ${formatMoney(entry.tax)}`),'Noch keine Ursprungsbindung bestätigt.'),allocationPagination(history,offset,next=>refundDialog(eventId,{offset:next}))),
      notice('Nur dieser freigegebene Zahlungsnachweis und seine berechtigten Ursprünge. Andere oder noch nicht übernommene Erstattungen können ungeklärt bleiben.'));
  }
  dialog(entryId?'Bestätigte Ursprungsbindung':'Erstattungsursprünge',content);
}
async function refundPortions(source,offset=0) {
  refundWritable(source);const current=refundContext(),page=accountingPage(await api.get(query(biz(refundPath(source.event_id,'/portions')),{limit:25,offset})),offset);
  await refundAuthorizeCurrent(source.event_id,[],true);if(!current())return;refundWritable(source);
  for(const portion of page.items)refundPortion(portion,source.event_id);
  dialog('Erstattungsanteil auswählen',el('div',{class:'stack accounting break-word','data-accounting-detail':'true','data-refund-detail':'true'},notice('Rechnung und ganzer ursprünglicher Erstattungsanteil sind fest. Die Ursprünge werden im nächsten Schritt ausdrücklich gewählt.'),rows(page.items,portion=>row(`${portion.number} · ${formatMoney(portion.amount)}`,portion.party_name,
    [portion.eligible?button('Ursprünge auswählen',()=>accountingAction(()=>refundOrigins(source,portion)),'primary'):null],portion.eligible?'Ganzer ursprünglicher Erstattungsanteil':REFUND_BLOCKS[portion.blocked_reason]||'Klärung erforderlich'),'Keine offenen ursprünglichen Erstattungsanteile vorhanden.'),allocationPagination(page,offset,next=>refundPortions(source,next))));
}
async function refundOrigins(source,portion,offset=0,draft={choices:new Map(),reason:''}) {
  refundWritable(source);const current=refundContext(),generation=api.generation,page=accountingPage(await api.get(query(biz(refundPath(source.event_id,'/origins')),{portion_id:portion.portion_id,limit:25,offset})),offset);
  for(const origin of page.items)refundOrigin(origin,portion,source.cash_date);
  const shown=[...page.items,...[...draft.choices.values()].map(item=>item.origin).filter(origin=>!page.items.some(item=>refundLotKey(item)===refundLotKey(origin)))];
  try{await refundAuthorizeCurrent(source.event_id,shown,true);}catch(error){if(current()){closeModal();await refresh();if(generation===api.generation)showError(error);}return;}
  if(!current())return;refundWritable(source);
  const render=state.render,fields=shown.map((origin,index)=>field('origin_'+index,refundOriginLabel(origin)+' – Rücknahmebetrag EUR','decimal',draft.choices.get(refundLotKey(origin))?.amount||'',{
    wide:true,help:`${refundReferences(origin)}. Ursprünglich netto ${formatMoney(origin.net)} + Steuer ${formatMoney(origin.tax)} = brutto ${formatMoney(origin.amount)}. Verfügbar netto ${formatMoney(origin.remaining_net)} · Steuer ${formatMoney(origin.remaining_tax)} · brutto ${formatMoney(origin.remaining_amount)}. Nicht gewählte Ursprünge leer lassen.`}));
  fields.push(field('reason','Begründung der Ursprungsbindung','text',draft.reason,{required:true,maxLength:1000,wide:true}));
  const remember=()=>{shown.forEach((origin,index)=>{const amount=editor.controls.get('origin_'+index).input.value.trim(),key=refundLotKey(origin);if(amount)draft.choices.set(key,{origin,amount});else draft.choices.delete(key);});draft.reason=editor.controls.get('reason').input.value;};
  const editor=form('',fields,async()=>{
    refundWritable(source);remember();const choices=[...draft.choices.values()].map(item=>({origin:{...item.origin},amount:item.amount})),body=refundPreviewData(source,portion,choices,draft.reason);
    try {
      await refundAuthorizeCurrent(source.event_id,choices.map(item=>item.origin),true);if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;refundWritable(source);
      const result=await api.post(biz(refundPath(source.event_id,'/preview')),body);
      if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;
      await refundAuthorizeCurrent(source.event_id,choices.map(item=>item.origin),true);if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;refundWritable(source);
      refundConfirm(source,body,refundPreview(result,body,source,choices),choices);return undefined;
    } catch(error) {if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;if([403,404,423].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}throw error;}
  },{key:'refund-preview-'+source.event_id,submit:'Ursprungsbindung unverbindlich prüfen',description:`${portion.number} · ${portion.party_name}. Fester ganzer Erstattungsanteil ${formatMoney(portion.amount)}. Positive Beträge ausdrücklich eingeben; ihre Summe muss genau passen. Keine automatische Auswahl.`,extra:el('div',{class:'stack'},
    page.items.length?null:notice('Keine berechtigten passenden Ursprünge mit verfügbarem Rest vorhanden. Fehlende Ursprünge werden nicht geschätzt.'),
    allocationPagination(page,offset,next=>{remember();return refundOrigins(source,portion,next,draft);}),notice(REFUND_NOTICE),button('Aktuellen Stand neu laden',()=>accountingAction(()=>refundDialog(source.event_id)),'small'))});
  editor.dataset.accountingDetail='true';editor.dataset.refundDetail='true';dialog('Erstattungsursprünge auswählen',editor);
}
function refundConfirm(source,body,preview,choices) {
  const generation=api.generation,render=state.render;
  const editor=form('',[field('confirmation','Ich bestätige die gewählten Ursprünge und dokumentierten Rücknahmebeträge des ganzen Erstattungsanteils.','checkbox',false,{required:true})],async(values,key)=>{
    refundWritable(source);const data=refundConfirmData(body,preview,source,choices,values.confirmation),origins=choices.map(item=>({origin_event_id:item.origin.origin_event_id}));
    try {await refundAuthorizeCurrent(source.event_id,origins,true);}catch(error){if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;if([403,404,423].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}throw error;}
    if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;refundWritable(source);
    refundPendingSources.set(key,{generation,eventId:source.event_id,origins});
    try {const result=await accountingSave(editor,generation,key,refundPath(source.event_id,'/confirm'),data);return render===state.render?result:undefined;}
    finally {if(!api.pendingOperations().some(item=>item.key===key))refundPendingSources.delete(key);}
  },{key:refundPendingKey(source.event_id),submit:'Ursprungsbindung verbindlich bestätigen',description:'Erst diese gesonderte Bestätigung speichert die Ursprungsbindung. Eine verlorene Antwort mit derselben unveränderten Anfrage wiederholen; neue Vorgänge benötigen frisch geprüfte Ursprungsreste.',
    extra:el('div',{class:'stack'},refundRecord(preview),button('Aktuellen Stand neu laden',()=>accountingAction(()=>refundDialog(source.event_id)),'small')),
    after:async()=>{const render=state.render+1,section=state.section;await refresh();if(generation===api.generation&&state.render===render&&state.section===section&&!modal&&refundRights().read)await refundDialog(source.event_id);}});
  editor.dataset.accountingDetail='true';editor.dataset.refundDetail='true';dialog('Erstattungsursprung prüfen',editor);
}

const REFUND_V2_NOTICE='Dokumentarische Ursprungsbindung. Ursprüngliche und wiederverwendete Zahlungsanteile ausdrücklich auswählen. Keine neue Zahlung, Rechnungszuordnung oder Steuerbuchung. Erst eine spätere bestätigte Wiederbelegung übernimmt die Rücknahmecents als Restbeträge. Steuerliche Einordnung offen; kein Steuerergebnis.';
function refundV2Rights(source=null) { return refundV2Access({permissions:[...state.globalPermissions],features:[...state.features],capabilities:[...state.capabilities],readonly:state.readonly},state.organization,source,navigator.onLine); }
function refundV2Writable(source=null) { if(!refundV2Rights(source).prepare)throw new ApiError('Eine neue Ursprungsbindung benötigt Internet, aktuelle Buchführungs- und Finanzrechte und einen freigegebenen Finanzbetrieb.',423); }
function refundV2Path(id,suffix='') { return `/accounting/refunds/v2/events/${accountingId(id)}${suffix}`; }
function refundV2Context() { const generation=api.generation,render=state.render,previous=modal;return ()=>generation===api.generation&&render===state.render&&previous===modal&&refundV2Rights().read; }
async function refundV2Original(eventId,portion,origins) { const current=refundV2Context();await refundV2Authorize(api,eventId,origins);if(current())await download(biz(`/documents/${portion.document_id}/pdf`),`${portion.number}.pdf`); }
function refundV2Record(value) {
  refundV2Lines(value);
  return el('div',{class:'stack accounting break-word'},panel(value.portion.number,el('p',{},value.portion.party_name),el('p',{},refundReferences(value)),el('p',{},`Ganzer Erstattungsanteil ${formatMoney(value.amount)} · ${value.reason}`)),
    panel('Dokumentierte Rücknahme',el('p',{},`Nettoanteil ${formatMoney(value.net)}`),el('p',{},`Ausgewiesener Steueranteil ${formatMoney(value.tax)}`),el('p',{},`Bruttoanteil ${formatMoney(value.amount)}`)),
    panel('Ausdrücklich gewählte Ursprünge',rows(value.lines,line=>row(refundV2OriginLabel(line),refundReferences(line,true),[],`Rücknahme: netto ${formatMoney(line.net)} · ausgewiesene Steuer ${formatMoney(line.tax)} · brutto ${formatMoney(line.amount)}. Insgesamt bisher zurückgenommen ${formatMoney(line.gross_before)} → ${formatMoney(line.gross_after)}. Verbleibend netto ${formatMoney(line.remaining_net)} · Steuer ${formatMoney(line.remaining_tax)} · brutto ${formatMoney(line.remaining_gross)}.`))),
    value.action==='takeover_and_bind'?notice('Diese Bestätigung aktiviert die Zuordnung zu wiederverwendeten Zahlungsanteilen für die gesamte Rechnung. Frühere Erstattungsnachweise bleiben unverändert.'):null,notice(REFUND_V2_NOTICE),
    button('Rechnungs-PDF ansehen',()=>accountingAction(()=>refundV2Original(value.event_id,value.portion,value.lines)),'small'));
}
async function refundV2Dialog(eventId,{offset=0,legacyOffset=0,entryId=null,legacyHistory=null}={}) {
  if(!refundV2Rights().read)throw new ApiError('Dieser Server oder Ihre aktuellen Rechte erlauben keine Zuordnung zu wiederverwendeten Zahlungsanteilen.',403);
  const current=refundV2Context(),[rawState,rawHistory,rawLegacy]=await Promise.all([api.get(biz(refundV2Path(eventId))),api.get(query(biz(refundV2Path(eventId,'/history')),{limit:25,offset})),legacyHistory||api.get(query(biz(refundPath(eventId,'/history')),{limit:25,offset:legacyOffset}))]);
  if(!current())return;const source=refundV2State(rawState),history=accountingPage(rawHistory,offset),old=accountingPage(rawLegacy,legacyOffset);
  if(source.event_id!==eventId||[...history.items,...old.items].some(item=>item.event_id!==eventId))throw new ApiError('Die Erstattungsnachweise gehören nicht zum ausgewählten Geldfluss.',502);
  for(const entry of history.items)refundV2Lines(entry);for(const entry of old.items)refundLines(entry);
  await refundV2Authorize(api,eventId,[]);if(!current())return;
  const content=el('div',{class:'stack accounting break-word','data-accounting-detail':'true','data-refund-detail':'true','data-refund-v2-detail':'true'},notice(REFUND_V2_NOTICE));
  if(entryId) {
    const entry=history.items.find(item=>item.id===entryId);if(!entry)throw new ApiError('Die Historie wurde erweitert. Bitte den Eintrag erneut auswählen.',409);
    content.append(refundV2Record(entry),el('p',{class:'caption'},`Bestätigt ${formatDate(entry.created_at,true)}. Diese damaligen Rücknahmecents bleiben unverändert.`),button('Zurück zu den Ursprungsbindungen',()=>accountingAction(()=>refundV2Dialog(eventId,{offset,legacyOffset})),'small'));
  } else {
    const pending=refundPendingOperation(api.pendingOperations(),eventId),rights=refundV2Rights(source);
    content.append(panel('Dokumentierter Ursprungsstand',el('p',{},refundReferences(source)),el('p',{},`Erstattung ${formatMoney(source.amount)} · Ursprung dokumentiert ${formatMoney(source.origin_documented_amount)} · Noch ungeklärt ${formatMoney(source.origin_unresolved_amount)}`),el('p',{},`Davon ohne ursprüngliche Rechnungszuordnung: ${formatMoney(source.unallocated_amount)}`),
      !source.eligible?notice(REFUND_BLOCKS[source.blocked_reason]||'Die Erstattung benötigt eine Klärung.'):null,!source.writes_allowed?notice('Neue Bindungen sind derzeit gesperrt. Freigegebene Historie bleibt lesbar.','warn'):null,
      pending?notice('Eine Bestätigungsantwort ist offen. Unter „Antworten offen“ zuerst dieselbe unveränderte Anfrage an ihrem ursprünglichen Zuordnungsweg wiederholen.','warn'):null,
      rights.prepare&&!pending?button('Erstattungsanteil auswählen',()=>accountingAction(()=>refundV2Portions(source)),'primary'):null,
      button('Ursprünglichen Zahlungsnachweis ansehen',()=>accountingAction(()=>accountingEventDialog(eventId)),'small')),
      panel('Ursprungsbindungen für wiederverwendbare Beleganteile',rows(history.items,entry=>row(`${entry.portion.number} · ${formatMoney(entry.amount)}`,`${entry.portion.party_name} · ${formatDate(entry.created_at,true)} · ${entry.reason}`,[button('Bindung ansehen',()=>accountingAction(()=>refundV2Dialog(eventId,{offset,legacyOffset,entryId:entry.id})),'small')],`Netto ${formatMoney(entry.net)} · Ausgewiesene Steuer ${formatMoney(entry.tax)}`),'Noch keine neue Ursprungsbindung bestätigt.'),allocationPagination(history,offset,next=>refundV2Dialog(eventId,{offset:next,legacyOffset}))),
      panel('Frühere Ursprungsbindungen',rows(old.items,entry=>row(`${entry.portion.number} · ${formatMoney(entry.amount)}`,`${entry.portion.party_name} · ${formatDate(entry.created_at,true)} · ${entry.reason}`,[button('Ursprungsbindung ansehen',()=>accountingAction(()=>refundDialog(eventId,{offset:legacyOffset,entryId:entry.id,legacy:true})),'small')],`Netto ${formatMoney(entry.net)} · Ausgewiesene Steuer ${formatMoney(entry.tax)}`),'Noch keine Ursprungsbindung bestätigt.'),allocationPagination(old,legacyOffset,next=>refundV2Dialog(eventId,{offset,legacyOffset:next}))));
  }
  dialog(entryId?'Bestätigte Ursprungsbindung':'Erstattungsursprünge',content);
}
async function refundV2Portions(source,offset=0) {
  refundV2Writable(source);const current=refundV2Context(),page=accountingPage(await api.get(query(biz(refundV2Path(source.event_id,'/portions')),{limit:25,offset})),offset);
  await refundV2Authorize(api,source.event_id,[],{selection:true});if(!current())return;refundV2Writable(source);for(const portion of page.items)refundV2Portion(portion,source.event_id);
  dialog('Erstattungsanteil auswählen',el('div',{class:'stack accounting break-word','data-accounting-detail':'true','data-refund-detail':'true','data-refund-v2-detail':'true'},notice('Rechnung und ganzer ursprünglicher Erstattungsanteil sind fest. Der aktuelle Zuordnungsweg gilt für die ganze Rechnung; die Zahlungsursprünge werden ausdrücklich gewählt.'),rows(page.items,portion=>row(`${portion.number} · ${formatMoney(portion.amount)}`,portion.party_name,
    [portion.eligible?button('Ursprünge auswählen',()=>accountingAction(()=>portion.action==='bind_legacy'?refundV2LegacyInput(source,portion):refundV2Origins(source,portion)),'primary'):null],portion.action==='bind_legacy'?'Ursprüngliche Belegaufteilungen':portion.action==='takeover_and_bind'?'Zuordnung zu wiederverwendeten Zahlungsanteilen für die Rechnung aktivieren':portion.action==='bind_current'?'Ursprüngliche und wiederverwendete Aufteilungen auswählbar':REFUND_BLOCKS[portion.blocked_reason]||'Klärung erforderlich'),'Keine offenen ursprünglichen Erstattungsanteile vorhanden.'),allocationPagination(page,offset,next=>refundV2Portions(source,next))));
}
async function refundV2LegacyInput(source,portion) {
  refundV2Writable(source);const current=refundV2Context(),legacy=refundState(await api.get(biz(refundPath(source.event_id))));let selected=null,offset=0;
  for(;;){const page=accountingPage(await api.get(query(biz(refundPath(source.event_id,'/portions')),{limit:100,offset})),offset);selected=page.items.find(item=>item.portion_id===portion.portion_id);if(selected||page.next_offset===null)break;offset=page.next_offset;if(!current())return;}
  await refundV2Authorize(api,source.event_id,[],{selection:true});if(!current())return;
  if(!selected)throw new ApiError('Dieser Erstattungsanteil wurde inzwischen gebunden oder verändert. Bitte neu laden.',409);
  refundPortion(selected,source.event_id);refundWritable(legacy);await refundOrigins(legacy,selected);
}
async function refundV2Origins(source,portion,offset=0,draft={choices:new Map(),reason:''}) {
  refundV2Writable(source);const current=refundV2Context(),generation=api.generation,page=accountingPage(await api.get(query(biz(refundV2Path(source.event_id,'/origins')),{portion_id:portion.portion_id,limit:25,offset})),offset);
  for(const origin of page.items)refundV2Origin(origin,portion,source.cash_date);
  const shown=[...page.items,...[...draft.choices.values()].map(item=>item.origin).filter(origin=>!page.items.some(item=>refundV2LotKey(item)===refundV2LotKey(origin)))];
  try{await refundV2Authorize(api,source.event_id,shown,{selection:true});}catch(error){if(current()){closeModal();await refresh();if(generation===api.generation)showError(error);}return;}
  if(!current())return;refundV2Writable(source);
  const render=state.render,fields=shown.map((origin,index)=>field('origin_'+index,refundV2OriginLabel(origin)+' – Rücknahmebetrag EUR','decimal',draft.choices.get(refundV2LotKey(origin))?.amount||'',{
    wide:true,help:`${refundReferences(origin)}. Ursprünglich netto ${formatMoney(origin.net)} + Steuer ${formatMoney(origin.tax)} = brutto ${formatMoney(origin.amount)}. Insgesamt bereits zurückgenommen ${formatMoney(origin.returned_amount)}. Verfügbar netto ${formatMoney(origin.remaining_net)} · Steuer ${formatMoney(origin.remaining_tax)} · brutto ${formatMoney(origin.remaining_amount)}. Nicht gewählte Ursprünge leer lassen.`}));
  fields.push(field('reason','Begründung der Ursprungsbindung','text',draft.reason,{required:true,maxLength:1000,wide:true}));
  const remember=()=>{shown.forEach((origin,index)=>{const amount=editor.controls.get('origin_'+index).input.value.trim(),key=refundV2LotKey(origin);if(amount)draft.choices.set(key,{origin,amount});else draft.choices.delete(key);});draft.reason=editor.controls.get('reason').input.value;};
  const editor=form('',fields,async()=>{
    refundV2Writable(source);remember();const choices=[...draft.choices.values()].map(item=>({origin:{...item.origin},amount:item.amount})),body=refundV2PreviewData(source,portion,choices,draft.reason);
    try {
      await refundV2Authorize(api,source.event_id,choices.map(item=>item.origin),{selection:true});if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;refundV2Writable(source);
      const result=await api.post(biz(refundV2Path(source.event_id,'/preview')),body);if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;
      await refundV2Authorize(api,source.event_id,choices.map(item=>item.origin),{selection:true});if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;refundV2Writable(source);
      refundV2Confirm(source,body,refundV2Preview(result,body,source,choices),choices);return undefined;
    }catch(error){if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;if([403,404,423].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}throw error;}
  },{key:'refund-v2-preview-'+source.event_id,submit:'Ursprungsbindung unverbindlich prüfen',description:`${portion.number} · ${portion.party_name}. Fester ganzer Erstattungsanteil ${formatMoney(portion.amount)}. Positive Beträge ausdrücklich eingeben; ihre Summe muss genau passen. Keine automatische Auswahl.`,extra:el('div',{class:'stack'},
    page.items.length?null:notice('Keine berechtigten passenden Ursprünge mit verfügbarem Rest vorhanden. Fehlende Ursprünge werden nicht geschätzt.'),allocationPagination(page,offset,next=>{remember();return refundV2Origins(source,portion,next,draft);}),notice(REFUND_V2_NOTICE),button('Aktuellen Stand neu laden',()=>accountingAction(()=>refundDialog(source.event_id)),'small'))});
  editor.dataset.accountingDetail='true';editor.dataset.refundDetail='true';editor.dataset.refundV2Detail='true';dialog('Erstattungsursprünge auswählen',editor);
}
function refundV2Confirm(source,body,preview,choices) {
  const generation=api.generation,render=state.render,editor=form('',[field('confirmation','Ich bestätige die gewählten ursprünglichen und wiederverwendeten Zahlungsanteile und die ganze Erstattung.','checkbox',false,{required:true})],async(values,key)=>{
    refundV2Writable(source);const data=refundV2ConfirmData(body,preview,source,choices,values.confirmation);
    try{await refundV2Authorize(api,source.event_id,choices.map(item=>item.origin),{selection:true});}catch(error){if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;if([403,404,423].includes(error.status)){closeModal();await refresh();if(generation===api.generation)showError(error);return undefined;}throw error;}
    if(generation!==api.generation||render!==state.render||!editor.isConnected)return undefined;refundV2Writable(source);
    const result=await accountingSave(editor,generation,key,refundV2Path(source.event_id,'/confirm'),data);return render===state.render?result:undefined;
  },{key:refundPendingKey(source.event_id),submit:'Ursprungsbindung verbindlich bestätigen',description:'Diese gesonderte Bestätigung bindet den ganzen Erstattungsanteil gemeinsam an alle gewählten Ursprünge. Eine unklare Antwort zuerst unverändert wiederholen.',extra:el('div',{class:'stack'},refundV2Record(preview),button('Aktuellen Stand neu laden',()=>accountingAction(()=>refundDialog(source.event_id)),'small')),
    after:async()=>{const render=state.render+1,section=state.section;await refresh();if(generation===api.generation&&state.render===render&&state.section===section&&!modal&&refundV2Rights().read)await refundDialog(source.event_id);}});
  editor.dataset.accountingDetail='true';editor.dataset.refundDetail='true';editor.dataset.refundV2Detail='true';dialog('Erstattungsursprung prüfen',editor);
}

/* Price-free article identities for stock operations, scoped to the open project. */
export async function loadInventoryArticleRefs(read,{projectId='',isCurrent=()=>true}={}) {
  const identifier=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
  if(projectId&&!identifier(projectId))throw new Error('Gültigen Projektbezug für die Artikelauswahl laden.');
  const result=[];let after=null;
  for(let page=0;page<100;page++) {
    if(!isCurrent())throw new Error('Die Artikelauswahl gehört nicht mehr zum aktuellen Arbeitsbereich.');
    const query=new URLSearchParams({limit:'200'});
    if(projectId)query.set('project_id',projectId);
    if(after)query.set('after',after);
    const value=await read('/inventory/articles?'+query);
    if(!isCurrent())throw new Error('Die Artikelauswahl gehört nicht mehr zum aktuellen Arbeitsbereich.');
    if(!value||Object.keys(value).sort().join(',')!=='has_more,items,next_after'||!Array.isArray(value.items)||value.items.length>200||typeof value.has_more!=='boolean')throw new Error('Die Artikelauswahl ist unvollständig. Bitte neu laden.');
    let last=after;
    for(const item of value.items) {
      if(!item||Object.keys(item).sort().join(',')!=='active,code,id,name,revision,unit'||!identifier(item.id)||
          !Number.isSafeInteger(item.revision)||item.revision<1||item.active!==true||
          !['code','name','unit'].every(key=>typeof item[key]==='string')||!item.name.trim()||!item.unit.trim()||last&&item.id<=last)throw new Error('Die Artikelauswahl ist widersprüchlich. Bitte neu laden.');
      result.push(item);last=item.id;
    }
    if(value.has_more) {
      if(!value.items.length||value.next_after!==last)throw new Error('Die Fortsetzung der Artikelauswahl fehlt. Bitte neu laden.');
      after=last;
    } else {
      if(value.next_after!==null)throw new Error('Die Artikelauswahl enthält eine unerwartete Fortsetzung. Bitte neu laden.');
      return result;
    }
  }
  throw new Error('Die Artikelauswahl überschreitet 20.000 Einträge und benötigt eine eingegrenzte Suche.');
}

async function materialView() { return el('div',{class:'stack'},heading('Material','Bestellungen, Lieferungen, Bestände und nachvollziehbare Entnahmen.'),await materialContent(state.projectId)); }
async function materialContent(projectId='') {
  const generation=api.generation,render=state.render;
  const [locations,stock]=await Promise.all([api.get(biz('/inventory/locations')),api.get(biz('/inventory/stock'))]);
  const articles=has('finance.read')?collection(await api.get(biz('/articles'))):[];
  const operationalArticles=state.features.has('inventory_article_refs')?await loadInventoryArticleRefs(path=>api.get(biz(path)),{projectId,
    isCurrent:()=>generation===api.generation&&render===state.render&&has('inventory.read')}):articles;
  const reserved=projectId?collection(await api.get(query(biz('/inventory/reservations'),{project_id:projectId}))):[];
  const controls=[];
  if(canWrite('inventory.write','material'))controls.push(button('Material zurückgeben',()=>action(()=>stockReturns.open(projectId)),'primary'));
  if(state.features.has('inventory_counts')&&state.globalPermissions.has('inventory.read'))controls.push(button('Inventur öffnen',()=>action(()=>inventoryCounts.list()),'small'));
  if(canWrite('inventory.write','material'))controls.push(button('Lagerort anlegen',()=>dialog('Lagerort',form('',[field('name','Name','text','',{required:true})],(data,key)=>mutation(key,'/inventory/locations',data),{key:'location-new'})),'small'),
    button('Bewegung buchen',()=>stockMovementDialog(collection(locations),operationalArticles,projectId),'primary'));
  if(canWrite('finance.write','documents'))controls.push(button('Artikel / Leistung anlegen',()=>articleDialog(),'small'));
  const content=el('div',{class:'stack'},panel('Lagerbestand',el('div',{class:'actions'},controls),table(['Lagerort','Artikel','Bestand','Reserviert','Verfügbar',...(has('finance.read')?['Wert netto']:[])],collection(stock).map(item=>[
    collection(locations).find(location=>location.id===item.location_id)?.name||'Lagerort',item.article_name||articles.find(article=>article.id===item.article_id)?.name||item.article_code||'Artikel',formatQuantity(item.on_hand,item.unit),formatQuantity(item.reserved),formatQuantity(item.available),...(has('finance.read')?[formatMoney(item.stock_value_net)]:[])]))),
    form('Artikel per Code finden',[field('code','Artikelnummer / Barcode','text','',{required:true})],async data=>{const found=await api.get(query(biz('/inventory/scan'),{code:data.code}));dialog('Artikel gefunden',panel(found.name,el('p',{},`${found.code} · ${found.unit}`),found.price_policy==='dated_catalog'?notice('Datierte Preisquelle mit Gültigkeitstag ausdrücklich wählen.'):found.cost_price_net?el('p',{},'EK netto: '+formatMoney(found.cost_price_net)):null));return undefined;},{submit:'Suchen',key:'scan',description:'Die Suche liest nur Stammdaten. Sie löst keine Entnahme aus.'}));
  if(projectId)content.append(panel('Kommissionierung',canWrite('inventory.write','material')?button('Material reservieren',()=>reservationDialog(projectId,collection(locations),operationalArticles),'small'):null,
    rows(reserved,item=>row(item.article_snapshot?.name||item.article_id,`Reserviert ${formatQuantity(item.quantity)} · Entnommen ${formatQuantity(item.picked_quantity)} · Rest ${formatQuantity(item.remaining_quantity)}`,[badge(item.status),canWrite('inventory.write','material')&&['reserved','partial'].includes(item.status)?button('Entnehmen',()=>dialog('Material entnehmen',form('',[field('quantity','Entnahmemenge','decimal',item.remaining_quantity,{required:true})],(data,key)=>mutation(key,'/inventory/pick',{project_id:projectId,items:[{reservation_id:item.id,quantity:data.quantity}]}),{key:'pick-'+item.id,submit:'Entnahme verbindlich buchen'})),'small'):null]))));
  if(state.features.has('purchasing_receipts')&&state.capabilities.has('business_purchasing')&&has('inventory.read')) {
    const availableArticles=articles.length?articles:operationalArticles.length?operationalArticles:Array.from(new Map(collection(stock).map(item=>[item.article_id,
      {id:item.article_id,name:item.article_name||item.article_code,code:item.article_code,unit:item.unit}])).values());
    content.prepend(await purchasingContent(projectId,collection(locations),availableArticles));
  }
  if(has('finance.read'))content.append(panel('Artikel & Leistungen',rows(articles,item=>row(item.name,`${item.code||'Ohne Artikelnummer'} · ${item.unit} · ${item.price_policy==='dated_catalog'?'Datierte Preisquelle ausdrücklich wählen':`VK ${formatMoney(item.unit_price_net)} · EK ${formatMoney(item.cost_price_net)}`}`,[badge(item.kind),canWrite('finance.write','documents')?button('Bearbeiten',()=>articleDialog(item),'small'):null]))));
  return content;
}
async function purchasingContent(projectId,locations,articles) {
  const orders=collection(await api.get(query(biz('/purchasing/orders'),{project_id:projectId})));
  return panel('Bestellungen',el('p',{class:'muted'},'Bestellvorschläge freigeben, extern erteilte Bestellungen dokumentieren und tatsächliche Lieferungen ins Lager buchen.'),
    canWrite('inventory.write','material')?button('Bestellvorschlag anlegen',()=>purchaseProposalDialog(projectId,articles),'primary'):null,
    rows(orders,order=>row(order.supplier_name,
      `${state.projects.find(project=>project.id===order.project_id)?.name||(order.project_id?'Projekt':'Ohne Projekt')} · ${order.items.length} Position${order.items.length===1?'':'en'}${order.confirmation?' · '+order.confirmation.order_reference:''}`,
      [badge(order.status),button('Bestellung ansehen',()=>action(()=>purchaseOrderDialog(order.id,locations)),'small')]),'Noch keine Bestellvorschläge vorhanden.'));
}
function purchaseProposalDialog(projectId,articles,order=null) {
  const catalog=new PurchaseCatalog({fetcher:path=>api.get(path),enabled:state.features.has('purchasing_catalog'),projectId,
      items:state.features.has('purchasing_catalog')?[]:articles,
      selected:(order?.items||[]).map(item=>({id:item.article_id,name:item.article_name,code:item.article_code,unit:item.unit,catalog_price_required:item.catalog_price_required}))}),
    lines=[],lineArea=el('div',{class:'stack'}),title=order?'Bestellvorschlag bearbeiten':'Bestellvorschlag anlegen';
  const search=el('input',{type:'search','aria-label':'Artikelnummer oder Artikelname',maxLength:200}),
    status=el('p',{class:'muted',role:'status','aria-live':'polite'}),errors=el('div',{}),
    searchButton=button('Einkaufsartikel suchen',()=>loadCatalog(),'small'),
    more=button('Weitere Artikeltreffer',()=>loadCatalog(true),'small');
  let loadVersion=0;
  function refreshChoices() {
    for(const line of lines){const selected=line.article.value;line.article.replaceChildren(el('option',{value:''},'Artikel auswählen'),
      ...catalog.choices(selected).map(item=>el('option',{value:item.id,selected:item.id===selected},`${item.code?item.code+' · ':''}${item.name} (${item.unit})`)));}
  }
  async function loadCatalog(append=false) {
    const version=++loadVersion;errors.replaceChildren();searchButton.disabled=true;more.disabled=true;status.textContent='Einkaufsartikel werden geladen …';
    try{
      if(!await catalog.load(search.value,append)||version!==loadVersion||!lineArea.isConnected)return;
      refreshChoices();status.textContent=`${catalog.items.length} von ${catalog.total} Artikeln geladen. Bereits gewählte Positionen bleiben erhalten.`;
    }catch(error){if(version===loadVersion&&lineArea.isConnected){status.textContent='Artikelsuche nicht aktualisiert. Gewählte Positionen bleiben erhalten.';showError(error,errors);}}
    finally{if(version===loadVersion){searchButton.disabled=false;more.disabled=false;more.hidden=catalog.nextOffset===null;}}
  }
  search.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();loadCatalog();}});
  function addLine(existing=null) {
    const identifier=requestId(),article=el('select',{'aria-label':'Bestellartikel',required:true},
      el('option',{value:''},'Artikel auswählen'),catalog.choices(existing?.article_id).map(item=>el('option',{value:item.id,selected:item.id===existing?.article_id},`${item.code?item.code+' · ':''}${item.name} (${item.unit})`))),
      amount=el('input',{type:'text',inputMode:'decimal','aria-label':'Bestellmenge',required:true,value:existing?.ordered_quantity||'',maxLength:24}),
      node=el('div',{class:'panel soft'},el('div',{class:'form-grid'},
        el('label',{class:'field'},'Artikel',article),el('label',{class:'field'},'Bestellmenge',amount)),
        button('Position entfernen',()=>{node.remove();const index=lines.findIndex(item=>item.id===identifier);if(index>=0)lines.splice(index,1);},'small'));
    const picker=pricePicker({article:()=>catalog.choices(article.value).find(item=>item.id===article.value),priceRole:'purchase_net',initial:existing?.catalog_price_snapshot||null});article.addEventListener('change',()=>picker.reset());node.append(picker);lines.push({id:identifier,article,amount,picker});lineArea.append(node);
  }
  if(order)order.items.forEach(addLine);else addLine();
  const editor=el('div',{class:'stack'},panel('Einkaufsartikel',el('label',{class:'field'},'Artikelnummer oder Artikelname',search),
    el('div',{class:'actions'},searchButton,more),status,errors,
    !catalog.enabled?notice('Dieser Server bietet noch keine vollständige Einkaufssuche. Die Auswahl verwendet den vorhandenen Artikelkatalog bzw. Lagerbestand.'):null),
    lineArea,button('Position hinzufügen',()=>addLine(),'small'));
  const draft=form('',[...(order?[]:[field('project_id','Projekt (optional)','select',projectId,{options:[['','Ohne Projekt'],...options(state.projects)]})]),field('supplier_name','Lieferant','text',order?.supplier_name||'',{required:true,maxLength:300})],(data,key)=>{
    if(!lines.length)throw new Error('Bitte mindestens eine Bestellposition angeben.');
    const items=lines.map(line=>{const quantity=purchaseDecimal(line.amount.value);if(!line.article.value||quantity.scaled<=0n)throw new Error('Bitte Artikel und positive Bestellmenge für jede Position angeben.');const selected=catalog.choices(line.article.value).find(item=>item.id===line.article.value);return {article_id:line.article.value,quantity:quantity.text,...(selected?.price_policy==='dated_catalog'||selected?.catalog_price_required?{catalog_price_selection:line.picker.selection()}: {})};});
    return mutation(key,'/inventory/orders'+(order?'/'+order.id:''),{...data,project_id:data.project_id||null,items,status:'draft',...(order?{project_id:order.project_id,revision:order.source_revision}:{})});
  },{key:'purchase-proposal-'+(order?.id||'new'),extra:editor,submit:'Vorschlag speichern',after:async saved=>{await refresh();await purchaseOrderDialog(saved.id);}});
  draft.controls.get('project_id')?.input.addEventListener('change',event=>{catalog.setProject(event.target.value);loadCatalog();});
  dialog(title,draft,'Der Vorschlag wird intern gespeichert. Er löst keine Bestellung beim Lieferanten aus.');loadCatalog();
}
async function purchaseOrderDialog(id,knownLocations=null) {
  const [order,history,locationResponse]=await Promise.all([api.get(biz('/purchasing/orders/'+id)),api.get(biz('/purchasing/orders/'+id+'/receipts')),
    knownLocations?Promise.resolve({items:knownLocations}):api.get(biz('/inventory/locations'))]);
  const capabilities=await api.get(query(biz('/capabilities'),{project_id:order.project_id})),access=purchaseActions(order,capabilities,state.organization),
    locations=collection(locationResponse),costs=access.costs,controls=[];
  if(capabilities.features?.includes('purchase_changes')&&capabilities.capabilities?.includes('business_purchase_changes'))controls.push(button('Belegte Mengenänderungen und Retouren',()=>action(()=>purchaseChanges.open(id))));
  if(access.edit)
    controls.push(button('Bestellvorschlag bearbeiten',()=>action(async()=>{
      const articles=state.features.has('purchasing_catalog')?[]:state.globalPermissions.has('finance.read')?collection(await api.get(biz('/articles'))):collection(await api.get(biz('/inventory/stock'))).map(item=>
        ({id:item.article_id,name:item.article_name||item.article_code,code:item.article_code,unit:item.unit}));
      purchaseProposalDialog(order.project_id,articles,order);
    }),'small'));
  if(access.approve)
    controls.push(button('Vorschlag freigeben',()=>dialog('Bestellvorschlag freigeben',form('',[],(_,key)=>
      mutation(key,'/inventory/orders/'+id,{project_id:order.project_id,supplier_name:order.supplier_name,revision:order.source_revision,
        status:'approved',items:order.items.map(item=>({article_id:item.article_id,quantity:item.ordered_quantity,...(item.catalog_price_required?{catalog_price_selection:priceSelection(item.catalog_price_snapshot)}:{})}))}),
      {key:'purchase-approve-'+id,submit:'Vorschlag verbindlich freigeben',after:async()=>{await refresh();await purchaseOrderDialog(id);}}),
      'Die Positionen werden intern freigegeben und anschließend nicht mehr verändert. Eine Bestellung beim Lieferanten erfolgt dadurch nicht.'),'primary'));
  if(access.confirm)
    controls.push(button('Extern erteilte Bestellung dokumentieren',()=>purchaseConfirmDialog(order),'primary'));
  if(access.receive)
    controls.push(button('Lieferung erfassen',()=>purchaseReceiptDialog(order,locations),'primary'));
  const body=el('div',{class:'stack'},el('div',{class:'actions'},badge(order.status),controls),
    order.confirmation?notice(`Extern bestellt am ${formatDate(order.confirmation.ordered_on)} · Referenz ${order.confirmation.order_reference}.`):
      el('p',{class:'muted'},'Die Bestellung ist noch nicht als extern erteilt dokumentiert.'),
    panel('Positionen',table(['Pos.','Artikel','Bestellt','Geliefert','Offen',...(costs?['Gewählte datierte Quelle']:[])],order.items.map(item=>[
      String(item.line_index+1),`${item.article_code?item.article_code+' · ':''}${item.article_name}`,formatQuantity(item.ordered_quantity,item.unit),
      formatQuantity(item.received_quantity,item.unit),formatQuantity(item.remaining_quantity,item.unit),...(costs?[item.catalog_price_snapshot?`${item.catalog_price_snapshot.source_name} · ${item.catalog_price_snapshot.price.price_net} EUR / ${item.catalog_price_snapshot.price.price_base_quantity} ${item.unit} · Preisstand ${item.catalog_price_snapshot.effective_on}`:'Undatierter Bestellstand']:[])]))),
    panel('Lieferhistorie',rows(collection(history),receipt=>el('section',{class:'panel soft'},el('h3',{},receipt.receipt_reference),
      el('p',{class:'muted'},`${formatDate(receipt.received_on)} · ${locations.find(location=>location.id===receipt.location_id)?.name||'Lagerort'} · erfasst ${formatDate(receipt.created_at,true)}`),
      table(['Pos.','Artikel','Geliefert',...(costs?['Einstand je Einheit','Kosten netto']:[])],receipt.lines.map(line=>[
        String(line.line_index+1),line.article_name,formatQuantity(line.quantity,line.unit),...(costs?[formatMoney(line.unit_cost_net),formatMoney(line.cost_net)]:[])])),
      assetOrigins.allowed(order.project_id)?button('Original-Lieferschein',()=>action(()=>assetOrigins.document(order.project_id,receipt.id)),'small'):null),
      'Noch keine Lieferung gebucht.')),
    el('p',{class:'caption'},'Diese Ansicht dokumentiert den tatsächlichen Ablauf. Die Anwendung versendet keine Bestellung an den Lieferanten.'));
  dialog('Bestellung · '+order.supplier_name,body,state.projects.find(project=>project.id===order.project_id)?.name||'');
}
function purchaseConfirmDialog(order) {
  dialog('Extern erteilte Bestellung dokumentieren',form('',[
    field('order_reference','Bestellreferenz','text','',{required:true,maxLength:300}),field('ordered_on','Tatsächliches Bestelldatum','date',order.items.some(item=>item.catalog_price_required)?'':dateInput(),{required:true,help:order.items.some(item=>item.catalog_price_snapshot)?'Gewählter Preisstand: '+[...new Set(order.items.map(item=>item.catalog_price_snapshot?.effective_on).filter(Boolean))].join(', '):''}),
    field('confirmation','Ich bestätige, dass diese Bestellung bereits extern erteilt wurde.','checkbox',false,{required:true,wide:true})],
    (data,key)=>mutation(key,'/purchasing/orders/'+order.id+'/confirm',purchaseConfirmationData(order,data)),
    {key:'purchase-confirm-'+order.id,submit:'Bestellung dokumentieren',after:async()=>{await refresh();await purchaseOrderDialog(order.id);}}),
    'Referenz und Datum werden nachvollziehbar festgehalten. Es erfolgt kein Versand.');
}
function purchaseReceiptDialog(order,locations) {
  const remaining=order.items.filter(item=>purchaseDecimal(item.remaining_quantity).scaled>0n),fields=[
    field('receipt_reference','Lieferschein / Belegreferenz','text','',{required:true,maxLength:300}),
    field('received_on','Tatsächliches Lieferdatum','date',dateInput(),{required:true}),
    field('location_id','Ziellager','select','',{required:true,options:[['','Bitte auswählen'],...options(locations.filter(item=>item.active!==false&&item.active!==0))]})];
  for(const item of remaining)fields.push(
    field('quantity_'+item.line_index,`Pos. ${item.line_index+1} · ${item.article_name} – Liefermenge (${item.unit})`,'decimal','',
      {maxLength:24,help:`Bestellt ${formatQuantity(item.ordered_quantity,item.unit)} · bereits geliefert ${formatQuantity(item.received_quantity,item.unit)} · offen ${formatQuantity(item.remaining_quantity,item.unit)}.`}),
    field('cost_'+item.line_index,`Pos. ${item.line_index+1} · Einstand netto EUR / ${item.unit}`,'decimal','',
      {maxLength:24,help:'Tatsächlichen Einstandspreis je Einheit bestätigen; 0 nur bei einem tatsächlichen Nullpreis.'}));
  const editor=form('',fields,(data,key)=>mutation(key,'/purchasing/orders/'+order.id+'/receipts',purchaseReceiptData(order,data)),
    {key:'purchase-receipt-'+order.id,submit:'Wareneingang verbindlich buchen',after:async()=>{await refresh();await purchaseOrderDialog(order.id);}});
  editor.prepend(button('Restmengen übernehmen',()=>remaining.forEach(item=>{editor.controls.get('quantity_'+item.line_index).input.value=item.remaining_quantity;}),'small'));
  dialog('Lieferung erfassen',editor,'Nur tatsächlich erhaltene Mengen eintragen. Nicht gelieferte Positionen leer lassen. Die Buchung erhöht den Lagerbestand; Teilmengen bleiben offen.');
}
function articleDialog(item=null) {
  dialog(item?'Artikel bearbeiten':'Artikel / Leistung',form('',[field('code','Artikelnummer','text',item?.code||''),field('name','Bezeichnung','text',item?.name||'',{required:true}),field('kind','Art','select',item?.kind||'material',{options:['material','labor','service','machine'].map(kind=>[kind,LABELS[kind]])}),field('unit','Einheit','text',item?.unit||'Stk.',{required:true}),field('unit_price_net','Verkauf netto EUR','decimal',item?.unit_price_net||'0.00',{required:true}),field('cost_price_net','Einstand netto EUR','decimal',item?.cost_price_net||'0.00',{required:true}),field('tax_rate','MwSt. %','select',item?.tax_rate||'19',{options:[['19','19 %'],['7','7 %'],['0','0 %']]}),field('active','Aktiv','checkbox',item?.active??true)].filter(value=>item?.price_policy!=='dated_catalog'||!['unit_price_net','cost_price_net'].includes(value.name)),
    (data,key)=>mutation(key,'/articles'+(item?'/'+item.id:''),{...data,currency:'EUR',tax_category:data.tax_rate==='0'?'Z':'S',...(item?{revision:item.revision}:{})}),{key:'article-'+(item?.id||'new')}));
}
const stockReturns=stockReturnsUi({api,el,button,field,form,panel,table,notice,dialog,action,mutation,closeModal,refresh,formatDate,formatMoney,stamp:()=>`${api.generation}/${state.render}/${dialogGeneration}`});
function stockMovementDialog(locations,articles,projectId) {
  const fields=[field('kind','Bewegung','select','receive',{options:[['receive','Zugang'],['issue','Entnahme'],['transfer','Umbuchung']]}),field('article_id','Artikel','select','',{options:options(articles),required:true}),field('quantity','Menge','decimal','1',{required:true}),...(canWrite('finance.write','material')?[field('unit_cost_net','Bestätigter Einstand netto EUR / Einheit','decimal','',{help:'Für datierte Katalogartikel bei Zugang erforderlich. Ein tatsächlicher Nullpreis muss ausdrücklich als 0 eingegeben werden.'})]:[]),field('from_location_id','Quelllager','select','',{options:[['','Kein Quelllager'],...options(locations)]}),field('to_location_id','Ziellager','select','',{options:[['','Kein Ziellager'],...options(locations)]}),field('project_id','Projekt für Entnahme','select',projectId,{options:[['','Kein Projekt'],...options(state.projects)]}),field('note','Buchungsnotiz','textarea')];
  dialog('Lagerbewegung',form('',fields,(data,key)=>{if(data.kind!=='receive')delete data.unit_cost_net;return mutation(key,'/inventory/movements',data);},{key:'stock-move',submit:'Bewegung buchen'}),'Zugang: nur Ziellager. Entnahme: nur Quelllager und Projekt. Umbuchung: Quell- und Ziellager. Historische Einstandskosten entstehen aus dem Journal.');
}
function reservationDialog(projectId,locations,articles) {
  dialog('Material reservieren',form('',[field('article_id','Artikel','select','',{options:options(articles),required:true}),field('location_id','Lagerort','select','',{options:options(locations),required:true}),field('quantity','Menge','decimal','1',{required:true})],
    (data,key)=>mutation(key,'/inventory/reservations',{...data,project_id:projectId}),{key:'reserve-'+projectId}),'Reservierungen werden gegen den freien Bestand geprüft.');
}
const accountingEuer=createAccountingEuer({api,biz,el,button,panel,row,rows,notice,table,form,dialog,closeModal,formatMoney,formatDate,mutation,action,refresh,download,jsonDownload,updatePending,organization:()=>state.organization,context:()=>state.render,privateContext:()=>`${api.generation}/${state.render}/${dialogGeneration}`,yearValuesAvailable:()=>yearValuesWorkspace.available(),openYearValues:year=>year?yearValuesWorkspace.detail(year):yearValuesWorkspace.open(),yearPackageAvailable:()=>yearPackageWorkspace.available(),openYearPackage:value=>yearPackageWorkspace.open(value),openEvent:accountingEventDialog,openProfile:accountingProfileDialog,openItemsAvailable:()=>openItemWorkspace.available(),openOpenItems:entity=>entity?openItemWorkspace.detail(entity):openItemWorkspace.open(),historicalAvailable:()=>historicalWorkspace.available(),openHistoricalAssets:(identity)=>identity?historicalWorkspace.detail(identity):historicalWorkspace.open(),openingAvailable:()=>openingWorkspace.available(),openOpenings:()=>openingWorkspace.open(),openCash:tab=>{closeModal();state.accounting.tab=tab;refresh();},textDownload:(value,filename,type)=>{const link=el('a',{href:objectUrl(new Blob([value],{type})),download:filename});document.body.append(link);link.click();link.remove();},onDenied:()=>{closeModal();main?.querySelectorAll('.accounting-euer').forEach(node=>node.replaceChildren(notice('Die EÜR-Quellen sind aktuell nicht freigegeben. Offene Buchungsaufträge bleiben unverändert erhalten.','warn')));}});
const projectEconomics=createProjectEconomics({api,biz,query,el,button,panel,row,rows,notice,empty,form,field,dialog,closeModal,table,formatMoney,formatDate,mutation,action,refresh,download,dateInput,bytesBase64,duration,canWrite,confirmDialog,documentDetail,projectId:()=>state.projectId,organization:()=>state.organization,actorId:()=>state.user?.id,onDenied:()=>{closeModal();main?.querySelectorAll('.project-economics').forEach(node=>node.replaceChildren(notice('Die Projektwirtschaftlichkeit ist aktuell nicht freigegeben. Offene Anfragen bleiben unverändert erhalten.','warn')));}});
async function costsPanel(projectId) {
  if(state.features.has('project_economics'))return projectEconomics.render(projectId);
  return legacyCostsPanel(projectId);
}
async function legacyCostsPanel(projectId) {
  const [costs,changes]=await Promise.all([api.get(biz(`/projects/${projectId}/costs`)),api.get(biz(`/projects/${projectId}/changes`))]);
  return el('div',{class:'stack'},costs.costs_complete===false?notice(`Die Istkosten sind unvollständig: ${costs.missing_rates_count} genehmigte Zeitnachweise haben keinen bestätigten Kostensatz. Die bekannte Teilsumme ist kein vollständiger Gewinn- oder Budgetnachweis.`,'warn'):null,
    el('div',{class:'grid'},panel('Gespeichertes Budget',el('div',{class:'metric'},formatMoney(costs.budget_net)),el('p',{class:'metric-sub'},'Baseline · Revision '+costs.budget_revision)),
    panel(costs.costs_complete===false?'Bekannte Istkosten':'Gebuchte Istkosten',el('div',{class:'metric'},formatMoney(costs.actual_net)),el('p',{class:'metric-sub'},'Materialbewegungen + genehmigte Zeiten')),panel('Verfügbares Budget',el('div',{class:'metric'},formatMoney(costs.remaining_net)),el('p',{class:'metric-sub'},'Inklusive freigegebener Nachträge'))),
    panel('Nachweis',el('p',{},'Material netto: '+formatMoney(costs.material_actual_net)),el('p',{},'Genehmigte Zeitkosten: '+formatMoney(costs.labor_actual_net)),el('p',{class:'caption'},'Zeitkosten verwenden den historischen Satz des Zeiteintrags. Unbestätigte Zeiten und manuelle Terminlängen zählen nicht als Istkosten.'),
      table(['Arbeitstag','Genehmigte Dauer','Kosten netto'],costs.approved_times.map(item=>[formatDate(item.work_date),duration(item.net_seconds),formatMoney((item.cost_minor/100).toFixed(2))]))),
    panel('Nachträge',rows(collection(changes),item=>row(item.title,formatMoney(item.amount_net),[badge(item.approved?'Freigegeben':'Vorschlag'),!item.approved&&canWrite('finance.approve','material')?button('Nachtrag freigeben',()=>confirmDialog('Nachtrag freigeben','Dieser Vorschlag erhöht das Projektbudget um '+formatMoney(item.amount_net)+'. Die ursprüngliche Fassung bleibt nachvollziehbar. Es wird keine Nachricht versendet.',async()=>{await mutation('approve-change-'+item.id,`/projects/${projectId}/changes/${item.id}/approve`,{revision:item.revision});refresh();}),'small'):null]))),
    canWrite('finance.write','material')?form('Budget festlegen',[field('material_net','Material netto EUR','decimal','0.00',{required:true}),field('labor_net','Lohn netto EUR','decimal','0.00',{required:true}),field('machine_net','Maschinen netto EUR','decimal','0.00',{required:true}),field('other_net','Sonstige Kosten netto EUR','decimal','0.00',{required:true})],(data,key)=>mutation(key,'/budgets',{...data,project_id:projectId,...(costs.budget_revision?{revision:costs.budget_revision}:{})}),{key:'budget-'+projectId,submit:'Neue Budgetfassung speichern'}):null,
    canWrite('finance.write','material')?form('Nachtrag erfassen',[field('title','Nachtrag','text','',{required:true}),field('amount_net','Zusätzlicher Budgetbetrag netto EUR','decimal','',{required:true}),...(canWrite('finance.approve','material')?[field('approved','Nachtrag ausdrücklich freigeben','checkbox',false)]:[])],(data,key)=>mutation(key,`/projects/${projectId}/changes`,data),{key:'change-'+projectId}):null);
}

async function documentationPanel(projectId) {
  const [media,diary,defects,measurements,checklists,runs]=await Promise.all(['media','diary','defects','measurements','checklists','checklist-runs'].map(resource=>api.get(query(biz('/'+resource),{project_id:projectId}))));
  const allMedia=collection(media).slice().reverse(),page=Math.min(state.galleryPage||0,Math.max(0,Math.ceil(allMedia.length/12)-1));
  state.galleryPage=page;
  const shownMedia=allMedia.slice(page*12,page*12+12);
  const gallery=el('div',{class:'gallery'});
  for(const item of shownMedia) {
    const card=el('article',{class:'photo-card'});
    if(item.status==='ready'&&item.media_type.startsWith('image/')) {
      try {
        const blob=await api.binary(biz(`/media/${item.id}/content`));const thumbnail=await photoThumbnail(blob);
        card.append(el('img',{src:objectUrl(thumbnail),alt:item.caption||item.filename,loading:'lazy'}));
      }catch(error){
        if(error instanceof StaleSession||[401,403,404].includes(error.status))throw error;
        card.append(notice('Galerievorschau nicht verfügbar. Das Original separat prüfen.','warn'));
      }
    }
    card.append(el('div',{class:'photo-info'},el('h3',{},item.caption||item.filename),el('p',{},formatDate(item.captured_at||item.created_at,true)),el('div',{class:'actions'},badge(item.status),
      item.status==='ready'?button('Original',()=>action(()=>download(biz(`/media/${item.id}/content`),item.filename)),'small'):null,
      item.status==='ready'&&item.media_type.startsWith('image/')&&has('documents.write')?button('Markieren',()=>action(()=>annotateDialog(item)),'small'):null)));gallery.append(card);
  }
  const previous=button('Vorherige Fotos',()=>{state.galleryPage=page-1;refresh();},'small');previous.disabled=page===0;
  const next=button('Weitere Fotos',()=>{state.galleryPage=page+1;refresh();},'small');next.disabled=(page+1)*12>=allMedia.length;
  const content=el('div',{class:'stack'},panel('Fotos & Originalunterlagen',has('documents.write')?button('Foto aufnehmen / hochladen',()=>photoDialog(projectId),'primary'):null,
    el('p',{class:'caption'},'Verkleinerte Galerievorschauen · Die unveränderten Originale bleiben separat abrufbar.'),allMedia.length?gallery:empty('Noch keine Baustellenfotos vorhanden.'),
    allMedia.length>12?el('div',{class:'actions'},previous,el('span',{class:'caption'},`Seite ${page+1} von ${Math.ceil(allMedia.length/12)}`),next):null),
    panel('Bautagebuch',has('documents.write')?button('Tagesbericht hinzufügen',()=>diaryDialog(projectId),'small'):null,rows(collection(diary),item=>row(item.title,`${formatDate(item.entry_date)} · ${item.crew_count} Personen · ${item.imported_net_seconds?duration(item.imported_net_seconds):'Keine übernommenen Zeiten'}`,[badge(item.status)],item.work))),
    panel('Mängel',has('documents.write')?button('Mangel aufnehmen',()=>defectDialog(projectId),'small'):null,rows(collection(defects),item=>row(item.title,`${item.location||''}${item.due_date?' · Frist '+formatDate(item.due_date):''}`,[badge(item.status),has('documents.write')?button('Bearbeiten',()=>defectDialog(projectId,item),'small'):null],item.details))),
    panel('Aufmaß',has('documents.write')?button('Aufmaß erfassen',()=>measurementDialog(projectId),'small'):null,rows(collection(measurements),item=>row(item.title,(item.lines||[]).map(line=>line.description+': '+formatQuantity(line.quantity,line.unit)).join(' · '),[badge(item.status),item.status==='signed'?button('PDF',()=>action(()=>download(biz(`/measurements/${item.id}/pdf`),'Aufmass.pdf')),'small'):has('documents.write')?button('Prüfen & unterzeichnen',()=>signatureDialog(item,'measurements'),'small'):null]))),
    panel('Checklisten',has('documents.write')?button('Prüfliste anlegen',()=>checklistDialog(projectId),'small'):null,rows(collection(checklists),item=>row(item.title,`${item.items.length} Prüfpunkte · Vorlage ${item.revision}`,[has('documents.write')?button('Prüfung starten',()=>action(async()=>{const run=await mutation('run-'+item.id,'/checklists/'+item.id+'/start',{project_id:projectId});checklistRunDialog(run);}), 'small'):null])),
      rows(collection(runs),item=>row(item.title,formatDate(item.created_at,true),[badge(item.status),button('Prüfung öffnen',()=>checklistRunDialog(item),'small')]))),
    button('Dokumentation exportieren',()=>action(async()=>jsonDownload(await api.get(query(biz('/documentation/export'),{project_id:projectId})),'Projektdokumentation.json')),'small'));
  return content;
}
const photoUploads=new Map();
async function photoThumbnail(original) {
  const bitmap=await createImageBitmap(original);
  try {
    const ratio=Math.min(1,600/Math.max(bitmap.width,bitmap.height)),canvas=el('canvas',{width:Math.max(1,Math.round(bitmap.width*ratio)),height:Math.max(1,Math.round(bitmap.height*ratio))});
    const context=canvas.getContext('2d',{alpha:false});context.fillStyle='#ffffff';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(bitmap,0,0,canvas.width,canvas.height);
    return await new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Galerievorschau konnte nicht erzeugt werden.')),'image/jpeg',0.8));
  } finally { bitmap.close(); }
}
function bytesBase64(bytes) { let value='';for(let offset=0;offset<bytes.length;offset+=16384)value+=String.fromCharCode(...bytes.subarray(offset,offset+16384));return btoa(value); }
function photoDialog(projectId) {
  const file=el('input',{type:'file',accept:'image/jpeg,image/png,image/webp',capture:'environment','aria-label':'Baustellenfoto auswählen',required:true});
  const progress=el('progress',{max:1,value:0,'aria-label':'Uploadfortschritt'});
  const editor=form('',[field('caption','Bildnotiz','textarea','',{maxLength:2000})],async(data)=> {
    const original=file.files?.[0];if(!original)throw new Error('Bitte ein Foto auswählen.');
    if(original.size<1||original.size>20*1024*1024)throw new Error('Fotos dürfen höchstens 20 MiB groß sein.');
    if(!['image/jpeg','image/png','image/webp'].includes(original.type))throw new Error('JPEG, PNG oder WebP auswählen. Das Original wird unverändert gespeichert.');
    const bytes=new Uint8Array(await original.arrayBuffer()),digest=await crypto.subtle.digest('SHA-256',bytes),sha=Array.from(new Uint8Array(digest),value=>value.toString(16).padStart(2,'0')).join('');
    const key=projectId+':'+sha+':'+original.name;
    let record=photoUploads.get(key);
    if(record&&record.caption!==(data.caption||''))throw new Error('Den begonnenen Upload zuerst mit unveränderter Bildnotiz abschließen. Danach lässt sich die Notiz bearbeiten.');
    if(!record) {record=await mutation('photo-'+key,'/media',{project_id:projectId,filename:original.name,media_type:original.type,size:bytes.length,sha256:sha,caption:data.caption||'',purpose:'site_photo',classification:'operational'});photoUploads.set(key,record);}
    record=await api.get(biz('/media/'+record.id));const chunks=new Set(record.uploaded_chunks);progress.max=bytes.length;
    for(let index=0,offset=0;offset<bytes.length;index++,offset+=record.chunk_size) {
      const part=bytes.subarray(offset,Math.min(offset+record.chunk_size,bytes.length));
      if(!chunks.has(index))await api.post(biz(`/media/${record.id}/chunks/${index}`),{content_base64:bytesBase64(part)});
      progress.value=offset+part.length;
    }
    const completed=await mutation('complete-photo-'+record.id,`/media/${record.id}/complete`,{});photoUploads.delete(key);return completed;
  },{key:'photo-upload-'+projectId,submit:'Original sicher hochladen',after:()=>{state.galleryPage=0;return refresh();},extra:el('div',{class:'stack'},file,progress),description:'Original, Bildnotiz und Markierungen bleiben getrennt. Der Browser benötigt eine aktive Verbindung; unklare Antworten mit unverändertem Foto erneut versuchen.'});
  dialog('Baustellenfoto',editor);
}
function diaryDialog(projectId) {
  dialog('Bautagesbericht',form('',[field('title','Titel','text','Tagesbericht',{required:true}),field('entry_date','Arbeitstag','date',dateInput(),{required:true}),field('weather','Wetter'),field('crew_count','Personenzahl','integer',1,{min:0,max:1000}),field('work','Ausgeführte Arbeiten','textarea','',{required:true}),field('issues','Probleme / Hinweise','textarea')],(data,key)=>mutation(key,'/diary',{...data,project_id:projectId}),{key:'diary-'+projectId}));
}
function defectDialog(projectId,item=null) {
  dialog(item?'Mangel bearbeiten':'Mangel erfassen',form('',[field('title','Mangel','text',item?.title||'',{required:true}),field('location','Ort / Bauteil','text',item?.location||''),field('due_date','Frist','date',item?.due_date||''),field('details','Beschreibung','textarea',item?.details||''),field('status','Status','select',item?.status||'open',{options:[['open','Offen'],['in_progress','In Bearbeitung'],['resolved','Behoben'],['accepted','Abgenommen']]}),field('resolution','Abschlussnachweis','textarea',item?.resolution||'')],
    (data,key)=>mutation(key,'/defects'+(item?'/'+item.id:''),{...data,project_id:projectId,...(item?{revision:item.revision}:{})}),{key:'defect-'+(item?.id||'new')}));
}
function measurementDialog(projectId) {
  dialog('Metrisches Aufmaß',form('',[field('title','Aufmaßbezeichnung','text','',{required:true}),field('description','Position / Bauteil','text','',{required:true}),field('shape','Berechnung','select','area',{options:[['length','Länge'],['area','Rechteckfläche'],['volume','Quader-Volumen']]}),field('length','Länge in Metern','decimal','',{required:true}),field('width','Breite in Metern','decimal'),field('height','Höhe in Metern','decimal')],
    (data,key)=>{const variables={length:{value:data.length,unit:'m'}};if(data.shape!=='length'){if(!data.width)throw new Error('Breite eingeben.');variables.width={value:data.width,unit:'m'};}if(data.shape==='volume'){if(!data.height)throw new Error('Höhe eingeben.');variables.height={value:data.height,unit:'m'};}
      return mutation(key,'/measurements',{project_id:projectId,title:data.title,lines:[{description:data.description,unit:({length:'m',area:'m2',volume:'m3'})[data.shape],formula:({length:'length',area:'length * width',volume:'length * width * height'})[data.shape],variables}]});},
    {key:'measurement-'+projectId,description:'Bestätigte metrische Werte manuell erfassen. Aus einem Foto oder maßstabslosen Plan werden keine Maße abgeleitet.'}));
}
function drawingCanvas({height=180,background=null,annotations=[]}={}) {
  const canvas=el('canvas',{class:background?'':'signature',tabIndex:0,'aria-label':background?'Bildmarkierungen':'Unterschriftsfläche'}),strokes=[],marks=annotations.map(item=>structuredClone(item));let current=null,mode='signature',textValue='';
  const context=canvas.getContext('2d');
  function redraw() {
    const rect=canvas.getBoundingClientRect(),ratio=devicePixelRatio||1;canvas.width=Math.max(1,Math.round(rect.width*ratio));canvas.height=Math.max(1,Math.round((background?rect.height:height)*ratio));context.setTransform(ratio,0,0,ratio,0,0);context.clearRect(0,0,rect.width,rect.height);context.lineWidth=2;context.lineCap='round';context.strokeStyle='#245ec8';
    const line=points=>{context.beginPath();points.forEach((point,index)=>context[index?'lineTo':'moveTo'](point[0]*rect.width,point[1]*rect.height));context.stroke();};
    strokes.forEach(line);if(current&&mode==='signature')line(current);
    [...marks,...(current&&mode!=='signature'?[{kind:mode,points:[current[0],current.at(-1)]}]:[])].forEach(mark=>{context.strokeStyle=mark.color||'#ff3333';context.fillStyle=mark.color||'#ff3333';if(mark.kind==='text'){context.font='16px system-ui';context.fillText(mark.text,mark.point[0]*rect.width,mark.point[1]*rect.height);}else if(mark.kind==='rectangle'){const[a,b]=mark.points;context.strokeRect(a[0]*rect.width,a[1]*rect.height,(b[0]-a[0])*rect.width,(b[1]-a[1])*rect.height);}else line(mark.points);});
  }
  const point=event=>{const bounds=canvas.getBoundingClientRect();return[Math.min(1,Math.max(0,(event.clientX-bounds.left)/bounds.width)),Math.min(1,Math.max(0,(event.clientY-bounds.top)/bounds.height))];};
  canvas.addEventListener('pointerdown',event=>{event.preventDefault();canvas.setPointerCapture(event.pointerId);const p=point(event);if(mode==='text'){if(textValue.trim())marks.push({kind:'text',point:p,text:textValue.trim(),color:'#ff3333'});redraw();return;}current=[p,p];redraw();});
  canvas.addEventListener('pointermove',event=>{if(!current)return;event.preventDefault();const p=point(event);if(mode==='signature'){if(current.length<2000)current.push(p);}else current=[current[0],p];redraw();});
  canvas.addEventListener('pointerup',()=>{if(!current)return;if(mode==='signature')strokes.push(current);else marks.push({kind:mode,points:[current[0],current.at(-1)],color:'#ff3333'});current=null;redraw();});
  canvas.addEventListener('pointercancel',()=>{current=null;redraw();});
  const observer=new ResizeObserver(()=>redraw());observer.observe(canvas);canvas.disconnect=()=>observer.disconnect();canvas.strokes=strokes;canvas.marks=marks;canvas.clear=()=>{strokes.splice(0);marks.splice(0);redraw();};canvas.mode=(value,text='')=>{mode=value;textValue=text;};return canvas;
}
function signatureDialog(item,resource) {
  const canvas=drawingCanvas(),snapshot=resource==='measurements'?table(['Position','Formel','Ergebnis'],item.lines.map(line=>[line.description,line.formula,formatQuantity(line.quantity,line.unit)])):panel('Prüfliste',rows(item.checklist?.items||[],line=>row(line.label,item.checklist.answers[line.key]===true?'Ja':item.checklist.answers[line.key]===false?'Nein':String(item.checklist.answers[line.key]))));
  const editor=form('',[field('signer','Name der unterzeichnenden Person','text','',{required:true,maxLength:200}),field('confirmed','Ich bestätige die dargestellte Fassung','checkbox',false,{required:true})],(data,key)=>{if(!data.confirmed||!canvas.strokes.length)throw new Error('Fassung bestätigen und auf der Zeichenfläche unterzeichnen.');return mutation(key,`/${resource}/${item.id}/sign`,{revision:item.revision,expected_hash:item.content_hash,signer:data.signer,strokes:canvas.strokes});},
    {key:'sign-'+item.id,submit:'Fassung unterzeichnen',extra:el('div',{class:'stack'},snapshot,el('p',{class:'caption'},'Inhalt SHA-256: '+item.content_hash),canvas,button('Unterschrift löschen',()=>canvas.clear(),'small'))});
  dialog('Fassung prüfen & unterzeichnen',editor,'Name, Zeichnung und UTC-Zeit werden mit dieser Fassung als unveränderliches PDF gespeichert. Dies ist keine qualifizierte elektronische Signatur.');
}
async function annotateDialog(item) {
  const blob=await api.binary(biz(`/media/${item.id}/content`)),image=el('img',{src:objectUrl(blob),alt:item.caption||item.filename}),canvas=drawingCanvas({background:true,annotations:item.annotations||[]});
  canvas.mode('line');const stage=el('div',{class:'annotation-stage'},image,canvas),label=el('input',{type:'text',placeholder:'Text für die Markierung','aria-label':'Markierungstext',maxLength:500});
  const tool=select('Werkzeug',[['line','Linie'],['rectangle','Rechteck'],['text','Text']],'line',value=>canvas.mode(value,label.value));label.addEventListener('input',()=>canvas.mode(tool.querySelector('select').value,label.value));
  dialog('Bild separat markieren',form('',[field('caption','Bildnotiz','textarea',item.caption||'',{maxLength:2000})],(data,key)=>mutation(key,`/media/${item.id}`,{...data,revision:item.revision,annotations:canvas.marks}),{key:'annotate-'+item.id,extra:el('div',{class:'stack'},tool,label,stage,button('Markierungen löschen',()=>canvas.clear(),'small'))}),'Das Original bleibt unverändert. Die Markierungsebene wird getrennt versioniert.');
}
function checklistDialog(projectId) {
  dialog('Prüflistenvorlage',form('',[field('title','Checkliste','text','',{required:true}),field('items','Prüfpunkte – ein Punkt pro Zeile','textarea','',{required:true,maxLength:10000,help:'In dieser einfachen Vorlage sind alle Punkte verpflichtende Ja/Nein-Prüfungen.'})],
    (data,key)=>mutation(key,'/checklists',{project_id:projectId,title:data.title,items:data.items.split('\n').map(line=>line.trim()).filter(Boolean).map((label,index)=>({key:'check_'+index,label,required:true,type:'boolean'}))}),{key:'checklist-'+projectId}));
}
function checklistRunDialog(run) {
  if(run.status==='completed') {action(async()=>{const report=await api.get(biz('/service-reports/'+run.report_id));if(report.status==='signed')await download(biz('/service-reports/'+report.id+'/pdf'),'Servicebericht.pdf');else signatureDialog(report,'service-reports');});return;}
  let savedAnswers=null;
  const fields=run.items.map(item=>field(item.key,item.label,item.type==='boolean'?'select':item.type==='number'?'decimal':'text',run.answers[item.key]===undefined?'':String(run.answers[item.key]),{required:item.required,...(item.type==='boolean'?{options:[['','Bitte prüfen'],['true','Ja'],['false','Nein']]}:{})}));
  dialog(run.title,form('',fields,async(data,key)=>{const answers={};run.items.forEach(item=>{if(data[item.key]!==undefined)answers[item.key]=item.type==='boolean'?data[item.key]==='true':data[item.key];});
    const fingerprint=JSON.stringify(answers);
    if(savedAnswers&&savedAnswers!==fingerprint)throw new Error('Zuerst den begonnenen Berichtsabschluss mit unveränderten Antworten wiederholen.');
    if(!savedAnswers){await mutation(key,'/checklists/'+run.id+'/answers',{revision:run.revision,answers});savedAnswers=fingerprint;}
    const report=await mutation('check-report-'+run.id,'/checklists/'+run.id+'/report',{});signatureDialog(report,'service-reports');return undefined;},
    {key:'answers-'+run.id,submit:'Prüfergebnis in Servicebericht übernehmen'}),'Diese Prüfung verwendet die eingefrorene Vorlagenfassung '+run.template_revision+'.');
}

const timeTracking=timeTrackingUi({api,biz,query,el,button,panel,notice,table,field,form,dialog,action,mutation,formatDate,duration,
  allowed:()=>state.section==='personnel'&&(has('time.own')||has('personnel.read')),
  writable:()=>canWrite('time.approve','personnel'),userId:()=>state.user?.id,
  projectName:id=>state.projects.find(project=>project.id===id)?.name||'Zugeordnetes Projekt',
  stamp:()=>`${api.generation}/${state.render}/${dialogGeneration}`});

async function personnelView() {
  const employees=collection(await api.get(biz('/employees'))),own=employees.find(employee=>employee.user_id===state.user.id);
  const selected=employees.find(employee=>employee.id===state.employeeId)||own||(has('personnel.read')?employees[0]:null);
  const from=new Date();from.setDate(1);const to=new Date();
  let entries=[],summary=null;
  if(selected) {
    const filters={employee_id:selected.id,from:dateInput(from),to:dateInput(to)};
    [entries,summary]=await Promise.all([api.get(query(biz('/time/entries'),filters)).then(collection),api.get(query(biz('/time/summary'),filters))]);
  }
  const current=entries.find(item=>['working','paused'].includes(item.status)&&item.employee_id===own?.id);
  const buttons=[];if(own&&canWrite('time.own','personnel'))buttons.push(button(current?'Laufende Zeit öffnen':'Zeit starten',()=>timeDialog(current),'primary'));
  if(canWrite('personnel.manage','personnel'))buttons.push(button('Mitarbeiterprofil anlegen',()=>action(()=>employeeDialog()),'small'));
  if(selected&&personnelWorkflow.allowed(selected))buttons.push(button('Personalakte, Reisen und Lohnvorbereitung',()=>action(()=>personnelWorkflow.open(selected)),'primary'));
  const content=el('div',{class:'stack'},heading('Personal & Zeiten','Eigene Zeiten und bestätigte Tagesnachweise. Keine Hintergrundortung.',buttons),
    selected?select('Mitarbeiter',options(has('personnel.read')?employees:employees.filter(employee=>employee.user_id===state.user.id)),selected.id,value=>{state.employeeId=value;refresh();}):notice('Für diesen Zugang ist noch kein Mitarbeiterprofil eingerichtet. Die Geschäftsführung kann es mit dem vorhandenen Benutzer verknüpfen.','warn'));
  if(summary)content.append(el('div',{class:'grid'},panel('Nettoarbeitszeit im Monat',el('div',{class:'metric'},duration(summary.net_seconds)),el('p',{class:'metric-sub'},formatDate(dateInput(from))+' bis '+formatDate(dateInput(to))+' · Nach Pausen und Korrekturen.'))),
    panel('Arbeitszeiteinträge',rows(entries,item=>row(state.projects.find(project=>project.id===item.project_id)?.name||'Projekt',`${formatDate(item.started_at,true)}${item.ended_at?' – '+formatDate(item.ended_at,true):''}`,[badge(item.status),el('span',{class:'caption'},duration(item.worked_seconds)),button('Zeiteintrag prüfen',()=>action(()=>timeTracking.open(item)),'small'),canWrite('time.own','personnel')&&item.employee_id===own?.id&&['working','paused'].includes(item.status)?button('Fortsetzen / beenden',()=>timeDialog(item),'small'):null]))),
    panel('Tagesfreigaben',rows(summary.days||[],day=>row(formatDate(day.date),`Netto ${duration(day.net_seconds)} · Pause ${duration(day.break_seconds||0)}`,[badge(day.status),canWrite('time.approve','personnel')&&day.status!=='approved'?button('Tag freigeben',()=>confirmDialog('Arbeitstag freigeben','Die geprüfte Zeit wird eingefroren. Optionale Ortsdaten werden aus den aktiven Daten und Wiederholungsquittungen entfernt.',async()=>{await mutation('approve-day-'+selected.id+'-'+day.date,`/time/days/${day.date}/approve`,{employee_id:selected.id,revision:day.revision});refresh();}),'small'):null]))));
  if(has('personnel.read'))content.append(panel('Mitarbeiterprofile',rows(employees,employee=>row(employee.name,`${employee.weekly_minutes??'—'} Sollminuten / Woche`,[badge(employee.active?'Aktiv':'Inaktiv'),canWrite('personnel.manage','personnel')?button('Bearbeiten',()=>action(()=>employeeDialog(employee)),'small'):null]))));
  return content;
}
function timeDialog(entry=null) {
  const actions=entry?entry.status==='paused'?[['resume','Arbeit fortsetzen'],['stop','Zeit beenden']]:[['pause','Pause beginnen'],['stop','Zeit beenden']]:[['start','Arbeit beginnen']];
  dialog('Zeiterfassung',form('',[...(!entry?[projectField()]:[]),field('action','Aktion','select',actions[0][0],{options:actions,required:true}),field('occurred_at','Zeitpunkt (Gerätezeit)','datetime-local',localDateTime(),{required:true})],
    (data,key)=>mutation(key,'/time/events',{...data,project_id:entry?.project_id||data.project_id,entry_id:entry?.id||state.newTimeEntryId||(state.newTimeEntryId=requestId()),device_id:entry?.events?.at(-1)?.device_id||state.deviceId,sequence:(entry?.last_sequence||0)+1,revision:entry?.revision||0}),
    {key:'time-event-'+(entry?.id||'start')+'-'+(entry?.revision||0),submit:'Zeitereignis speichern',after:()=>{state.newTimeEntryId=null;refresh();}}),'Der Browser speichert keine dauerhafte Offlinewarteschlange. Bei unklarer Antwort dieselbe Eingabe in diesem Fenster erneut senden.');
}
async function employeeDialog(employee=null) {
  const users=collection(await api.get('/users'));
  dialog(employee?'Mitarbeiterprofil ändern':'Mitarbeiterprofil anlegen',form('',[field('user_id','Benutzerkonto','select',employee?.user_id||'',{options:options(users,item=>item.email),required:true}),field('name','Anzeigename','text',employee?.name||'',{required:true}),field('weekly_minutes','Wöchentliche Sollminuten','integer',employee?.weekly_minutes??2400,{required:true,min:0,max:10080}),field('hourly_cost_minor','Historischer Kostensatz in Cent / Stunde','integer',employee?.hourly_cost_minor??0,{required:true,min:0,help:'3500 entspricht 35,00 EUR. Bestehende Zeiteinträge behalten ihren ursprünglichen Satz.'}),field('active','Aktiv','checkbox',employee?.active??true)],
    (data,key)=>mutation(key,'/employees'+(employee?'/'+employee.id:''),{...data,...(employee?{revision:employee.revision}:{})}),{key:'employee-'+(employee?.id||'new')}));
}

const maintenanceContracts=maintenanceContractsUi({api,field,form,dialog,el,notice,button,action,closeModal,refresh,updatePending,
  today:dateInput,stamp:()=>`${api.generation}/${state.render}/${dialogGeneration}`,
  available:project=>state.section==='projects'&&state.tab==='maintenance'&&state.projectId===project&&has('documents.read')&&has('projects.manage')&&!state.readonly&&document.visibilityState!=='hidden'});
async function maintenancePanel(projectId) {
  const [assets,contracts,visits,reports]=await Promise.all(['assets','maintenance/contracts','maintenance/history','service-reports'].map(path=>api.get(query(biz('/'+path),{project_id:projectId})).then(collection)));
  return el('div',{class:'stack'},panel('Anlagen',has('documents.write')?button('Anlage erfassen',()=>assetDialog(projectId),'primary'):null,assetOrigins.allowed(projectId)?button('Lieferungen und Geräte',()=>action(()=>assetOrigins.sources(projectId)),'primary'):null,rows(assets,item=>row(item.name,`${item.serial_number||'Seriennummer offen'} · ${item.location||'Standort offen'}`,[state.features.has('custom_fields')?button('Zusatzfelder',()=>action(()=>customFields.open('asset',item.id)),'small'):null,has('documents.write')?button('Bearbeiten',()=>assetDialog(projectId,item),'small'):null,assetOrigins.allowed(projectId)?button('Lieferherkunft',()=>action(()=>assetOrigins.origin(projectId,item)),'small'):null]))),
    panel('Wartungsverträge',has('projects.manage')?button('Wartungsvertrag anlegen',()=>action(()=>maintenanceContracts.edit(projectId,assets)),'small'):null,rows(contracts,item=>row(item.title,`${assets.find(asset=>asset.id===item.asset_id)?.name||'Anlage'} · Nächste Fälligkeit ${formatDate(item.next_due_date)}`,[badge(item.active?'Aktiv':'Pausiert'),has('projects.manage')&&!state.readonly?button('Wartungsvertrag bearbeiten',()=>action(()=>maintenanceContracts.edit(projectId,assets,item.id)),'small'):null])),
      has('projects.manage')?button('Fällige Einsätze planen',()=>action(async()=>{const result=await mutation('maintenance-schedule-'+projectId+'-'+dateInput(),'/maintenance/schedule',{project_id:projectId,as_of:dateInput()});if(result.more_due)main.prepend(notice('Weitere Fälligkeiten vorhanden. Planung erneut ausführen.','warn'));await refresh();}),'small'):null),
    panel('Wartungshistorie',rows(visits,visit=>row(visit.asset_snapshot?.name||'Anlage',`${formatDate(visit.due_date)} · ${visit.contract_snapshot?.title||''}`,[badge(visit.status),visit.status==='completed'?button('Service-PDF',()=>action(()=>download(biz(`/service-reports/${visit.report_id}/pdf`),'Servicebericht.pdf')),'small'):has('documents.write')?button('Mit Servicebericht abschließen',()=>completeVisitDialog(projectId,visit,reports),'small'):null]))));
}
function assetDialog(projectId,item=null) {
  dialog(item?'Anlage bearbeiten':'Anlage erfassen',form('',[field('name','Anlage','text',item?.name||'',{required:true}),field('serial_number','Seriennummer','text',item?.serial_number||''),field('asset_type','Anlagentyp','text',item?.asset_type||''),field('location','Standort / Raum','text',item?.location||''),field('notes','Anlagenhinweise','textarea',item?.notes||'')],
    (data,key)=>mutation(key,'/assets'+(item?'/'+item.id:''),{...data,project_id:projectId,...(item?{revision:item.revision}:{})}),{key:'asset-'+(item?.id||'new')}));
}
function completeVisitDialog(projectId,visit,reports) {
  const signed=reports.filter(report=>report.status==='signed');
  if(!signed.length){dialog('Servicebericht fehlt',notice('Zuerst unter Fotos & Doku eine Checkliste durchführen und den zugehörigen Servicebericht unterzeichnen. Danach lässt sich die Wartung damit abschließen.','warn'));return;}
  dialog('Wartung abschließen',form('',[field('report_id','Unterzeichneter Servicebericht','select','',{options:options(signed),required:true})],(data,key)=>mutation(key,`/maintenance/visits/${visit.id}/complete`,{...data,project_id:projectId,revision:visit.revision}),{key:'complete-visit-'+visit.id,submit:'Abschluss verbindlich speichern'}),'Der PDF-Hash des gewählten Berichts wird dauerhaft mit diesem Wartungsbesuch verknüpft.');
}

function organizationPanel(organization) {
  const fields=ORGANIZATION_NEEDS.map(([name,label])=>field('needs_'+name,label,'checkbox',organization.needs?.[name]===true));
  for(const [name,label] of ORGANIZATION_AREAS) {
    const item=organization.modules?.[name];
    if(!item||typeof item.enabled!=='boolean'||![null,true,false].includes(item.visibility_override))
      throw new ApiError('Die Moduleinstellungen konnten nicht vollständig geladen werden.',502);
    fields.push(field('visibility_'+name,label+' in der Navigation','select',item.visibility_override===null?'auto':item.visibility_override?'show':'hide',
      {options:[['auto','Automatisch vorschlagen'],['show','Immer anzeigen'],['hide','Ausblenden']],help:'Aktueller Vorschlag: '+(item.suggested?'anzeigen':'ausblenden')+'. Eine manuelle Auswahl bleibt bei späteren Änderungen erhalten.'}),
      field('enabled_'+name,label+' fachlich aktiv','checkbox',item.enabled,{help:'Deaktiviert werden neue Vorgänge gesperrt. Vorhandene Daten bleiben lesbar.'}));
  }
  const count=organization.active_employee_count;
  const description='Der Unternehmensbedarf bestimmt die Vorschläge. Sichtbarkeit und fachliche Aktivierung können Sie getrennt korrigieren. Benutzerrechte bleiben eigenständig.'+
    (Number.isSafeInteger(count)?` Aktive Mitarbeiterprofile: ${count}.`:'');
  const links=el('div',{class:'stack'},el('p',{class:'muted'},'Bereiche hier auch bei ausgeblendeter Navigation öffnen. Die vorhandenen Zugriffsrechte gelten weiterhin.'),
    el('div',{class:'actions'},ORGANIZATION_AREAS.filter(([name])=>sectionAuthorized(name)).map(([name,label])=>button(label+' öffnen',()=>navigate(name,{includeHidden:true}),'small'))));
  return form('Unternehmensbedarf und Module',fields,(values,key)=>mutation(key,'/organization',organizationChange(organization,values)),
    {key:'organization-'+organization.revision,description,extra:links,readonly:state.readonly,submit:'Bedarf und Module speichern'});
}
async function settingsView() {
  const [branding,statuses,organization]=await Promise.all([api.get(biz('/settings/branding')),api.get(biz('/project-statuses')),
    state.features.has('organization_modules')?api.get(biz('/organization')):Promise.resolve(null)]);
  const content=el('div',{class:'stack'},heading('Einstellungen','Betriebsdaten und Freigaben. Externe Integrationen bleiben ausdrücklich getrennt.'),
    organization?organizationPanel(organization):null,
    yearValuesWorkspace.available()?panel('Belegte frühere Jahreswerte',notice('Originalgebundene historische Journalzeilen vor Softwarebeginn; keine neue Zahlung und kein neuer Vorsteueranspruch.'),button('Jahresvorträge öffnen',()=>action(()=>yearValuesWorkspace.open()),'small')):null,
    has('privacy.manage')&&state.features.has('privacy_cases')?panel('Datenschutzfälle',el('p',{},'Betroffenenanfragen, Fristen, Quellenprüfung und geschützte Auskunft mit eigener Aufbewahrung.'),button('Datenschutzfälle öffnen',()=>action(()=>privacyCases.open()),'small')):null,
    state.features.has('custom_fields')?panel('Zusatzfelder',el('p',{},'Eigene Angaben für Kontakte, Projekte und Geräte mit lesbaren Fassungen.'),button('Zusatzfelder verwalten',()=>action(()=>customFields.definitions()),'small')):null,
    state.user?.role==='owner'&&state.features.has('company_handover')&&state.capabilities.has('business_company_handover')?panel('Unternehmensübergabe',el('p',{},'Portable Unternehmensarchive und dokumentierte Ausstiegsprüfung für die Geschäftsführung.'),button('Unternehmensübergabe öffnen',()=>action(()=>companyHandover.open()),'small')):null,
    migrationsAllowed()?panel('Kontrollierter Dateiimport',el('p',{},'Originaldateien, Feldzuordnung, Dubletten, Übernahmevorschau und Abgleich. Historische Rechnungen bleiben Archivbelege.'),button('Dateiimport öffnen',()=>action(()=>fileMigrations.open()),'small')):null,

    form('Aussteller & Briefpapier',[field('company_name','Firmenname','text',branding.company_name||'',{required:true}),field('address_line','Straße / Hausnummer','text',branding.address_line||''),field('postal_code','Postleitzahl','text',branding.postal_code||''),field('city','Ort','text',branding.city||''),field('vat_id','USt-IdNr.','text',branding.vat_id||''),field('tax_number','Steuernummer','text',branding.tax_number||''),field('email','Betriebliche E-Mail','email',branding.email||''),field('phone','Telefon','tel',branding.phone||''),field('iban','IBAN','text',branding.iban||''),field('bic','BIC','text',branding.bic||''),field('footer','Fußzeile','textarea',branding.footer||'')],
      (data,key)=>mutation(key,'/settings/branding',{...data,revision:branding.revision}),{key:'branding',description:'Die vorhandene Ausstellerfreigabe wird hier nicht still aktiviert. Historisch finale Dokumente behalten ihre eigene Fassung.'}),
    panel('Projektstatus',button('Status hinzufügen',()=>dialog('Projektstatus',form('',[field('name','Bezeichnung','text','',{required:true}),field('color','Farbe','color','#2864da'),field('position','Reihenfolge','integer',collection(statuses).length,{min:0}),field('terminal','Abschlussstatus','checkbox',false)],(data,key)=>mutation(key,'/project-statuses',{...data,active:true}),{key:'status-new'})),'small'),rows(collection(statuses),status=>row(status.name,`Position ${status.position}`,[badge(status.terminal?'Abschluss':'Laufend')]))),
    panel('Benutzerrechte',button('Freigaben ansehen / ändern',()=>action(()=>permissionsDialog()),'small'),el('p',{class:'caption'},'Berechtigungen werden bei jeder Serveroperation erneut geprüft. Projektzuweisung und Fachrecht sind getrennt.')),
    panel('Externe Verbindungen',el('p',{class:'muted'},'Diese Oberfläche erzeugt keine externen Sendungen, Bestellungen oder Appregistrierungen.'),button('Lieferantenkataloge und Adapter',()=>action(()=>adapterDialog()),'small'),state.capabilities.has('business_catalog_prices')&&has('finance.read')?button('Datierte Katalogpreise',()=>action(()=>datedWorkspace.open()),'small'):null));
  return content;
}
async function permissionsDialog() {
  const [grants,users]=await Promise.all([api.get(biz('/settings/permissions')),api.get('/users')]);
  const permissions=['contacts.read','contacts.write','projects.manage','documents.read','documents.write','documents.classify','finance.read','finance.write','finance.issue','finance.approve','personnel.read','personnel.manage','personnel.write','personnel.approve','personnel.export','time.own','time.approve','inventory.read','inventory.write','settings.manage','privacy.manage',...(state.capabilities.has('business_portal')?['portal.manage']:[]),...(state.capabilities.has('business_accounting')?['accounting.read','accounting.prepare','accounting.admin']:[]),...(state.capabilities.has('business_assistant')?['assistant.use','assistant.approve']:[]),...(state.capabilities.has('business_bank_reconciliation')?['bank.read','bank.prepare','bank.admin']:[])];
  const editor=form('Freigabe / Sperre',[field('user_id','Benutzer','select','',{options:options(collection(users),user=>user.email),required:true}),field('permission','Fachrecht','select','documents.read',{options:permissions.map(name=>[name,name])}),field('scope','Geltungsbereich','select','*',{options:[['*','Global / alle freigegebenen Projekte'],...options(state.projects)]}),field('effect','Entscheidung','select','allow',{options:[['allow','Erlauben'],['deny','Sperren']]})],
    (data,key)=>{const scope=data.permission.startsWith('accounting.')?'*':data.scope;return mutation(key,'/settings/permissions',{...data,scope,revision:collection(grants).find(grant=>grant.user_id===data.user_id&&grant.permission===data.permission&&grant.scope===scope)?.revision||0});},
    {key:'grant-new',description:'Accounting-Rechte gelten ausschließlich global und benötigen zusätzlich global finance.read. Quellrechte und Projektzuweisungen bleiben erforderlich. Sperren gelten auch bei Wiederholungen.'});
  const permission=editor.controls.get('permission').input,scope=editor.controls.get('scope').input;
  permission.addEventListener('change',()=>{scope.disabled=permission.value.startsWith('accounting.');if(scope.disabled)scope.value='*';});
  dialog('Fachrechte',el('div',{class:'stack'},editor,panel('Vorhandene Entscheidungen',rows(collection(grants),grant=>row(collection(users).find(user=>user.id===grant.user_id)?.email||grant.user_id,`${grant.permission} · ${grant.scope==='*'?'Global':state.projects.find(project=>project.id===grant.scope)?.name||grant.scope}`,[badge(grant.effect==='allow'?'Freigegeben':'Gesperrt')])))));
}
async function adapterDialog() { await catalogWorkspace.open(); }

if(typeof document!=='undefined') {
  root=document.getElementById('office-app');
  if(root) {
    loginScreen();
    addEventListener('online',networkState);addEventListener('offline',networkState);
    matchMedia('(max-width:760px)').addEventListener('change',updateDrawer);
    addEventListener('beforeunload',event=>{if(api.pendingCount){event.preventDefault();event.returnValue='';}});
    document.addEventListener('visibilitychange',()=>{if(document.hidden){if(modal?.querySelector('[data-maintenance-contract]'))closeModal();companyEvents.clear();yearPackageWorkspace.clear();accountingEuer.invalidateExport();openItemWorkspace.clear();if(modal?.querySelector('[data-accounting-openings], [data-historical-assets], [data-company-events], [data-open-items], [data-year-package], [data-year-export]'))closeModal();}});
    document.addEventListener('visibilitychange',()=>{if(document.hidden){yearValuesWorkspace.clear();accountingEuer.invalidatePrivateContext();if(modal?.querySelector('[data-year-values],[data-year-values-euer]'))closeModal();}});
    addEventListener('pagehide',()=>endSession());
  }
}
