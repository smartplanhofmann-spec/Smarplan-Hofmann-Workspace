"""Freeze actual MFA/time/hash-only results using disposable synthetic companies."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from online.test_legacy_time_recovery import LegacyTimeRecoveryHttpTests


def generate(destination):
    fixture = LegacyTimeRecoveryHttpTests('runTest')
    fixture.setUp()
    try:
        result = fixture.call('/business/offline/recovery/time-event', fixture.request).json
        fields = ('id', 'employee_id', 'project_id', 'category_id', 'status', 'revision', 'sequence',
            'last_sequence', 'started_at', 'start_at', 'last_at', 'ended_at', 'timezone', 'events',
            'worked_seconds', 'break_seconds', 'work_dates', 'approved_work_dates', 'corrections', 'updated_at')
        record = {key: value for key, value in fixture.first['entry'].items() if key in fields}
        record.update(user_id=fixture.actor, revision=2, sequence=2, status='stopped',
                      sync_status='Auf diesem Gerät gesichert')
        value = dict(schema_version=1,
            source_contract='Native V1 retained time CORE; old acknowledged employee/category basis; no location proof or current timer snapshot',
            historical_native_commit='7b54dddfeb85bdef718bf4c76d369b0f673a5ede',
            account_id=fixture.actor, binding=result['binding'], cache_record=record,
            retained_operation=dict(entry_id=fixture.stop['entry_id'], project_id=fixture.f.project, body=fixture.stop),
            expected_core=fixture.core, lookup_command=fixture.request, lookup_result=result)
        destination.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print('Actual synthetic MFA/time fixture:', destination.name, destination.stat().st_size, 'bytes')
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    generate(ROOT / 'app/test/fixtures/legacy_time_recovery.json')
