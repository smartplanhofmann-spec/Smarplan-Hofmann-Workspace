"""Bounded UBL XRechnung generation and official KoSIT validation.

An ordinary PDF with XML attached is deliberately not offered as ZUGFeRD/PDF-A.
No XML parser resolves DTDs, entities, URLs or executes document content.
"""
from dataclasses import dataclass
from pathlib import Path
from decimal import Decimal
import hashlib
import json
import os
import re
import signal
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from core import Problem

MAX_XML=2*1024*1024
JAR_SHA256='799e64befca97d4080e03608c80b85dd5a5ecc5f4ae4f35d1116ec2855b9a7c9'
CONFIG_TREE_SHA256='a85e078104dd621e1cf39d4674878c046a6cec1d8b3d34cf187aa279d19712db'
UBL='urn:oasis:names:specification:ubl:schema:xsd:Invoice-2'
CREDIT='urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2'
CAC='urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
CBC='urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
REPORT='http://www.xoev.de/de/validator/varl/1'
RSM='urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100'
RAM='urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100'
UDT='urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100'
ET.register_namespace('cac',CAC);ET.register_namespace('cbc',CBC)
ET.register_namespace('rsm',RSM);ET.register_namespace('ram',RAM);ET.register_namespace('udt',UDT)


def secure_xml(value):
    if not isinstance(value,bytes) or not 1<=len(value)<=MAX_XML:raise Problem(413,'XML-Größenlimit überschritten')
    try:text=value.decode('utf-8-sig')
    except UnicodeDecodeError:raise Problem(400,'XML muss UTF-8 sein') from None
    if '\x00' in text or re.search(r'<!\s*(?:DOCTYPE|ENTITY)',text,re.I):raise Problem(400,'DTD und XML-Entitäten sind nicht erlaubt')
    try:return ET.fromstring(text)
    except ET.ParseError:raise Problem(400,'Ungültiges XML') from None


def _child(parent,namespace,tag,value=None,**attributes):
    result=ET.SubElement(parent,'{'+namespace+'}'+tag,attributes)
    if value is not None:result.text=str(value)
    return result


def _party(root,tag,values,seller=False):
    branch=_child(root,CAC,tag);party=_child(branch,CAC,'Party')
    endpoint=values.get('email') if seller else values.get('endpoint_id') or values.get('email')
    if not endpoint:raise Problem(409,'Elektronische Rechnungsadresse fehlt')
    _child(party,CBC,'EndpointID',endpoint,schemeID='EM' if seller or not values.get('endpoint_id') else values.get('endpoint_scheme') or 'EM')
    name=values.get('company_name') if seller else values['name']
    _child(_child(party,CAC,'PartyName'),CBC,'Name',name)
    address=_child(party,CAC,'PostalAddress');_child(address,CBC,'StreetName',values['address_line'])
    _child(address,CBC,'CityName',values['city']);_child(address,CBC,'PostalZone',values['postal_code'])
    _child(_child(address,CAC,'Country'),CBC,'IdentificationCode',values['country'])
    if values.get('vat_id'):
        tax=_child(party,CAC,'PartyTaxScheme');_child(tax,CBC,'CompanyID',values['vat_id']);_child(_child(tax,CAC,'TaxScheme'),CBC,'ID','VAT')
    elif seller and values.get('tax_number'):
        tax=_child(party,CAC,'PartyTaxScheme');_child(tax,CBC,'CompanyID',values['tax_number']);_child(_child(tax,CAC,'TaxScheme'),CBC,'ID','FC')
    _child(_child(party,CAC,'PartyLegalEntity'),CBC,'RegistrationName',name)
    if seller:
        if not values.get('phone') or not values.get('email'):raise Problem(409,'Telefon und E-Mail des Rechnungskontakts fehlen')
        contact=_child(party,CAC,'Contact');_child(contact,CBC,'Name',name);_child(contact,CBC,'Telephone',values['phone']);_child(contact,CBC,'ElectronicMail',values['email'])


def build_xrechnung(snapshot):
    """EN16931/UBL Invoice or CreditNote; the validator is a mandatory next step."""
    credit=snapshot['kind']=='credit_note'
    if snapshot['kind'] not in ('invoice','advance_invoice','cumulative_invoice','final_invoice','credit_note'):raise Problem(409,'Kein elektronischer Rechnungsbeleg')
    root=ET.Element('{'+(CREDIT if credit else UBL)+'}'+('CreditNote' if credit else 'Invoice'))
    _child(root,CBC,'CustomizationID','urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0')
    _child(root,CBC,'ProfileID','urn:fdc:peppol.eu:2017:poacc:billing:01:1.0')
    _child(root,CBC,'ID',snapshot['number']);_child(root,CBC,'IssueDate',snapshot['issue_date'])
    if not credit:_child(root,CBC,'DueDate',snapshot['due_date'])
    _child(root,CBC,'CreditNoteTypeCode' if credit else 'InvoiceTypeCode','381' if credit else ('386' if snapshot['kind']=='advance_invoice' else '380'))
    if snapshot.get('notes'):_child(root,CBC,'Note',snapshot['notes'])
    _child(root,CBC,'DocumentCurrencyCode','EUR')
    if not snapshot.get('buyer_reference'):raise Problem(409,'Käuferreferenz / Leitweg-ID für XRechnung fehlt')
    _child(root,CBC,'BuyerReference',snapshot['buyer_reference'])
    if credit and snapshot.get('cancels'):
        reference=_child(_child(root,CAC,'BillingReference'),CAC,'InvoiceDocumentReference')
        _child(reference,CBC,'ID',snapshot.get('cancelled_number') or snapshot['cancels'])
    for previous in snapshot.get('previous_documents',[]):
        reference=_child(_child(root,CAC,'BillingReference'),CAC,'InvoiceDocumentReference');_child(reference,CBC,'ID',previous['number']);_child(reference,CBC,'IssueDate',previous['issue_date'])
    _party(root,'AccountingSupplierParty',snapshot['issuer'],True);_party(root,'AccountingCustomerParty',snapshot['buyer'])
    issuer=snapshot['issuer']
    if not issuer.get('iban'):raise Problem(409,'IBAN für XRechnung fehlt')
    payment=_child(root,CAC,'PaymentMeans');_child(payment,CBC,'PaymentMeansCode','58');_child(payment,CBC,'PaymentID',snapshot['number'])
    account=_child(payment,CAC,'PayeeFinancialAccount');_child(account,CBC,'ID',issuer['iban'].replace(' ',''))
    if issuer.get('bic'):_child(_child(account,CAC,'FinancialInstitutionBranch'),CBC,'ID',issuer['bic'])
    if issuer.get('payment_terms'):_child(_child(root,CAC,'PaymentTerms'),CBC,'Note',issuer['payment_terms'])
    allowances=_prior_allowances(snapshot)
    for bucket in allowances:
        allowance=_child(root,CAC,'AllowanceCharge');_child(allowance,CBC,'ChargeIndicator','false')
        _child(allowance,CBC,'AllowanceChargeReason','Bereits gesondert berechnete Leistung; keine Zahlungsbestätigung')
        _child(allowance,CBC,'Amount',bucket['net'],currencyID='EUR')
        category=_child(allowance,CAC,'TaxCategory');_child(category,CBC,'ID',bucket['category']);_child(category,CBC,'Percent',bucket['rate']);_child(_child(category,CAC,'TaxScheme'),CBC,'ID','VAT')
    totals=snapshot['totals'];tax=_child(root,CAC,'TaxTotal');_child(tax,CBC,'TaxAmount',totals['tax'],currencyID='EUR')
    for bucket in totals['tax_breakdown']:
        subtotal=_child(tax,CAC,'TaxSubtotal');_child(subtotal,CBC,'TaxableAmount',bucket['net'],currencyID='EUR');_child(subtotal,CBC,'TaxAmount',bucket['tax'],currencyID='EUR')
        category=_child(subtotal,CAC,'TaxCategory');_child(category,CBC,'ID',bucket['category']);_child(category,CBC,'Percent',bucket['rate'])
        if bucket.get('reason'):_child(category,CBC,'TaxExemptionReason',bucket['reason'])
        _child(_child(category,CAC,'TaxScheme'),CBC,'ID','VAT')
    monetary=_child(root,CAC,'LegalMonetaryTotal')
    for key,value in (('LineExtensionAmount',snapshot.get('contract_totals',totals)['net']),('TaxExclusiveAmount',totals['net']),('TaxInclusiveAmount',totals['gross'])):_child(monetary,CBC,key,value,currencyID='EUR')
    if allowances:_child(monetary,CBC,'AllowanceTotalAmount',_amount(sum((Decimal(b['net']) for b in allowances),Decimal(0))),currencyID='EUR')
    _child(monetary,CBC,'PayableAmount',totals['gross'],currencyID='EUR')
    for position in snapshot['positions']:
        line=_child(root,CAC,'CreditNoteLine' if credit else 'InvoiceLine');_child(line,CBC,'ID',position['index'])
        _child(line,CBC,'CreditedQuantity' if credit else 'InvoicedQuantity',position['quantity'],unitCode=position['unit'])
        _child(line,CBC,'LineExtensionAmount',position['net'],currencyID='EUR')
        if Decimal(position.get('discount_percent','0')):
            # Exact net unit after discount avoids implicit, unevidenced
            # allowance percentages in the emitted UBL price semantics.
            net_unit=Decimal(position['unit_price_net'])*(100-Decimal(position['discount_percent']))/100
        else:net_unit=Decimal(position['unit_price_net'])
        item=_child(line,CAC,'Item');_child(item,CBC,'Name',position['description'])
        category=_child(item,CAC,'ClassifiedTaxCategory');_child(category,CBC,'ID',position['tax_category']);_child(category,CBC,'Percent',position['tax_rate']);_child(_child(category,CAC,'TaxScheme'),CBC,'ID','VAT')
        price=_child(line,CAC,'Price');_child(price,CBC,'PriceAmount',format(net_unit,'f'),currencyID='EUR')
        _child(price,CBC,'BaseQuantity',position.get('price_base_quantity','1'),unitCode=position['unit'])
    result=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    secure_xml(result)
    return result


def _amount(value):return format(value.quantize(Decimal('.01')),'f')


def _prior_allowances(snapshot):
    if not snapshot.get('previous_documents'):return []
    remaining={(b['rate'],b['category'],b['reason']):b for b in snapshot['totals']['tax_breakdown']};result=[]
    for full in snapshot['contract_totals']['tax_breakdown']:
        bucket=remaining[(full['rate'],full['category'],full['reason'])];net=Decimal(full['net'])-Decimal(bucket['net'])
        if net<0:raise Problem(409,'Ungültiger kumulierter Leistungsabzug')
        if net:result.append({**full,'net':_amount(net)})
    return result


def build_zugferd_cii(snapshot):
    """ZUGFeRD2/Factur-X EN16931 CII, no invented PDF/A attachment profile."""
    if snapshot['kind'] not in ('invoice','advance_invoice','credit_note','cumulative_invoice','final_invoice'):raise Problem(409,'ZUGFeRD-EN16931-Profil für diese Belegart ist noch nicht freigegeben')
    root=ET.Element('{'+RSM+'}CrossIndustryInvoice')
    context=_child(root,RSM,'ExchangedDocumentContext');_child(_child(context,RAM,'BusinessProcessSpecifiedDocumentContextParameter'),RAM,'ID','urn:fdc:peppol.eu:2017:poacc:billing:01:1.0')
    _child(_child(context,RAM,'GuidelineSpecifiedDocumentContextParameter'),RAM,'ID','urn:cen.eu:en16931:2017')
    document=_child(root,RSM,'ExchangedDocument');_child(document,RAM,'ID',snapshot['number']);_child(document,RAM,'TypeCode','381' if snapshot['kind']=='credit_note' else '380')
    _child(_child(document,RAM,'IssueDateTime'),UDT,'DateTimeString',snapshot['issue_date'].replace('-',''),format='102')
    if snapshot.get('notes'):_child(_child(document,RAM,'IncludedNote'),RAM,'Content',snapshot['notes'])
    trade=_child(root,RSM,'SupplyChainTradeTransaction')
    for p in snapshot['positions']:
        line=_child(trade,RAM,'IncludedSupplyChainTradeLineItem');_child(_child(line,RAM,'AssociatedDocumentLineDocument'),RAM,'LineID',p['index'])
        _child(_child(line,RAM,'SpecifiedTradeProduct'),RAM,'Name',p['description'])
        agreement=_child(line,RAM,'SpecifiedLineTradeAgreement')
        price=Decimal(p['unit_price_net'])*(100-Decimal(p['discount_percent']))/100
        net_price=_child(agreement,RAM,'NetPriceProductTradePrice');_child(net_price,RAM,'ChargeAmount',format(price,'f'))
        _child(net_price,RAM,'BasisQuantity',p.get('price_base_quantity','1'),unitCode=p['unit'])
        _child(_child(line,RAM,'SpecifiedLineTradeDelivery'),RAM,'BilledQuantity',p['quantity'],unitCode=p['unit'])
        settlement=_child(line,RAM,'SpecifiedLineTradeSettlement');tax=_child(settlement,RAM,'ApplicableTradeTax')
        _child(tax,RAM,'TypeCode','VAT');_child(tax,RAM,'CategoryCode',p['tax_category']);_child(tax,RAM,'RateApplicablePercent',p['tax_rate'])
        _child(_child(settlement,RAM,'SpecifiedTradeSettlementLineMonetarySummation'),RAM,'LineTotalAmount',p['net'])
    agreement=_child(trade,RAM,'ApplicableHeaderTradeAgreement')
    if snapshot.get('buyer_reference'):_child(agreement,RAM,'BuyerReference',snapshot['buyer_reference'])
    for seller,values in ((True,snapshot['issuer']),(False,snapshot['buyer'])):
        party=_child(agreement,RAM,'SellerTradeParty' if seller else 'BuyerTradeParty');name=values['company_name'] if seller else values['name']
        _child(party,RAM,'Name',name)
        if seller:
            contact=_child(party,RAM,'DefinedTradeContact');_child(contact,RAM,'PersonName',name)
            if values.get('phone'):_child(_child(contact,RAM,'TelephoneUniversalCommunication'),RAM,'CompleteNumber',values['phone'])
            if values.get('email'):_child(_child(contact,RAM,'EmailURIUniversalCommunication'),RAM,'URIID',values['email'])
        address=_child(party,RAM,'PostalTradeAddress');_child(address,RAM,'PostcodeCode',values['postal_code']);_child(address,RAM,'LineOne',values['address_line']);_child(address,RAM,'CityName',values['city']);_child(address,RAM,'CountryID',values['country'])
        if values.get('email'):_child(_child(party,RAM,'URIUniversalCommunication'),RAM,'URIID',values['email'],schemeID='EM')
        if values.get('vat_id'):_child(_child(party,RAM,'SpecifiedTaxRegistration'),RAM,'ID',values['vat_id'],schemeID='VA')
        elif seller and values.get('tax_number'):_child(_child(party,RAM,'SpecifiedTaxRegistration'),RAM,'ID',values['tax_number'],schemeID='FC')
    _child(trade,RAM,'ApplicableHeaderTradeDelivery')
    settlement=_child(trade,RAM,'ApplicableHeaderTradeSettlement');_child(settlement,RAM,'PaymentReference',snapshot['number']);_child(settlement,RAM,'InvoiceCurrencyCode','EUR')
    payment=_child(settlement,RAM,'SpecifiedTradeSettlementPaymentMeans');_child(payment,RAM,'TypeCode','58')
    issuer=snapshot['issuer']
    if not issuer.get('iban'):raise Problem(409,'IBAN für das freigegebene ZUGFeRD-Profil fehlt')
    _child(_child(payment,RAM,'PayeePartyCreditorFinancialAccount'),RAM,'IBANID',issuer['iban'].replace(' ',''))
    if issuer.get('bic'):_child(_child(payment,RAM,'PayeeSpecifiedCreditorFinancialInstitution'),RAM,'BICID',issuer['bic'])
    totals=snapshot['totals']
    for bucket in totals['tax_breakdown']:
        tax=_child(settlement,RAM,'ApplicableTradeTax');_child(tax,RAM,'CalculatedAmount',bucket['tax']);_child(tax,RAM,'TypeCode','VAT')
        if bucket['reason']:_child(tax,RAM,'ExemptionReason',bucket['reason'])
        _child(tax,RAM,'BasisAmount',bucket['net']);_child(tax,RAM,'CategoryCode',bucket['category']);_child(tax,RAM,'RateApplicablePercent',bucket['rate'])
    allowances=_prior_allowances(snapshot)
    for bucket in allowances:
        allowance=_child(settlement,RAM,'SpecifiedTradeAllowanceCharge');_child(_child(allowance,RAM,'ChargeIndicator'),UDT,'Indicator','false')
        _child(allowance,RAM,'ActualAmount',bucket['net']);_child(allowance,RAM,'Reason','Bereits gesondert berechnete Leistung; keine Zahlungsbestätigung')
        tax=_child(allowance,RAM,'CategoryTradeTax');_child(tax,RAM,'TypeCode','VAT');_child(tax,RAM,'CategoryCode',bucket['category']);_child(tax,RAM,'RateApplicablePercent',bucket['rate'])
    terms=_child(settlement,RAM,'SpecifiedTradePaymentTerms');_child(terms,RAM,'Description',issuer.get('payment_terms') or 'Zahlbar ohne Abzug.')
    _child(_child(terms,RAM,'DueDateDateTime'),UDT,'DateTimeString',snapshot['due_date'].replace('-',''),format='102')
    summary=_child(settlement,RAM,'SpecifiedTradeSettlementHeaderMonetarySummation')
    _child(summary,RAM,'LineTotalAmount',snapshot.get('contract_totals',totals)['net'])
    if allowances:_child(summary,RAM,'AllowanceTotalAmount',_amount(sum((Decimal(b['net']) for b in allowances),Decimal(0))))
    for tag,key in (('TaxBasisTotalAmount','net'),('TaxTotalAmount','tax'),('GrandTotalAmount','gross'),('DuePayableAmount','gross')):
        _child(summary,RAM,tag,totals[key],**({'currencyID':'EUR'} if tag=='TaxTotalAmount' else {}))
    if snapshot.get('cancels'):
        reference=_child(settlement,RAM,'InvoiceReferencedDocument');_child(reference,RAM,'IssuerAssignedID',snapshot.get('cancelled_number') or snapshot['cancels'])
    result=ET.tostring(root,encoding='utf-8',xml_declaration=True);secure_xml(result);return result


MUSTANG_SHA256='42d7868cb68264874a7b8cab4c3587b03b23ccc7cd72373da917f66758bb9736'
VERAPDF_SHA256='4c8acbaeb16405456c8d6d76deac8cf40d94618cb4e33aedf44e51ee1b68be91'


def _pinned_tool(name,default,digest):
    path=Path(os.environ.get(name,default))
    if not path.is_absolute() or not path.is_file():raise Problem(409,'Offizielles ZUGFeRD-/PDF-A-Prüfwerkzeug ist nicht eingerichtet')
    with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=digest:raise Problem(409,'ZUGFeRD-/PDF-A-Werkzeugprüfsumme stimmt nicht')
    return str(path)


def _run_local(command,*,cwd,output=None,timeout=40):
    destination=Path(output) if output else Path(cwd)/('tool-'+os.urandom(6).hex()+'.log')
    with destination.open('wb') as stream:
        worker=subprocess.Popen(command,cwd=cwd,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.DEVNULL,
            env={'PATH':'/usr/bin:/bin','HOME':str(cwd),'LANG':'C.UTF-8'},start_new_session=True,close_fds=True)
        try:code=worker.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(worker.pid,signal.SIGKILL);worker.wait();raise Problem(503,'Zeitlimit der lokalen Belegprüfung überschritten') from None
    if destination.stat().st_size>8*1024*1024:raise Problem(503,'Belegprüfbericht überschreitet das Größenlimit')
    return code,destination.read_bytes()


def validate_pdfa3(pdf,*,evidence_dir=None):
    if not isinstance(pdf,bytes) or not pdf.startswith(b'%PDF-') or len(pdf)>20*1024*1024:raise Problem(400,'Begrenzte PDF-Datei erwartet')
    jar=_pinned_tool('SMARTPLAN_VERAPDF_JAR','/workspace/toolchains/verapdf-cli-1.30.3.jar',VERAPDF_SHA256)
    java=os.environ.get('SMARTPLAN_KOSIT_JAVA','/usr/bin/java')
    with tempfile.TemporaryDirectory(prefix='smartplan-verapdf-') as tmp:
        path=Path(tmp);source=path/'document.pdf';source.write_bytes(pdf)
        code,raw=_run_local([java,'-Xmx384m','-Djava.awt.headless=true','-jar',jar,'--format','xml','--flavour','3b','--loglevel','0','--maxfailures','20','--maxfailuresdisplayed','3',str(source)],cwd=path)
        try:root=ET.fromstring(raw)
        except ET.ParseError:raise Problem(503,'veraPDF-Prüfung konnte nicht ausgewertet werden') from None
        reports=[e for e in root.iter() if e.tag.rsplit('}',1)[-1]=='validationReport']
        if len(reports)!=1 or reports[0].get('isCompliant')!='true':raise Problem(409,'PDF/A-3B-Prüfung durch veraPDF abgelehnt')
        if code!=0:raise Problem(503,'veraPDF-Prüfung konnte nicht abgeschlossen werden')
        if evidence_dir:
            destination=Path(evidence_dir);destination.mkdir(parents=True,mode=0o700,exist_ok=True)
            (destination/(hashlib.sha256(pdf).hexdigest()+'-verapdf.xml')).write_bytes(raw)
        return {'accepted':True,'profile':'PDF/A-3B','validator':'veraPDF 1.30.3','validator_sha256':VERAPDF_SHA256,'report_sha256':hashlib.sha256(raw).hexdigest()}


def build_zugferd(snapshot,pdf,*,evidence_dir=None):
    xml=build_zugferd_cii(snapshot)
    jar=_pinned_tool('SMARTPLAN_MUSTANG_JAR','/workspace/toolchains/Mustang-CLI-2.26.0.jar',MUSTANG_SHA256)
    java=os.environ.get('SMARTPLAN_KOSIT_JAVA','/usr/bin/java');gs=os.environ.get('SMARTPLAN_GHOSTSCRIPT','/usr/bin/gs')
    icc=Path(os.environ.get('SMARTPLAN_SRGB_ICC','/usr/share/color/icc/ghostscript/srgb.icc'))
    if not Path(gs).is_absolute() or not Path(gs).is_file() or not icc.is_absolute() or not icc.is_file():raise Problem(409,'PDF/A-3-Erzeugung ist nicht eingerichtet')
    with tempfile.TemporaryDirectory(prefix='smartplan-zugferd-') as tmp:
        path=Path(tmp);(path/'source.pdf').write_bytes(pdf);(path/'invoice.xml').write_bytes(xml);(path/'profile.icc').write_bytes(icc.read_bytes())
        # Only this generated PDF, our bounded logo, and a local ICC profile
        # enter Ghostscript; user PDF/PS originals are never executed here.
        (path/'pdfa.ps').write_text("%!\n/ICCProfile ("+str(path/'profile.icc')+") def\n"
            "[/_objdef {icc_PDFA} /type /stream /OBJ pdfmark\n[{icc_PDFA} << /N 3 >> /PUT pdfmark\n[{icc_PDFA} ICCProfile (r) file /PUT pdfmark\n"
            "[/_objdef {OutputIntent_PDFA} /type /dict /OBJ pdfmark\n[{OutputIntent_PDFA} << /Type /OutputIntent /S /GTS_PDFA1 /DestOutputProfile {icc_PDFA} /OutputConditionIdentifier (sRGB) >> /PUT pdfmark\n"
            "[{Catalog} << /OutputIntents [{OutputIntent_PDFA}] >> /PUT pdfmark\n",encoding='ascii')
        code,_=_run_local([gs,'-dSAFER','-dBATCH','-dNOPAUSE','-dPDFA=3','-dPDFACompatibilityPolicy=1','-sDEVICE=pdfwrite','-sColorConversionStrategy=RGB',
            '-dEmbedAllFonts=true','-dSubsetFonts=true','--permit-file-read='+str(path/'profile.icc'),'-sOutputFile='+str(path/'pdfa.pdf'),str(path/'pdfa.ps'),str(path/'source.pdf')],cwd=path,timeout=25)
        if code!=0 or not (path/'pdfa.pdf').is_file():raise Problem(503,'PDF/A-Erzeugung fehlgeschlagen')
        command=[java,'-Xmx384m','-Djava.awt.headless=true','-Djavax.xml.accessExternalDTD=','-Djavax.xml.accessExternalSchema=file','-jar',jar]
        code,_=_run_local(command+['--action','combine','--source',str(path/'pdfa.pdf'),'--source-xml',str(path/'invoice.xml'),'--out',str(path/'zugferd.pdf'),
            '--format','zf','--version','2','--profile','E','--no-additional-attachments','--disable-file-logging'],cwd=path)
        if code!=0 or not (path/'zugferd.pdf').is_file():raise Problem(503,'ZUGFeRD-Verknüpfung konnte nicht abgeschlossen werden')
        result=(path/'zugferd.pdf').read_bytes()
        if len(result)>20*1024*1024:raise Problem(413,'ZUGFeRD-Datei überschreitet das Limit')
        code,raw=_run_local(command+['--action','validate','--source',str(path/'zugferd.pdf'),'--disable-file-logging'],cwd=path)
        # Mustang emits a machine-readable validation document after its banner.
        start=raw.find(b'<validation')
        try:report=ET.fromstring(raw[start:] if start>=0 else raw)
        except ET.ParseError:raise Problem(503,'ZUGFeRD-Prüfbericht konnte nicht ausgewertet werden') from None
        statuses=[e.get('status') for e in report.iter() if e.tag.rsplit('}',1)[-1]=='summary']
        if code!=0 or not statuses or any(s!='valid' for s in statuses):raise Problem(409,'ZUGFeRD-EN16931-Prüfung durch Mustang abgelehnt')
        # Extract again to prove that the delivered embedded original is exactly
        # the XML that was generated from the frozen monetary snapshot.
        code,_=_run_local(command+['--action','extract','--source',str(path/'zugferd.pdf'),'--out',str(path/'embedded.xml'),'--disable-file-logging'],cwd=path)
        if code!=0 or not (path/'embedded.xml').is_file() or (path/'embedded.xml').read_bytes()!=xml:raise Problem(409,'Eingebettete ZUGFeRD-Rechnung stimmt nicht mit dem Original überein')
        pdfa=validate_pdfa3(result,evidence_dir=evidence_dir)
        if evidence_dir:
            destination=Path(evidence_dir);destination.mkdir(parents=True,mode=0o700,exist_ok=True)
            (destination/'synthetic-zugferd.pdf').write_bytes(result);(destination/'synthetic-zugferd.xml').write_bytes(xml);(destination/'synthetic-mustang-report.xml').write_bytes(raw)
        return result,xml,{'accepted':True,'format':'ZUGFeRD 2 / EN16931','validator':'Mustang 2.26.0','validator_sha256':MUSTANG_SHA256,
            'xml_sha256':hashlib.sha256(xml).hexdigest(),'report_sha256':hashlib.sha256(raw).hexdigest(),'pdfa':pdfa}


@dataclass(frozen=True)
class KositConfiguration:
    java:str
    jar:str
    scenarios:str


def configuration(config=None):
    # Explicit, operator-provided absolute paths. Cloud defaults are a local
    # development convenience, never an automatic download or deployment.
    base=Path('/workspace/toolchains/kosit-1.6.3')
    value=config or KositConfiguration(os.environ.get('SMARTPLAN_KOSIT_JAVA','/usr/bin/java'),
        os.environ.get('SMARTPLAN_KOSIT_JAR',str(base/'validator-1.6.3-standalone.jar')),
        os.environ.get('SMARTPLAN_KOSIT_SCENARIOS',str(base/'xrechnung-3.0.2-2026-08-31/scenarios.xml')))
    if any(not Path(p).is_absolute() or not Path(p).is_file() for p in (value.java,value.jar,value.scenarios)):raise Problem(409,'Offizieller KoSIT-Validator ist nicht eingerichtet')
    if hashlib.sha256(Path(value.jar).read_bytes()).hexdigest()!=JAR_SHA256:raise Problem(409,'KoSIT-Version / Prüfsumme stimmt nicht')
    root=Path(value.scenarios).parent;files=[];total=0
    if Path(value.scenarios).name!='scenarios.xml':raise Problem(409,'Offizielle XRechnung-Konfiguration erforderlich')
    for item in sorted(root.rglob('*')):
        if item.is_symlink():raise Problem(409,'Keine Verknüpfungen in der XRechnung-Konfiguration erlaubt')
        if item.is_file():
            total+=item.stat().st_size
            if total>64*1024*1024 or len(files)>=97:raise Problem(409,'XRechnung-Konfiguration stimmt nicht mit der freigegebenen Version überein')
            with item.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            files.append((item.relative_to(root).as_posix(),digest))
    actual=hashlib.sha256(json.dumps(files,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
    if actual!=CONFIG_TREE_SHA256:raise Problem(409,'Offizielle XRechnung-Konfiguration ist verändert oder unvollständig')
    return value


def validate_xrechnung(value,*,config=None,timeout=45,evidence_dir=None):
    secure_xml(value);config=configuration(config)
    if type(timeout) not in (int,float) or not 1<=timeout<=60:raise ValueError('Bounded validation deadline required')
    with tempfile.TemporaryDirectory(prefix='smartplan-kosit-') as directory:
        private=Path(directory);private.chmod(0o700);source=private/'invoice.xml';source.write_bytes(value);source.chmod(0o600)
        output=private/'report';output.mkdir(mode=0o700)
        command=[config.java,'-Xmx256m','-Djava.awt.headless=true','-Djavax.xml.accessExternalDTD=',
            '-Djavax.xml.accessExternalSchema=file','-jar',config.jar,'-s',config.scenarios,'-r',str(Path(config.scenarios).parent),'-o',str(output),str(source)]
        with open(os.devnull,'wb') as stream:
            process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':directory},start_new_session=True,close_fds=True)
            try:code=process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait();raise Problem(503,'Zeitlimit der offiziellen Rechnungsprüfung überschritten') from None
        reports=[]
        for file in output.glob('*.xml'):
            if file.stat().st_size>8*1024*1024:raise Problem(503,'Prüfbericht überschreitet das Größenlimit')
            try:root=ET.fromstring(file.read_bytes())
            except ET.ParseError:continue
            if root.tag=='{'+REPORT+'}report':reports.append((root,file.read_bytes()))
        if len(reports)!=1:raise Problem(503,'Offizielle Rechnungsprüfung konnte nicht abgeschlossen werden')
        root,raw_report=reports[0]
        if evidence_dir is not None:
            destination=Path(evidence_dir);destination.mkdir(parents=True,exist_ok=True,mode=0o700)
            if destination.is_symlink() or destination.stat().st_mode&0o077:raise ValueError('Private validator evidence directory required')
            target=destination/(hashlib.sha256(value).hexdigest()+'-report.xml')
            with target.open('xb') as stream:os.chmod(target,0o600);stream.write(raw_report)
        accepted=root.find('.//{'+REPORT+'}assessment/{'+REPORT+'}accept') is not None
        rejected=root.find('.//{'+REPORT+'}assessment/{'+REPORT+'}reject') is not None
        if not accepted or rejected:
            # No invoice content or provider response is reflected into errors.
            raise Problem(409,'XRechnung wurde vom offiziellen KoSIT-Validator abgelehnt')
        if code!=0:raise Problem(503,'Offizielle Rechnungsprüfung konnte nicht abgeschlossen werden')
        return {'accepted':True,'validator':'KoSIT','validator_version':'1.6.3','validator_sha256':JAR_SHA256,
            'configuration':'XRechnung 3.0.2 / 2026-08-31','xml_sha256':hashlib.sha256(value).hexdigest(),
            'configuration_tree_sha256':CONFIG_TREE_SHA256,
            'report_sha256':hashlib.sha256(raw_report).hexdigest()}


def inspect_invoice(value):
    """Read supported XML facts as a review suggestion, retaining original hash."""
    root=secure_xml(value)
    if root.tag=='{'+RSM+'}CrossIndustryInvoice':
        ns={'rsm':RSM,'ram':RAM,'udt':UDT}
        def cii_text(path):
            element=root.find(path,ns);return element.text if element is not None else None
        issued=cii_text('rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString')
        if issued and re.fullmatch('[0-9]{8}',issued):issued=issued[:4]+'-'+issued[4:6]+'-'+issued[6:]
        prefix='rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/'
        return {'format':'cii','sha256':hashlib.sha256(value).hexdigest(),'number':cii_text('rsm:ExchangedDocument/ram:ID'),
            'issue_date':issued,'currency':cii_text(prefix+'ram:InvoiceCurrencyCode'),
            'gross':cii_text(prefix+'ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount'),
            'payable':cii_text(prefix+'ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:DuePayableAmount'),'status':'needs_review','original_preserved':True}
    if root.tag not in ('{'+UBL+'}Invoice','{'+CREDIT+'}CreditNote'):raise Problem(415,'Nur UBL- oder CII-Rechnung wird derzeit erkannt')
    ns={'cbc':CBC,'cac':CAC}
    def text(path):
        element=root.find(path,ns);return element.text if element is not None else None
    return {'format':'ubl','sha256':hashlib.sha256(value).hexdigest(),'number':text('cbc:ID'),'issue_date':text('cbc:IssueDate'),
        'currency':text('cbc:DocumentCurrencyCode'),'gross':text('cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount'),
        'payable':text('cac:LegalMonetaryTotal/cbc:PayableAmount'),'status':'needs_review','original_preserved':True}


def capabilities():return {'xrechnung':'official_kosit_required','zugferd':'EN16931 / PDF-A-3B / Mustang+veraPDF required',
    'pdfa':'only_verified_zugferd_artifact','cii_import':True,'zugferd_cumulative':True}
