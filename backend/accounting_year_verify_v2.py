"""Standalone v2 year package checker. Standard library only; never extracts.

Internal consistency is not a signature. A separately authenticated ZIP hash is
mandatory: legacy journals do not bind a complete intrinsic dependency index.
This frozen version checks financial evidence; it does not recalculate tax law.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

MAX_BYTES = 128 * 1024 * 1024
MAX_FILES = 10000
HEX = re.compile(r'[a-f0-9]{64}')
ID = re.compile(r'[a-f0-9]{32}')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def sha(value):
    if not isinstance(value, bytes):
        value = (value if isinstance(value, str) else canonical(value)).encode()
    return hashlib.sha256(value).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def decode(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'Duplicate JSON field')
            result[key] = value
        return result
    def reject(value):
        raise ValueError('Nonfinite number')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)
    require(canonical(value).encode() == raw, 'Noncanonical JSON')
    return value


def cents(value):
    require(isinstance(value, str) and re.fullmatch(r'-?(?:0|[1-9][0-9]*)\.[0-9]{2}', value) and value != '-0.00', 'Invalid exact amount')
    return int(value.replace('.', ''))


def money(value):
    return ('-' if value < 0 else '') + str(abs(value)//100) + '.' + str(abs(value)%100).zfill(2)


def state_hash(revision, head):
    return sha(dict(schema_version=1, revision=revision, head=head))


def csv_bytes(report):
    stream=io.StringIO(newline=''); writer=csv.writer(stream,delimiter=';',lineterminator='\r\n')
    writer.writerow(['entry_id','sequence','date','ledger','category','amount_eur','account_skr04','source_key'])
    for value in report['postings']:
        cells=[str(value[key]) for key in ('entry_id','sequence','date','ledger','category','amount','account','source_key')]
        writer.writerow([("'"+cell if index!=5 and cell[:1] in ('=','+','-','@','\t','\r') else cell) for index,cell in enumerate(cells)])
    return stream.getvalue().encode()


def verify_journal(manifest, report, journal):
    prefix=journal['prefix']; decisions=journal['decisions']; entries={}
    require(len(prefix)==report['revision'] and len(prefix)<=100000, 'Changed frozen journal horizon')
    for index,row in enumerate(prefix,1):
        require(set(row)=={'sequence','entry_hash','target_hash'} and row['sequence']==index
                and HEX.fullmatch(row['entry_hash']) and HEX.fullmatch(row['target_hash']), 'Invalid prefix commitment')
    require(report['state_hash']==state_hash(len(prefix),prefix[-1]['entry_hash'] if prefix else None), 'Changed journal head')
    for decision in decisions:
        entry=decision['entry']; acceptance=decision['acceptance']; key=entry['id']; seq=entry['sequence']
        require(ID.fullmatch(key) and key not in entries and type(seq) is int and 1<=seq<=len(prefix)+1, 'Invalid decision identity')
        require(sha({k:v for k,v in entry.items() if k!='entry_hash'})==entry['entry_hash'], 'Changed original journal entry')
        require(entry['previous_hash']==state_hash(seq-1,prefix[seq-2]['entry_hash'] if seq>1 else None), 'Changed preceding journal commitment')
        if seq<=len(prefix):
            require(prefix[seq-1]['entry_hash']==entry['entry_hash'] and prefix[seq-1]['target_hash']==sha(entry['target']), 'Crossed journal commitment')
        command=decode(acceptance['request_json'].encode())
        require(acceptance['entry_id']==key and acceptance['request_hash']==sha(command)
                and acceptance['user_id']==entry['created_by'] and command['request_id']==acceptance['request_id']
                and command['confirmation'] is True and command['expected_revision']==seq-1
                and command['state_hash']==entry['previous_hash'], 'Changed original acceptance')
        require(all(command[k]==entry[k] for k in ('operation','payload','reason','evidence_reference','preview_hash')), 'Crossed accepted command')
        preview={k:v for k,v in entry.items() if k not in ('id','sequence','previous_hash','created_by','created_at','preview_hash','entry_hash')}
        preview.update(expected_revision=seq-1,state_hash=entry['previous_hash'])
        require(sha(preview)==entry['preview_hash'], 'Changed accepted preview')
        entries[key]=entry
    export=entries.get(manifest['export_id'])
    require(export and export['operation']=='export' and export['sequence']==len(prefix)+1
            and export['entry_hash']==manifest['export_hash'] and journal['export_id']==export['id'], 'Foreign export entry')
    artifact=export['artifact']
    require(artifact['format']=='smartplan_euer_review_v1' and artifact['report']==report
            and artifact['report_sha256']==manifest['report_sha256'] and artifact['csv_sha256']==manifest['csv_sha256']
            and export['payload']=={'year':report['year']} and artifact['official_tax_return'] is False
            and artifact['datev_certified'] is False, 'Changed frozen export artifact')
    ordered=sorted((row for row in entries.values() if row['id']!=export['id']),key=lambda x:x['sequence'])
    require([v['entry']['id'] for v in decisions]==[v['id'] for v in ordered]+[export['id']], 'Noncanonical decision order')
    targets={sha(row['target']) for row in ordered}
    # A later paid purchase intrinsically requires its earlier VAT/asset
    # decisions, even when they produced no postings in the exported year.
    for row in ordered:
        if not row['effect']:continue
        source=row['effect']['source'];original=source.get('receipt',{}).get('original_sha256')
        if source['kind']=='cash' and source['event']['source']['kind']=='receipt':
            original=source['event']['source']['snapshot']['original_sha256']
        if original:
            targets.update(sha(kind+':'+original) for kind in ('input_vat','asset'))
    require(all(row['entry_hash'] in {v['entry_hash'] for v in ordered} for row in prefix if row['target_hash'] in targets), 'Truncated economic correction history')
    roots=set();year=str(report['year']);postings=[]
    for entry in ordered:
        effect=entry['effect']; old=entries.get(entry['reverses']) if entry['reverses'] else None
        if entry['reverses']:
            require(old and old['effect'] and old['sequence']<entry['sequence'] and old['target']==entry['target'], 'Missing correction origin')
        expected=[]
        if old:
            expected=[dict(value,amount=money(-cents(value['amount']))) for value in old['effect']['postings']]
        if effect:
            require(effect['target']==entry['target'], 'Crossed economic target')
            require(effect['operation']==(entry['payload']['operation'] if entry['operation']=='correct' else entry['operation']), 'Crossed economic operation')
            expected+=effect['postings'];roots.add('source:'+effect['source']['source_hash'])
            if effect['operation']=='depreciation':
                require(effect['payload']['asset_entry_id'] in entries,'Missing original asset decision')
        require(entry['postings']==expected,'Changed original or exact counter-postings')
        postings.extend(dict(value,entry_id=entry['id'],sequence=entry['sequence']) for value in entry['postings'] if value['date'].startswith(year))
    require(postings==report['postings'], 'Changed year postings')
    for row in report['sources']:
        entry=entries.get(row['entry_id']);source=entry['effect']['source'] if entry and entry['effect'] else None
        require(source and entry['entry_hash']==row['entry_hash'] and all(source[k]==row[k] for k in ('source_hash','source_path','kind')), 'Missing or crossed reported source')
    require(all(row['entry_id'] in entries for row in report['assets']), 'Missing reported asset decision')
    for row in report.get('historical_assets',[]):
        roots.add('source:'+row['source']['source_hash'])
    current_year=None
    for entry in ordered:
        if entry['target']=='opening_year_values:'+year:
            current_year=entry if entry['effect'] else None
    projection=None
    if current_year:
        source=current_year['effect']['source']
        require(source['kind']=='opening_year_values','Crossed original year operation')
        projection=dict(schema_version=1,entry_id=current_year['id'],entry_hash=current_year['entry_hash'],
            source_hash=source['source_hash'],source_path=source['source_path'],coverage=source['coverage'],
            original_periods_preserved=True,cash_flow_created=False,new_input_vat_claim_created=False)
    require(report.get('historical_year_values')==projection,'Changed original year coverage projection')
    grouped={}
    for value in postings:
        key=(value['ledger'],value['category']);grouped[key]=grouped.get(key,0)+cents(value['amount'])
    categories=[dict(ledger=key[0],category=key[1],amount=money(amount)) for key,amount in sorted(grouped.items())]
    income=sum(v for (ledger,category),v in grouped.items() if ledger=='euer' and category in ('sales','vat_collected','vat_refund'))
    expense=-sum(v for (ledger,category),v in grouped.items() if ledger=='euer' and category not in ('sales','vat_collected','vat_refund'))
    output=sum(v for (ledger,category),v in grouped.items() if ledger=='vat' and category=='output_vat')
    iv=-sum(v for (ledger,category),v in grouped.items() if ledger=='vat' and category=='input_vat')
    complete=not report['issues']
    totals=dict(confirmed_income=money(income),confirmed_expenses=money(expense),confirmed_surplus=money(income-expense),
        euer_surplus=money(income-expense) if complete else None,confirmed_output_vat=money(output),confirmed_input_vat=money(iv),
        vat_balance=money(output-iv) if complete else None)
    require(report['categories']==categories and report['totals']==totals and report['complete_for_recorded_sources'] is complete
            and manifest['original_year_complete'] is complete, 'Changed year completeness or totals')
    return entries, roots


def verify_proofs(manifest, proofs, entries, roots):
    nodes={row['id']:row for row in proofs['nodes']}
    require(len(nodes)==len(proofs['nodes']) and list(nodes)==sorted(nodes), 'Duplicate or unordered proof node')
    originals={row['path']:row for row in manifest['originals']}
    require(len(originals)==len(manifest['originals']), 'Duplicate original descriptor')
    used=set();reachable=set();queue=list(roots);boundaries=set()
    def expect_original(node,digest):
        path='originals/'+digest+'.bin'
        require(path in node['originals'] and path in originals and originals[path]['sha256']==digest, 'Missing bound original')
    def embedded_links(value,node):
        if isinstance(value,list):
            for part in value:embedded_links(part,node)
        elif isinstance(value,dict):
            document=value.get('document_id')
            if document:
                ref='document:'+document;require(ref in node['links'],'Missing documentary original link')
                proof=nodes[ref]['payload']['proof']
                for name in ('payload_sha256','pdf_sha256','xml_sha256'):
                    if value.get(name) is not None:require(value[name]==proof[name],'Crossed document original hash')
            if value.get('receipt_id') and type(value.get('review_revision')) is int:
                ref='receipt:'+value['receipt_id']+':'+str(value['review_revision'])
                require(ref in node['links'],'Missing historical receipt link')
                public=nodes[ref]['payload']['public']
                for name in ('original_sha256','review_sha256'):
                    if value.get(name) is not None:require(value[name]==public[name],'Crossed historical receipt original hash')
            if isinstance(value.get('document'),dict) and value['document'].get('id'):
                doc=value['document'];ref='document:'+doc['id'];require(ref in node['links'],'Missing archived document')
                require(nodes[ref]['payload']['proof']['payload_sha256']==doc['payload_sha256'],'Changed archived document binding')
            if value.get('entry_id') and value.get('entry_sha256'):
                refs=[ref for ref in node['links'] if ref.startswith('component:') and ref.endswith(':'+value['entry_id'])]
                require(len(refs)==1 and nodes[refs[0]]['payload']['entry_sha256']==value['entry_sha256'],'Missing documentary predecessor')
            for name,part in value.items():
                if name.endswith('_json') and isinstance(part,str):part=decode(part.encode())
                embedded_links(part,node)
    while queue:
        key=queue.pop()
        if key in reachable:continue
        require(key in nodes, 'Missing linked source proof');reachable.add(key)
        node=nodes[key];payload=node['payload'];kind=node['kind']
        require(sha(payload)==node['payload_sha256'], 'Changed proof payload')
        require(node['links']==sorted(set(node['links'])) and node['originals']==sorted(set(node['originals'])), 'Noncanonical proof links')
        queue.extend(node['links']);used.update(node['originals'])
        require(set(node['originals'])<=set(originals), 'Unknown original file')
        if kind=='source':
            source=payload;tag=source['kind']
            require(key=='source:'+source['source_hash'] and sha({k:v for k,v in source.items() if k not in ('source_hash','payment_event')})==source['source_hash'], 'Crossed source hash')
            if source.get('payment_event'):
                event=source['payment_event'];ref='cash:'+event['id']
                require(ref in node['links'] and sha(nodes[ref]['payload'])==event['source']['source_hash'],'Missing original prepayment proof')
            if tag=='receipt':
                r=source['receipt'];ref='receipt:'+r['receipt_id']+':'+str(r['review_revision'])
                require(ref in node['links'] and nodes[ref]['payload']['public']==r,'Crossed receipt revision')
            elif tag=='cash':
                event=source['event'];ref='cash:'+event['id']
                require(ref in node['links'] and sha(nodes[ref]['payload'])==event['source']['source_hash'], 'Missing cash original proof')
                for unit in source['units']:
                    ref='component:'+unit['version']+':'+unit['entry_id']
                    require(ref in node['links'],'Missing documentary component')
                    entry=nodes[ref]['payload']['entry'];part=entry['lines'][unit['index']]
                    require(entry['id']==unit['entry_id'] and part['group_id']==unit['group_id']
                            and all(part[k]==unit[k] for k in ('net','tax')) and part['amount']==unit['gross']
                            and unit['unit_id']==sha(dict(version=unit['version'],entry_id=unit['entry_id'],index=unit['index'])), 'Changed exact documentary part')
            elif tag=='opening_asset':
                ref='asset:'+source['id'];require(ref in node['links'],'Missing historical asset original')
                asset=nodes[ref]['payload'];require(asset['content_hash']==source['entry_hash'] and asset['asset']==source['asset']
                    and asset['source_proof']==source['source_proof'] and asset['revision']==source['revision'],'Crossed historical asset')
                revisions=[nodes[v]['payload']['revision'] for v in node['links']]
                require(sorted(revisions)==list(range(1,source['revision']+1)),'Missing historical asset revision')
            elif tag=='opening_item_cash':
                ref='opening_item:'+source['entry_id'];item='opening_item:'+source['item_id']
                require(ref in node['links'] and item in node['links'],'Missing old item or actual payment')
                payment=nodes[ref]['payload'];old=nodes[item]['payload']
                require(payment['content_hash']==source['entry_hash'] and old['content_hash']==source['item_hash']
                    and payment['payload']['item_id']==old['id'] and source['prior_input_vat']==old['payload']['prior_input_vat'],'Crossed old item payment')
                require(source['proof'] in payment['proofs'],'Changed actual payment original')
            elif tag=='opening_year_values':
                ref='year_values:'+source['entry_id']
                require(ref in node['links'],'Missing original yearly journal decision')
                original=nodes[ref]['payload']['entry']
                require(original['content_hash']==source['entry_hash'] and original['entity_key']==source['id']
                    and original['revision']==source['revision'] and original['details']==source['details']
                    and original['proofs']==source['proofs'] and original['profile_ref']==source['profile_ref']
                    and original['payload']['coverage']==source['coverage'] and original['payload']['status']==source['status']
                    and original['payload']['attestations']==source['attestations'] and source['cash_movements']==[],
                    'Crossed original yearly journal projection')
                revisions=[nodes[v]['payload']['entry']['revision'] for v in node['links']]
                require(sorted(revisions)==list(range(1,source['revision']+1)),'Missing yearly source revision')
            elif tag in ('payroll_cash','travel_cash'):
                require(node['links']==[] and node['originals']==[], 'Private originals cross public financial boundary');boundaries.add(tag)
            else:raise ValueError('Unsupported source contract')
        elif kind=='receipt':
            public=payload['public'];proof=payload['proof'];review=proof['review']
            require(public['source_hash']==sha(proof) and review['revision']==public['review_revision']
                and sha(review['payload_json'])==review['payload_sha256']==public['review_sha256']
                and proof['receipt']['sha256']==public['original_sha256'],'Changed historical receipt proof')
            expect_original(node,public['original_sha256'])
        elif kind=='document':
            proof=payload['proof'];require(sha(payload['payload'])==proof['payload_sha256'],'Changed final document payload')
            expect_original(node,proof['pdf_sha256'])
            if proof['xml_sha256']:expect_original(node,proof['xml_sha256'])
        elif kind=='documentary_component':
            require(sha(payload['entry'])==payload['entry_sha256'],'Changed documentary decision')
            embedded_links(payload,node)
        elif kind=='historical_asset':
            require(sha({k:v for k,v in payload.items() if k!='content_hash'})==payload['content_hash'],'Changed asset original decision')
            expect_original(node,payload['source_proof']['original']['sha256'])
        elif kind=='opening_item':
            require(sha({k:v for k,v in payload.items() if k!='content_hash'})==payload['content_hash'],'Changed old item original decision')
            for original in payload['proofs']:expect_original(node,original['sha256'])
            previous=payload['previous_ref']
            if previous:
                ref='opening_item:'+previous['id']
                require(ref in nodes,'Missing original old-item revision')
                old=nodes[ref]['payload']
                require(old['content_hash']==previous['content_hash'] and old['revision']==previous['revision']==payload['revision']-1
                    and old['entity_key']==payload['entity_key'] and old['operation']==payload['operation']
                    and old['sequence']<payload['sequence'],'Crossed old-item revision history')
            else:require(payload['revision']==1,'Truncated original old-item revisions')
            if payload['operation']=='payment':
                ref='opening_item:'+payload['payload']['item_id']
                require(ref in nodes,'Missing original old invoice for payment')
                item=nodes[ref]['payload']
                require(item['operation']=='item' and item['entity_key']==payload['payload']['item_key']
                    and item['content_hash']==payload['payload']['item_hash'],'Crossed original old invoice payment')
                prior={}
                for row in sorted((n['payload'] for n in nodes.values() if n['kind']=='opening_item'),key=lambda r:r['sequence']):
                    if row['sequence']>=payload['sequence']:break
                    if row['operation']=='payment' and row['payload']['item_key']==item['entity_key']:
                        prior[row['entity_key']]=row
                paid=cents(item['details']['settled_before_start'])+sum(cents(r['payload']['amount']) for key,r in prior.items()
                    if key!=payload['entity_key'] and r['payload']['status']=='active')
                require(cents(payload['details']['settled_before'])==paid,'Missing prior actual payment original')
                require(cents(payload['details']['settled_after'])==paid+cents(payload['payload']['amount']),
                    'Changed original payment accumulation')
        elif kind=='year_values':
            entry=payload['entry'];acceptance=payload['acceptance']
            require(key=='year_values:'+entry['id'] and sha({k:v for k,v in entry.items() if k!='content_hash'})==entry['content_hash'],
                'Changed original year decision')
            command=decode(acceptance['request_json'].encode())
            require(acceptance['operation']=='confirm' and acceptance['user_id']==entry['created_by']
                and acceptance['request_id']==command['request_id'] and acceptance['request_hash']==sha(['confirm',command])
                and decode(acceptance['result_json'].encode())=={'entry_id':entry['id']} and command['confirmation'] is True,
                'Changed original year acceptance')
            require(all(command[k]==entry[k] for k in ('expected_revision','state_hash','entity_key','profile_ref','operation','payload','reason','preview_hash')),
                'Crossed original year command')
            preview={k:v for k,v in entry.items() if k not in ('id','sequence','revision','previous_hash','created_by','created_at','content_hash','preview_hash')}
            require(sha(preview)==entry['preview_hash'],'Changed original year preview')
            if entry['previous_ref']:
                previous=entry['previous_ref'];ref='year_values:'+previous['id']
                require(ref in node['links'],'Missing earlier yearly source revision')
                old=nodes[ref]['payload']['entry']
                require(old['content_hash']==previous['content_hash'] and old['revision']==previous['revision']==entry['revision']-1
                    and old['entity_key']==entry['entity_key'],'Crossed yearly source history')
            else:require(entry['revision']==1,'Truncated yearly source history')
            for original in entry['proofs']:expect_original(node,original['sha256'])
            journal=entry['payload']['ledger_proof']
            require(any(p['id']==journal['original_id'] and p['sha256']==journal['sha256']
                and p['entity_key']==entry['entity_key'] for p in entry['proofs']),'Missing independent period journal original')
            refs=entry['payload']['sources'];resolved=entry['resolved_sources']
            require(len(refs)==len(resolved),'Incomplete resolved original sources')
            for ref,source in zip(refs,resolved):
                require(all(ref[k]==source[k] for k in ('kind','accounts','cash_entry_keys','vat_entry_key')),'Crossed original journal identities')
                if ref['kind']=='opening_item':
                    linked='opening_item:'+ref['entry_id']
                    require(linked in node['links'],'Missing canonical old invoice decision')
                    old=nodes[linked]['payload']
                    require(old['operation']=='item' and old['content_hash']==ref['entry_hash']==source['source_ref']
                        and old['payload']==source['record'],'Crossed canonical old invoice')
                elif ref['kind']=='closed_trade':
                    require(ref['record']==source['record'],'Changed fully settled original invoice')
                    record=source['record']
                    bound=[record['invoice_proof'],record['cutover_proof']]+[p['proof'] for p in record['prior_payments']]+([record['prior_input_vat']['proof']] if record['prior_input_vat'] else [])
                    originals_by_id={p['id']:p for p in entry['proofs']}
                    exact=[]
                    for proof in bound:
                        original=originals_by_id[proof['original_id']]
                        require(original['sha256']==proof['sha256'] and original['entity_key']==entry['entity_key'],'Crossed settled original proof')
                        exact.append(original)
                    require(sha(dict(record=record,proofs=exact))==source['source_ref'],'Changed settled source identity')
                else:raise ValueError('Unsupported historical year source')
        elif kind=='cash_original':
            if 'receipt' in payload:
                ref='receipt:'+payload['receipt']['id']+':'+str(payload['review']['revision'])
                require(ref in node['links'] and nodes[ref]['payload']['proof']==payload,'Missing cash receipt original')
            else:
                for proof in payload['documents']:
                    ref='document:'+proof['document_id']
                    require(ref in node['links'] and nodes[ref]['payload']['proof']==proof,'Missing cash invoice original')
        else:raise ValueError('Unsupported proof node')
    require(reachable==set(nodes),'Unrelated or unbound proof included')
    require(used==set(originals),'Unrelated or missing original file')
    require(sorted(boundaries)==manifest['private_source_boundaries'] and manifest['private_personnel_originals_included'] is False,'Changed private-source boundary')
    for entry in entries.values():
        if entry['effect']:
            source=entry['effect']['source'];require(nodes['source:'+source['source_hash']]['payload']==source,'Crossed decision/source payload')


def _verify(raw, expected_sha256=None):
    require(isinstance(raw,bytes) and 0<len(raw)<=MAX_BYTES, 'Invalid archive size')
    require(isinstance(expected_sha256,str) and HEX.fullmatch(expected_sha256),
        'Separately authenticated archive SHA-256 is required; intrinsic dependency completeness is not established')
    require(sha(raw)==expected_sha256,'ZIP differs from trusted separate hash')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos=archive.infolist();names=[v.filename for v in infos]
        required={'manifest.json','report.json','postings.csv','journal.json','proofs.json','README.txt','verify_year_package.py'}
        require(len(names)==len(set(names)) and len(names)<=MAX_FILES and required<=set(names),'Invalid archive entry list')
        require(sum(v.file_size for v in infos)<=MAX_BYTES,'Oversized uncompressed content')
        require(all(not v.is_dir() and not v.flag_bits&1 and v.compress_type==zipfile.ZIP_STORED
            and (v.filename in required or re.fullmatch(r'originals/[a-f0-9]{64}\.bin',v.filename)) for v in infos),'Unsafe archive path or encoding')
        require(archive.getinfo('manifest.json').file_size<=8*1024*1024,'Oversized manifest')
        manifest=decode(archive.read('manifest.json'))
        require(manifest['format']=='smartplan-year-evidence-v2' and type(manifest['schema_version']) is int and manifest['schema_version']==1
            and ID.fullmatch(manifest['instance_id']) and ID.fullmatch(manifest['export_id'])
            and manifest['official_tax_return'] is False and manifest['datev_certified'] is False,'Unsupported package identity')
        require(manifest['intrinsic_dependency_closure'] is False
            and manifest['required_trust']=='separately_authenticated_archive_sha256',
            'Missing explicit legacy source completeness boundary')
        files={row['path']:row for row in manifest['files']}
        require(len(files)==len(manifest['files']) and set(files)==set(names)-{'manifest.json'},'Incomplete file manifest')
        for path,row in files.items():
            require(type(row['size']) is int and row['size']==archive.getinfo(path).file_size
                and sha(archive.read(path))==row['sha256'],'Changed or missing archive file')
        for original in manifest['originals']:
            require(original['path']=='originals/'+original['sha256']+'.bin'
                and all(original[k]==files[original['path']][k] for k in ('size','sha256')),'Crossed original file mapping')
        report=decode(archive.read('report.json'));journal=decode(archive.read('journal.json'));proofs=decode(archive.read('proofs.json'))
        require(sha(report)==manifest['report_sha256'] and sha(archive.read('postings.csv'))==manifest['csv_sha256']
            and report['year']==manifest['year'] and report['period'] is None,'Changed frozen year report')
        require(csv_bytes(report)==archive.read('postings.csv'),'CSV differs from original year postings')
        entries,roots=verify_journal(manifest,report,journal)
        verify_proofs(manifest,proofs,entries,roots)
        return dict(format=manifest['format'],instance_id=manifest['instance_id'],export_id=manifest['export_id'],year=manifest['year'],
            sha256=sha(raw),files=len(files),originals=len(manifest['originals']),journal_decisions=len(journal['decisions']),
            original_year_complete=manifest['original_year_complete'],private_source_boundaries=manifest['private_source_boundaries'],
            verified=True,official_tax_return=False,intrinsic_dependency_closure=False,
            verification_basis='separately_authenticated_archive_sha256_and_structural_checks')


def verify(raw, expected_sha256=None):
    try:
        return _verify(raw,expected_sha256)
    except (KeyError,TypeError,IndexError,AttributeError,OverflowError,zipfile.BadZipFile,UnicodeError,json.JSONDecodeError) as error:
        raise ValueError('Invalid or incomplete year package') from error


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archive');parser.add_argument('--sha256',required=True)
    args=parser.parse_args();path=Path(args.archive)
    require(0<path.stat().st_size<=MAX_BYTES,'Invalid archive size')
    result=verify(path.read_bytes(),args.sha256);print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
