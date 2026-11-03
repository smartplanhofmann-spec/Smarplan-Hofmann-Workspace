"""Standalone standard-library verifier for Smartplan company export ZIPs.

No extraction, script execution, provider calls or database access. This checks
internal integrity; compare the ZIP hash with the original separate receipt to
establish provenance. A self-consistent ZIP is not an electronic signature.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
import zlib

MAX_SOURCE_BYTES=256*1024*1024
MAX_ARCHIVE_BYTES=128*1024*1024
MAX_FILES=50000
MAX_ROWS=250000
HASH=re.compile(r'[a-f0-9]{64}')
NAME=re.compile(r'[a-z_][a-z0-9_]*')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON field')
        result[key]=value
    return result


def _decode(value):
    def reject(_):raise ValueError('Non-finite JSON number')
    return json.loads(value,object_pairs_hook=_unique,parse_constant=reject)


def _verify(raw,*,instance_id=None):
    if not isinstance(raw,bytes) or not 1<=len(raw)<=MAX_ARCHIVE_BYTES:raise ValueError('Invalid archive size')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries=archive.infolist();names=[value.filename for value in entries]
        if len(names)>MAX_FILES+1 or len(names)!=len(set(names)) or not {'manifest.json','README.txt','verify_archive.py'}<=set(names):raise ValueError('Invalid archive entries')
        if sum(value.file_size for value in entries)>MAX_SOURCE_BYTES+4*1024*1024:raise ValueError('Oversized archive')
        if any(value.is_dir() or value.flag_bits&1 or not re.fullmatch(r'(?:data/[a-z_]+[a-z0-9_]*\.jsonl|files/[a-z0-9_]+/[0-9]{8}-[a-z0-9_]+\.[a-z]+|originals/[a-z0-9_]+/[a-f0-9]{32}\.bin|README\.txt|manifest\.json|verify_archive\.py)',value.filename) for value in entries):
            raise ValueError('Invalid archive path')
        if archive.getinfo('manifest.json').file_size>4*1024*1024:raise ValueError('Oversized manifest')
        manifest=_decode(archive.read('manifest.json'))
        if (manifest.get('format')!='smartplan-company-export' or type(manifest.get('schema_version')) is not int or manifest['schema_version']!=1
                or not re.fullmatch(r'[a-f0-9]{32}',manifest.get('instance_id','')) or not re.fullmatch(r'[a-f0-9]{32}',manifest.get('export_id',''))
                or not HASH.fullmatch(manifest.get('catalog_sha256','')) or instance_id is not None and manifest['instance_id']!=instance_id):
            raise ValueError('Foreign or unsupported company archive')
        expected={value['path']:value for value in manifest['entries']}
        if len(expected)!=len(manifest['entries']) or set(expected)!=(set(names)-{'manifest.json'}):raise ValueError('Incomplete file manifest')
        for path,entry in expected.items():
            if type(entry['size']) is not int or entry['size']<0 or not HASH.fullmatch(entry['sha256']):raise ValueError('Invalid file descriptor')
            if archive.getinfo(path).file_size!=entry['size']:raise ValueError('Changed file size')
            digest=hashlib.sha256()
            with archive.open(path) as stream:
                while chunk:=stream.read(1024*1024):digest.update(chunk)
            if digest.hexdigest()!=entry['sha256']:raise ValueError('Changed archive content')
        inventory={table['table']:table for table in manifest['inventory']}
        if len(inventory)!=len(manifest['inventory']):raise ValueError('Duplicate inventory table')
        for name,table in inventory.items():
            if not NAME.fullmatch(name) or type(table['included']) is not bool or type(table['row_count']) is not int or table['row_count']<0:
                raise ValueError('Invalid inventory table')
            columns=[column['name'] for column in table['columns']]
            if len(columns)!=len(set(columns)) or any(not NAME.fullmatch(column) for column in columns) or not set(table['omitted_columns'])<=set(columns):
                raise ValueError('Invalid inventory schema')
            for relation in table['relationships']:
                target=inventory.get(relation['target_table'])
                if (relation['column'] not in columns or not target or type(relation['ordinal']) is not int or relation['ordinal']<0
                        or relation['target_column'] not in {value['name'] for value in target['columns']}
                        or relation['target_included'] is not target['included']):raise ValueError('Invalid relationship metadata')
        table_names=[table['table'] for table in manifest['tables']]
        if len(table_names)!=len(set(table_names)) or set(table_names)!={name for name,table in inventory.items() if table['included'] is True}:
            raise ValueError('Incomplete classified table manifest')
        if {value['path'] for value in manifest['tables']}!={name for name in expected if name.startswith('data/')}:
            raise ValueError('Unmapped table file')
        if any(type(manifest[key]) is not int or manifest[key]<0 for key in ('table_count','row_count','file_count')):
            raise ValueError('Invalid archive counts')
        count=0;references=set()
        for table in manifest['tables']:
            descriptor=expected[table['path']]
            if table['path']!='data/'+table['table']+'.jsonl' or descriptor['sha256']!=table['sha256']:raise ValueError('Invalid table mapping')
            source=inventory[table['table']]
            if (type(table['row_count']) is not int or table['row_count']!=source['row_count']
                    or table['columns']!=[column['name'] for column in source['columns'] if column['name'] not in source['omitted_columns']]):
                raise ValueError('Table diverges from classified inventory')
            rows=0
            with archive.open(table['path']) as stream:
                for line in stream:
                    row=_decode(line)
                    if set(row)!=set(table['columns']):raise ValueError('Invalid row schema')
                    for value in row.values():
                        if isinstance(value,dict) and '$file' in value:
                            file=expected[value['$file']]
                            if (set(value)!={'$file','sha256','size'} or not value['$file'].startswith('files/'+table['table']+'/')
                                    or file['sha256']!=value['sha256'] or file['size']!=value['size']):raise ValueError('Changed original mapping')
                            references.add(value['$file'])
                    rows+=1
            if rows!=table['row_count']:raise ValueError('Changed row count')
            count+=rows
        if count>MAX_ROWS or count!=manifest['row_count'] or len(manifest['tables'])!=manifest['table_count']:raise ValueError('Incomplete archive summary')
        for original in manifest['originals']:
            if type(original['complete']) is not bool or original['table'] not in inventory:raise ValueError('Invalid assembled original')
            if original['complete']:
                path=original['path'];file=expected[path]
                if (path!='originals/'+original['table']+'/'+original['id']+'.bin'
                        or file['size']!=original['size'] or file['sha256']!=original['sha256']):raise ValueError('Invalid assembled original mapping')
                if path in references:raise ValueError('Duplicate assembled original')
                references.add(path)
        if references!={name for name in expected if name.startswith(('files/','originals/'))}:raise ValueError('Unmapped original file')
        if manifest['file_count']!=sum(name.startswith(('files/','originals/')) for name in expected):raise ValueError('Invalid original count')
        return dict(valid=True,sha256=sha(raw),instance_id=manifest['instance_id'],table_count=manifest['table_count'],row_count=count,file_count=manifest['file_count'])


def verify(raw,*,instance_id=None):
    try:return _verify(raw,instance_id=instance_id)
    except (zipfile.BadZipFile,KeyError,TypeError,AttributeError,UnicodeError,RuntimeError,OverflowError,OSError,EOFError,zlib.error) as error:
        raise ValueError('Invalid or incomplete company archive') from error


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archive',type=Path);parser.add_argument('--instance-id',required=True)
    args=parser.parse_args(argv)
    try:
        if args.archive.stat().st_size>MAX_ARCHIVE_BYTES:raise SystemExit('Archiv überschreitet die Prüfgrenze.')
        result=verify(args.archive.read_bytes(),instance_id=args.instance_id)
    except (ValueError,OSError):raise SystemExit('Archivprüfung fehlgeschlagen; keine Daten wurden entpackt oder ausgeführt.') from None
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
