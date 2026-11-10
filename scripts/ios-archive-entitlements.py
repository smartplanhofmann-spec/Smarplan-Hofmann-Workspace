"""Bind archive entitlements to the App ID of an actual Apple distribution export.

An unsigned archive has no signature in which Xcode can preserve capabilities.
The first export supplies a real signed App ID and provisioning profile. Only
the app's own requested Keychain group is added to its temporary archive
signature; the final export must be independently verified before publication.
No certificate, private key, profile or identifier is guessed or downloaded here.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import plistlib
import re

BUNDLE_ID = 'de.smartplanhofmann.office'
SOURCE_GROUP = '$(AppIdentifierPrefix)$(PRODUCT_BUNDLE_IDENTIFIER)'
SIGNED_KEYS = {'application-identifier', 'com.apple.developer.team-identifier',
               'get-task-allow', 'beta-reports-active', 'keychain-access-groups'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def resolve(source, signed, profile, team, *, now=None):
    require(source == {'keychain-access-groups': [SOURCE_GROUP]},
            'Genau die angeforderte eigene Keychain-Gruppe erforderlich.')
    require(isinstance(team, str) and re.fullmatch(r'[A-Z0-9]{10}', team),
            'Erwartetes Apple-Team fehlt.')
    require(isinstance(signed, dict) and set(signed) <= SIGNED_KEYS,
            'Unbekannte signierte Berechtigung vor Archivierung pruefen.')
    application_id = signed.get('application-identifier')
    require(isinstance(application_id, str) and
            re.fullmatch(r'[A-Z0-9]{10}\.' + re.escape(BUNDLE_ID), application_id),
            'Export hat nicht die eigene konkrete App-Kennung.')
    prefix = application_id.split('.', 1)[0]
    require(signed.get('com.apple.developer.team-identifier') == team,
            'Export gehoert nicht zum erwarteten Apple-Team.')
    require(signed.get('get-task-allow') is False,
            'Export muss Debuggerzugriff ausdruecklich sperren.')
    # Missing/empty groups are the observed bootstrap defect. Foreign or shared
    # groups are never silently carried into the repaired archive.
    require(signed.get('keychain-access-groups') in (None, [], [application_id]),
            'Export enthaelt eine unerwartete Keychain-Gruppe.')
    require(isinstance(profile, dict) and profile.get('TeamIdentifier') == [team],
            'Profil gehoert nicht zum erwarteten Apple-Team.')
    require(profile.get('ApplicationIdentifierPrefix') == [prefix],
            'Tatsaechlicher App-ID-Praefix stimmt nicht mit dem Profil ueberein.')
    entitlements = profile.get('Entitlements')
    require(isinstance(entitlements, dict) and
            entitlements.get('application-identifier') == application_id and
            entitlements.get('com.apple.developer.team-identifier') == team and
            entitlements.get('get-task-allow') is False,
            'Profil und signierte Distributionsidentitaet stimmen nicht ueberein.')
    groups = entitlements.get('keychain-access-groups')
    require(isinstance(groups, list) and
            (application_id in groups or prefix + '.*' in groups),
            'Das Apple-Profil erlaubt die eigene Keychain-Gruppe nicht.')
    require(not profile.get('ProvisionedDevices') and not profile.get('ProvisionsAllDevices'),
            'App-Store-Profil statt Geraete-/Enterprise-Verteilung erforderlich.')
    expiry = profile.get('ExpirationDate')
    require(isinstance(expiry, datetime), 'Ablaufdatum des Apple-Profils fehlt.')
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    require(expiry > now, 'Apple-Profil ist abgelaufen.')
    return {**signed, 'keychain-access-groups': [application_id]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'signed-entitlements', 'provisioning-profile', 'team', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        def read(name):
            with Path(name).open('rb') as stream:
                return plistlib.load(stream)
        value = resolve(read(args.source), read(args.signed_entitlements),
                        read(args.provisioning_profile), args.team)
        with Path(args.output).open('xb') as stream:
            plistlib.dump(value, stream)
    except (ValueError, OSError, plistlib.InvalidFileException) as error:
        parser.error(str(error))
    print(json.dumps({'schema_version': 1, 'own_keychain_group_resolved': True,
                      'profile_checked': True, 'ready_for_final_export': False}))


if __name__ == '__main__':
    main()
