"""Portable, bounded company ZIP evidence; never imports or executes an archive."""
import hashlib
import io
from pathlib import Path
import re
import sqlite3
import tempfile
import zipfile

from core import Problem, canonical
from company_export_verify import verify
from company_export_catalog import CATALOG_VERSION, COLUMNS, EXCLUDED, OMITTED_COLUMNS, OPTIONAL_COLUMNS, catalog, policy

MAX_SOURCE_BYTES=256*1024*1024
MAX_ARCHIVE_BYTES=128*1024*1024
MAX_ROWS=250000
MAX_FILES=50000
NAME=re.compile(r'[a-z_][a-z0-9_]*')
HASH=re.compile(r'[a-f0-9]{64}')


def sha(value):
    return hashlib.sha256(value if isinstance(value,bytes) else value.encode('utf-8')).hexdigest()


def catalog_sha256():
    return sha(canonical(dict(version=CATALOG_VERSION,tables=catalog())))


def structure(office):
    from business_schema import _tables
    tables=sorted(_tables(office)); result=[]
    for table in tables:
        if table=='sqlite_sequence':continue
        if table not in COLUMNS or not NAME.fullmatch(table):
            raise Problem(409,'Der Exportkatalog muss für die aktuelle Datenstruktur ergänzt werden.')
        if isinstance(office.db,sqlite3.Connection):
            columns=[dict(name=row['name'],type=row['type'],primary_key_order=row['pk']) for row in office.db.execute('PRAGMA table_info('+table+')')]
            relations=[]
            for row in office.db.execute('PRAGMA foreign_key_list('+table+')'):
                relations.append(dict(constraint=str(row['id']),ordinal=row['seq'],column=row['from'],target_table=row['table'],target_column=row['to']))
        else:
            columns=[dict(name=row['column_name'],type=row['data_type'],primary_key_order=0) for row in office.db.execute(
                "SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=? ORDER BY ordinal_position",(table,))]
            keys=office.db.execute("SELECT a.attname,k.ordinality FROM pg_index i JOIN pg_class r ON r.oid=i.indrelid "
                "JOIN pg_namespace n ON n.oid=r.relnamespace CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum,ordinality) "
                "JOIN pg_attribute a ON a.attrelid=r.oid AND a.attnum=k.attnum WHERE i.indisprimary AND n.nspname='public' AND r.relname=?",(table,)).fetchall()
            order={row[0]:row[1] for row in keys}
            for column in columns:column['primary_key_order']=order.get(column['name'],0)
            relations=[]
            for row in office.db.execute("SELECT c.conname,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c "
                    "JOIN pg_class r ON r.oid=c.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace "
                    "WHERE c.contype='f' AND n.nspname='public' AND r.relname=? ORDER BY c.conname",(table,)):
                match=re.search(r'FOREIGN KEY \(([^)]+)\) REFERENCES ([a-z_][a-z0-9_]*)\(([^)]+)\)',row['definition'])
                if not match:raise Problem(409,'Unbekannte Datenbeziehung benötigt eine Exportprüfung.')
                local=[v.strip().strip('"') for v in match[1].split(',')]; foreign=[v.strip().strip('"') for v in match[3].split(',')]
                for index,(left,right) in enumerate(zip(local,foreign)):
                    relations.append(dict(constraint=row['conname'],ordinal=index,column=left,target_table=match[2],target_column=right))
        names={v['name'] for v in columns};expected=set(COLUMNS[table].split(','))
        if not expected<=names or names-expected-OPTIONAL_COLUMNS.get(table,set()):
            raise Problem(409,'Der Exportkatalog muss für neue oder geänderte Datenfelder geprüft werden.')
        value=policy(table);value['columns']=columns
        value['row_count']=office.db.execute('SELECT COUNT(*) FROM "'+table+'"').fetchone()[0]
        for relation in relations:
            relation['target_included']=relation['target_table'] in COLUMNS and relation['target_table'] not in EXCLUDED
        value['relationships']=relations;result.append(value)
    return result


README='''SMARTPLAN – PORTABLER UNTERNEHMENSEXPORT

Dieses ZIP enthält Fachdatensätze als UTF-8-JSONL unter data/, das Dateninventar
und Beziehungen in manifest.json sowie unveränderte Binärdateien unter files/.
Der Originaldateiname steht im verknüpften Datensatz/Originalverzeichnis.
Zusammengesetzte Plan- und E-Mail-Originale stehen unter originals/.

Personen-, Personal-, Lohn-, Bank- und gegebenenfalls Gesundheitsangaben sind
enthalten. Das Archiv ist nicht verschlüsselt: ausschließlich in eigener,
geschützter Ablage aufbewahren und an ausdrücklich berechtigte Empfänger geben.
Die Software hat nichts an einen Empfänger oder externen Anbieter gesendet.

Passwörter, MFA-/OAuth-/Sitzungs-/Gerätegeheimnisse, Providerkonfiguration und
technische Wiederholungsquittungen fehlen ausdrücklich. Das ist ein portabler
Fachexport, kein unmittelbar wiederherstellbares Datenbank-Backup und kein
vollständiges Replay-/Importpaket. Ein gesondertes Datenbank-Backup und dessen
Schlüssel bleiben für einen originalgetreuen Wiederanlauf erforderlich.

Private Arbeitsinhalte und zeitlich befristete Personenexporte aus Datenschutz-
fällen fehlen ebenfalls bewusst; ihre enge Fallfreigabe und Löschfristen dürfen
durch diesen Gesamtexport nicht umgangen werden. Minimale Fall-/Löschhashnachweise
bleiben im Dateninventar und in den exportierten Metadaten nachvollziehbar.

Externe Dateien, die nur als Verweis gespeichert sind, werden nicht automatisch
heruntergeladen. Aufbewahrung, Übergabe, Widerruf externer Zugänge und eventuelle
spätere Löschung brauchen einen gesonderten dokumentierten Operatorplan.

Zuerst den SHA-256 des ZIP mit dem separat in Smartplan angezeigten Hash
vergleichen. Für die Inhaltsprüfung den Prüfer aus der vertrauenswürdigen
Softwareinstallation verwenden; der mitgelieferte identische Prüfer darf erst
nach dieser Herkunftsprüfung verwendet werden. Keine fremden ZIP-Skripte starten.
Prüfung mit der ausgelieferten Software:
python verify_archive.py DATEI.zip --instance-id INSTANZ-ID
Der Prüfer kontrolliert Inhaltshashes, Dateiliste, JSONL-Zeilen und Zuordnung.
Das ist keine elektronische Signatur oder fachliche Steuerprüfung.
'''


class Builder:
    def __init__(self):
        self.stream=io.BytesIO();self.zip=zipfile.ZipFile(self.stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)
        self.files=[];self.total=0

    def add(self,path,content,*,media_type='application/octet-stream'):
        size=len(content);self.total+=size
        if self.total>MAX_SOURCE_BYTES or len(self.files)>=MAX_FILES:
            raise Problem(413,'Unternehmensbestand überschreitet die geprüfte Exportgrenze; kein Teilarchiv wurde gespeichert.')
        self.zip.writestr(path,content)
        self.files.append(dict(path=path,size=size,sha256=sha(content),media_type=media_type))
        if self.stream.tell()>MAX_ARCHIVE_BYTES:raise Problem(413,'Unternehmensarchiv überschreitet die geprüfte Größe.')
        return dict(path=path,size=size,sha256=sha(content))

    def jsonl(self,path,source,size,digest):
        self.total+=size
        if self.total>MAX_SOURCE_BYTES or len(self.files)>=MAX_FILES:raise Problem(413,'Unternehmensdaten überschreiten die geprüfte Exportgrenze.')
        source.seek(0)
        with self.zip.open(path,'w') as dest:
            while chunk:=source.read(1024*1024):dest.write(chunk)
        self.files.append(dict(path=path,size=size,sha256=digest,media_type='application/x-ndjson'))


def _blob(builder,table,index,column,row,value):
    raw=bytes(value);computed=sha(raw)
    hash_column={'pdf':'pdf_sha256','xml':'xml_sha256','original':'sha256','data':'sha256','content':'sha256','preview':'preview_sha256'}.get(column)
    if table=='business_bank_statements' and column=='original':hash_column='file_sha256'
    if column=='pdf' and 'pdf_hash' in row:hash_column='pdf_hash'
    if hash_column and row.get(hash_column) is not None and row[hash_column]!=computed:
        raise Problem(409,'Ein Original stimmt nicht mit seiner gespeicherten Prüfsumme überein.')
    extension='pdf' if column=='pdf' else 'xml' if column=='xml' else 'bin'
    if column in ('original','content'):
        extension={'application/pdf':'pdf','image/png':'png','image/jpeg':'jpg','image/webp':'webp'}.get(row.get('media_type'),'bin')
    path=f'files/{table}/{index:08d}-{column}.{extension}'
    return {'$file':path,**{key:value for key,value in builder.add(path,raw,media_type=row.get('media_type') or ('application/pdf' if extension=='pdf' else 'application/octet-stream')).items() if key!='path'}}


def _assembled_originals(office,builder,tables):
    result=[]
    for parent,child,foreign in (('plan_imports','plan_import_chunks','import_id'),('inquiry_attachments','inquiry_attachment_chunks','attachment_id')):
        if parent not in tables:continue
        for source in office.db.execute('SELECT id,filename,media_type,size,sha256,status FROM '+parent+' ORDER BY id'):
            if source['status'] in ('uploading','deleted'):
                result.append(dict(table=parent,id=source['id'],filename=source['filename'],status=source['status'],complete=False));continue
            chunks=list(office.db.execute('SELECT chunk_index,data,sha256 FROM '+child+' WHERE '+foreign+'=? ORDER BY chunk_index',(source['id'],)))
            if any(row['chunk_index']!=index or sha(bytes(row['data']))!=row['sha256'] for index,row in enumerate(chunks)):
                raise Problem(409,'Originalabschnitte sind unvollständig oder beschädigt.')
            raw=b''.join(bytes(row['data']) for row in chunks)
            if len(raw)!=source['size'] or sha(raw)!=source['sha256']:
                raise Problem(409,'Ein gespeichertes Original kann nicht vollständig rekonstruiert werden.')
            value=builder.add('originals/'+parent+'/'+source['id']+'.bin',raw,media_type=source['media_type'])
            result.append(dict(value,table=parent,id=source['id'],filename=source['filename'],status=source['status'],complete=True))
    return result


def build(office,*,instance_id,export_id,created_at,created_by,reason,inventory):
    builder=Builder();row_count=0;exported=[]
    try:
        for table in inventory:
            if not table['included']:continue
            name=table['table'];names=[v['name'] for v in table['columns'] if v['name'] not in table['omitted_columns']]
            keys=[v['name'] for v in sorted(table['columns'],key=lambda v:v['primary_key_order']) if v['primary_key_order']]
            statement='SELECT '+','.join('"'+v+'"' for v in names)+' FROM "'+name+'"'
            if keys:statement+=' ORDER BY '+','.join('"'+key+'"' for key in keys)
            count=0;size=0;digest=hashlib.sha256()
            with tempfile.SpooledTemporaryFile(max_size=8*1024*1024) as rows:
                for source in office.db.execute(statement):
                    raw=dict(source);value={}
                    for column,item in raw.items():
                        value[column]=_blob(builder,name,count,column,raw,item) if isinstance(item,(bytes,bytearray,memoryview)) else item
                    encoded=(canonical(value)+'\n').encode('utf-8');rows.write(encoded);digest.update(encoded);size+=len(encoded);count+=1;row_count+=1
                    if row_count>MAX_ROWS or size+builder.total>MAX_SOURCE_BYTES:
                        raise Problem(413,'Unternehmensdaten überschreiten die geprüfte Exportgrenze; keine Teilsicherung gespeichert.')
                if count!=table['row_count']:raise Problem(409,'Datenbestand wurde während der Exportprüfung verändert.')
                path='data/'+name+'.jsonl';builder.jsonl(path,rows,size,digest.hexdigest())
            exported.append(dict(table=name,path=path,row_count=count,sha256=digest.hexdigest(),columns=names))
        originals=_assembled_originals(office,builder,{value['table'] for value in inventory})
        builder.add('README.txt',README.encode(),media_type='text/plain')
        builder.add('verify_archive.py',Path(__file__).with_name('company_export_verify.py').read_bytes(),media_type='text/x-python')
        manifest=dict(format='smartplan-company-export',schema_version=1,catalog_version=CATALOG_VERSION,catalog_sha256=catalog_sha256(),
            export_id=export_id,instance_id=instance_id,created_at=created_at,created_by=created_by,reason=reason,
            snapshot_consistency='sqlite_immediate_or_postgresql_repeatable_read_with_application_write_lock',
            verification_scope='archive_hashes_jsonl_counts_and_relationship_metadata',
            complete_for_classified_database_business_records=True,database_restore_supported=False,external_only_files_downloaded=False,
            technical_request_replay_included=False,authentication_credentials_included=False,
            external_copy_note='Canonical DB originals included; externally referenced-only files require a separate handover.',
            limits=dict(max_source_bytes=MAX_SOURCE_BYTES,max_archive_bytes=MAX_ARCHIVE_BYTES,max_rows=MAX_ROWS),
            inventory=inventory,tables=exported,originals=originals,entries=builder.files,
            row_count=row_count,table_count=len(exported),file_count=sum(value['path'].startswith(('files/','originals/')) for value in builder.files))
        encoded=canonical(manifest).encode();builder.zip.writestr('manifest.json',encoded);builder.zip.close();raw=builder.stream.getvalue()
        if len(raw)>MAX_ARCHIVE_BYTES or len(encoded)>4*1024*1024:raise Problem(413,'Unternehmensarchiv überschreitet die geprüfte Größe.')
        verify(raw,instance_id=instance_id)
        return raw,manifest
    finally:builder.zip.close();builder.stream.close()


if __name__=='__main__':
    from company_export_verify import main
    main()
