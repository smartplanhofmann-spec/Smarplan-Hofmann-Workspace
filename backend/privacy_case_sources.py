"""Bounded, structured subject sources; never an automatic completeness claim."""
import hashlib
import json
import re
import sqlite3

from core import Problem, canonical
from business_foundation import BusinessFoundation, _fresh, require_permission
from business_operations import identifier
from company_export_archive import structure
from company_export_catalog import COLUMNS, EXCLUDED, OMITTED_COLUMNS, policy

MAX_SOURCES=1000
PRIVATE_PREFIX='business_privacy_case_'
MANUAL_AREAS=('free_text','originals_and_third_parties','historical_receipts','external_systems',
              'recipients_and_copies','backups','retention_and_legal_holds')


def sha(value):
    return hashlib.sha256(value if isinstance(value,bytes) else canonical(value).encode()).hexdigest()


def subject(office,actor,kind,subject_id):
    identifier(subject_id)
    fresh=require_permission(office,actor,'privacy.manage')
    if kind=='customer':
        value=BusinessFoundation(office).contact(fresh,subject_id)
        return fresh,dict(kind=kind,id=subject_id,label=value['name'],revision=value['revision'])
    if kind=='employee':
        from business_personnel_workflow import PersonnelWorkflow
        fresh,value=PersonnelWorkflow(office)._employee(fresh,subject_id)
        return fresh,dict(kind=kind,id=subject_id,label=value['name'],revision=value['revision'],user_id=value['user_id'])
    if kind=='user':
        if fresh['role']!='owner':raise Problem(403,'Benutzerbezogene Datenschutzfälle benötigen die Geschäftsführung.')
        row=office.db.execute('SELECT id,email FROM users WHERE id=?',(subject_id,)).fetchone()
        if row is None:raise Problem(404,'Betroffener Benutzer nicht verfügbar.')
        return fresh,dict(kind=kind,id=subject_id,label=row['email'])
    raise Problem(400,'Kontakt, Mitarbeiter oder Benutzer als Betroffenenanker angeben.')


def access(office,actor,table,row=None,*,export=False):
    fresh=require_permission(office,actor,'privacy.manage')
    if table not in COLUMNS or table in EXCLUDED or table.startswith(PRIVATE_PREFIX) or table=='business_company_exports':
        raise Problem(403,'Diese Quelle benötigt eine gesonderte geschützte Prüfung.')
    classification=policy(table)
    if table.startswith('business_bank_'):
        for permission in ('bank.read','accounting.read','finance.read'):
            require_permission(office,fresh,permission)
    if table.startswith('business_resource_'):
        for permission in ('planning.read','planning.write'):
            require_permission(office,fresh,permission)
    if table.startswith('business_purchase_') or table.startswith('business_supplier_return'):
        order_id=None
        if row:
            if table=='business_purchase_orders':order_id=row['id']
            elif row.get('order_id'):order_id=row['order_id']
            elif row.get('receipt_id'):
                source=office.db.execute('SELECT order_id FROM business_purchase_receipts WHERE id=?',(row['receipt_id'],)).fetchone()
                if source is None:raise Problem(409,'Bestellbezogene Quelle ist nicht mehr eindeutig verfügbar.')
                order_id=source['order_id']
            elif row.get('return_id'):
                source=office.db.execute('SELECT order_id FROM business_supplier_returns WHERE id=?',(row['return_id'],)).fetchone()
                if source is None:raise Problem(409,'Retoure besitzt keine verfügbare Bestellquelle.')
                order_id=source['order_id']
            else:raise Problem(403,'Bestellquelle benötigt eine gesonderte geschützte Zuordnung.')
        project_id=None
        if order_id:
            from business_purchasing import Purchasing
            project_id=Purchasing(office)._row(order_id)['project_id']
        for permission in ('inventory.read','finance.read'):
            require_permission(office,fresh,permission,project_id)
    project=row.get('project_id') if row else None
    if project is not None:
        identifier(project);office.project(fresh,project)
    if classification['category']=='personnel':
        require_permission(office,fresh,'personnel.read')
        if export:require_permission(office,fresh,'personnel.export')
    elif classification['category']=='financial':
        require_permission(office,fresh,'finance.read',project)
        if table.startswith('business_accounting') or table.startswith('business_euer'):
            require_permission(office,fresh,'accounting.read')
    elif classification['category'] in ('security','system'):
        if fresh['role']!='owner':raise Problem(403,'Geschützte Systemquelle benötigt die Geschäftsführung.')
    elif table in ('customers','business_contact_extras','business_contact_people','business_contact_addresses'):
        contact=row.get('customer_id') or row.get('id') if row else None
        if contact:BusinessFoundation(office)._contact_scope(fresh,contact)
        else:require_permission(office,fresh,'contacts.read')
    elif table.startswith('business_project_milestone'):
        require_permission(office,fresh,'planning.read',project)
        if fresh['role']!='owner':raise Problem(403,'Die vollständige Quellenzeile benötigt die Geschäftsführung.')
    else:
        require_permission(office,fresh,'documents.read',project)
        # Raw source records can contain restricted classifications or nested
        # personnel fields. Only the owner may inspect unclassified raw rows;
        # delegated reviewers still receive the explicit blocked-table list.
        if fresh['role']!='owner':raise Problem(403,'Die vollständige Quellenzeile benötigt die Geschäftsführung.')
    if table.startswith('business_assistant'):
        require_permission(office,fresh,'assistant.use',project)
    return fresh


def _value(row,table):
    result={}
    for key,value in dict(row).items():
        if key in OMITTED_COLUMNS.get(table,set()):continue
        if isinstance(value,(bytes,bytearray,memoryview)):
            raw=bytes(value);result[key]=dict(binary=True,size=len(raw),sha256=sha(raw))
        elif isinstance(value,str) and key.endswith(('_json','payload','result')):
            try:result[key]=json.loads(value)
            except ValueError:result[key]=value
        else:result[key]=value
    return result


def _descriptor(table,row,keys):
    primary={name:row[name] for name in keys}
    value=_value(row,table)
    return dict(key=sha([table,primary]),table=table,primary_key=primary,sha256=sha(value),
        category=policy(table)['category'],binary_fields=[key for key,item in value.items() if isinstance(item,dict) and item.get('binary') is True])


def inventory(office,actor,kind,subject_id):
    fresh,person=subject(office,actor,kind,subject_id)
    structures=structure(office)
    anchors={}
    if kind=='customer':anchors['customers']={subject_id}
    if kind=='employee':anchors.update(business_employees={subject_id},users={person['user_id']})
    if kind=='user':anchors['users']={subject_id}
    candidates={};blocked=set();skipped=set();truncated=False
    # Incoming foreign-key closure covers new structured modules without
    # substring-searching arbitrary free text or guessing personal identities.
    for _ in range(5):
        changed=False
        for item in structures:
            table=item['table'];names={v['name'] for v in item['columns']}
            if table in EXCLUDED or table.startswith(PRIVATE_PREFIX) or table=='business_company_exports':
                skipped.add(table);continue
            try:access(office,fresh,table)
            except Problem:blocked.add(table);continue
            keys=[v['name'] for v in sorted(item['columns'],key=lambda v:v['primary_key_order']) if v['primary_key_order']]
            if not keys:skipped.add(table);continue
            conditions=[];parameters=[]
            def match(column,values):
                values=sorted(values)
                if values:
                    conditions.append('"'+column+'" IN ('+','.join('?' for _ in values)+')');parameters.extend(values)
            if table in anchors and 'id' in names:match('id',anchors[table])
            for relation in item['relationships']:
                if relation['target_column']=='id' and relation['target_table'] in anchors:
                    match(relation['column'],anchors[relation['target_table']])
            # Responsible users are a typed field of the milestone record,
            # including each complete historical record. Query that JSON key
            # directly; text mentioning an ID is not a subject relationship.
            if table in ('business_project_milestones','business_project_milestone_versions') and anchors.get('users'):
                users=sorted(anchors['users'])
                fields=('assignee_id','created_by','updated_by') if table.endswith('_versions') else ('assignee_id',)
                for field in fields:
                    reference=("json_extract(payload_json,'$."+field+"')" if isinstance(office.db,sqlite3.Connection)
                               else "(CAST(payload_json AS JSONB)->>'"+field+"')")
                    conditions.append(reference+' IN ('+','.join('?' for _ in users)+')')
                    parameters.extend(users)
            # Existing polymorphic custom fields have no database FK.
            if {'entity_type','entity_id'}<=names:
                for entity,target in (('contact','customers'),('project','projects'),('asset','business_assets')):
                    values=sorted(anchors.get(target,set()))
                    if values:
                        conditions.append('("entity_type"=? AND "entity_id" IN ('+','.join('?' for _ in values)+'))')
                        parameters.extend([entity,*values])
            if not conditions:continue
            rows=office.db.execute('SELECT * FROM "'+table+'" WHERE '+' OR '.join(conditions)+' LIMIT 1001',tuple(parameters)).fetchall()
            if len(rows)>1000:raise Problem(413,'Zu viele strukturierte Quellen für einen geprüften Fall; Umfang zunächst gezielt eingrenzen.')
            for row in rows:
                try:access(office,fresh,table,dict(row))
                except Problem:blocked.add(table);continue
                descriptor=_descriptor(table,row,keys)
                if descriptor['key'] in candidates:continue
                candidates[descriptor['key']]=descriptor;changed=True
                if 'id' in names and isinstance(row['id'],str):anchors.setdefault(table,set()).add(row['id'])
                if len(candidates)>MAX_SOURCES:raise Problem(413,'Fall überschreitet die geprüfte Quellenzahl; kein Teilbestand wurde als vollständig übernommen.')
        if not changed:break
    else:truncated=True
    result=dict(subject=person,sources=sorted(candidates.values(),key=lambda v:(v['table'],v['key'])),
        blocked_tables=sorted(blocked),manual_tables=sorted(skipped),closure_limit_reached=truncated,
        inventory=[{key:policy(item['table'])[key] for key in ('table','category','purpose','sensitive','retention_basis','retention_days')} for item in structures],
        completeness='manual_review_required',manual_areas=list(MANUAL_AREAS))
    result['sha256']=sha({key:value for key,value in result.items() if key!='subject'})
    return result


def resolve(office,actor,descriptor,*,export=False,check_hash=True):
    if not isinstance(descriptor,dict) or descriptor.get('table') not in COLUMNS:
        raise Problem(400,'Geprüfte Quellenreferenz erwartet.')
    table=descriptor['table'];keys=descriptor.get('primary_key')
    if not isinstance(keys,dict) or not keys or set(keys)-set(COLUMNS[table].split(',')):
        raise Problem(400,'Strukturierter Quellenschlüssel erwartet.')
    access(office,actor,table)
    row=office.db.execute('SELECT * FROM "'+table+'" WHERE '+' AND '.join('"'+key+'"=?' for key in keys),tuple(keys.values())).fetchone()
    if row is None:raise Problem(409,'Verknüpfte Quelle ist nicht mehr verfügbar; Bestandsaufnahme erneuern.')
    access(office,actor,table,dict(row),export=export)
    actual=_descriptor(table,row,list(keys))
    if actual['key']!=descriptor.get('key') or check_hash and actual['sha256']!=descriptor.get('sha256'):
        raise Problem(409,'Quelle wurde geändert; Entscheidung mit aktuellem Stand erneut prüfen.')
    return _value(row,table),{key:bytes(value) for key,value in dict(row).items()
        if key not in OMITTED_COLUMNS.get(table,set()) and isinstance(value,(bytes,bytearray,memoryview))}
