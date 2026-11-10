"""Hash-only inspection of accepted legacy report captures, never an upload.

Float coordinates are represented by their exact IEEE-754 binary64 bytes in
this NEW proof contract. The archived legacy request hash and its signed data
are independently verified under their original encoding, without rewriting.
"""
import json
import math
import re
import struct

from core import Problem, canonical, digest

FEATURE='offline_service_report_recovery'
PATH='/offline/recovery/service-report'
KIND='service_report_capture'


def proof_hash(value):
    def typed(item):
        if type(item) is float:
            if not math.isfinite(item):raise ValueError('Nonfinite original coordinate')
            return {'$float64':struct.pack('>d',item).hex()}
        if isinstance(item,list):return [typed(v) for v in item]
        if isinstance(item,dict):return {k:typed(v) for k,v in item.items()}
        return item
    return digest(canonical(typed(value)))


def lookup(office,actor,data):
    from business_offline_binding import binding, _identifier
    from business_foundation import require_permission
    from business_operations import BusinessOperations
    from business_offline_reports import ACTION, validate_row
    fields={'schema_version','nonce','kind','project_id','entry_id','request_id','capture_hash'}
    if (not isinstance(data,dict) or set(data)!=fields or type(data['schema_version']) is not int
            or data['schema_version']!=4 or data['kind']!=KIND):
        raise Problem(400,'Nur Kennungen und Originalhash zum lesenden Protokollabgleich senden.')
    for name in ('nonce','project_id','entry_id','request_id'):_identifier(data[name],name)
    fingerprint=data['capture_hash']
    if not isinstance(fingerprint,str) or not re.fullmatch('[a-f0-9]{64}',fingerprint):
        raise Problem(400,'Eindeutigen ursprünglichen SHA-256-Nachweis angeben.')
    encoded=canonical(data)
    if len(encoded.encode())>4096:raise Problem(413,'Protokollabgleich ist zu groß.')
    with office.lock,office.db:
        fresh=require_permission(office,actor,'documents.read',data['project_id'])
        scope=binding(office,fresh,required=True)
        prior=office.db.execute('SELECT request_hash,result_json FROM business_operations_requests '
            'WHERE user_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
        if prior is None:
            raise Problem(404,'Keine passende ursprüngliche Protokollannahme gefunden. Der lokale Auftrag bleibt ungeklärt.')
        row=office.db.execute('SELECT * FROM business_operation_entries WHERE id=? AND project_id=?',
            (data['entry_id'],data['project_id'])).fetchone()
        if row is None:raise Problem(409,'Der ursprüngliche Protokollauftrag gehört zu einer anderen Archivfassung.')
        try:
            # Validate exact old signature/source/time/PDF under its original
            # contract before building the independently typed read-only proof.
            validate_row(row)
            result=BusinessOperations(office)._entry(row)
            proof=result['offline_capture']
            if (result['kind']!='service' or result['status']!='signed' or result['revision']!=2
                    or result['created_by']!=fresh['id'] or result['updated_by']!=fresh['id']
                    or result['signed_by']!=fresh['id'] or proof['request_id']!=data['request_id']
                    or prior['request_hash']!=proof['request_hash']
                    or json.loads(prior['result_json'])!=result):
                raise ValueError('Original receipt/archive disagreement')
            archived=office.db.execute('SELECT payload_json FROM business_operation_versions WHERE '
                "kind='entry' AND object_id=? AND project_id=? AND revision=2",
                (data['entry_id'],data['project_id'])).fetchone()
            if archived is None or json.loads(archived['payload_json'])!=result:
                raise ValueError('Missing original signed version')
            capture=dict(request_id=proof['request_id'],entry_id=result['id'],content=proof['content'],
                content_hash=proof['content_hash'],signer=result['signer'],strokes=result['strokes'],signed_at=result['signed_at'])
            actual=proof_hash([ACTION,data['project_id'],data['entry_id'],capture])
            if actual!=fingerprint:raise ValueError('Different original capture')
            signature=proof_hash({k:capture[k] for k in ('content_hash','signer','strokes','signed_at')})
            original=dict(schema_version=1,entry_id=result['id'],project_id=result['project_id'],
                request_id=data['request_id'],request_hash=prior['request_hash'],capture_hash=actual,
                actor_id=fresh['id'],revision=2,content_hash=proof['content_hash'],
                archive_content_hash=result['content_hash'],signature_sha256=signature,pdf_sha256=result['pdf_sha256'],
                signed_at=result['signed_at'],received_at=proof['received_at'])
        except (TypeError,KeyError,ValueError,Problem):
            raise Problem(409,'Die ursprüngliche unterschriebene Protokollfassung ist nicht unverändert verfügbar.') from None
        return dict(schema_version=4,nonce=data['nonce'],lookup_hash=digest(encoded),binding=scope,
            kind=KIND,project_id=data['project_id'],entry_id=data['entry_id'],request_id=data['request_id'],
            capture_hash=fingerprint,original=original)
