"""Explicit operator commands; passwords and vault values never enter command arguments."""
import argparse
import getpass
import os
from core import Problem
from online.store import migrate, PostgresOffice


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['migrate', 'init-owner', 'reset-mfa'])
    parser.add_argument('email', nargs='?')
    args = parser.parse_args()
    dsn = os.environ['SMARTPLAN_DATABASE_DSN']
    if args.action == 'migrate':
        migrate(dsn)
        print('PostgreSQL-Schema geprüft.')
        return
    if not args.email:
        parser.error('E-Mail-Adresse erforderlich')
    office = PostgresOffice(dsn)
    try:
        if args.action == 'init-owner':
            if office.db.execute("SELECT 1 FROM users WHERE role='owner'").fetchone():
                raise SystemExit('Geschäftsführung bereits angelegt.')
            password = getpass.getpass('Neues Online-Passwort (mindestens 12 Zeichen): ')
            if password != getpass.getpass('Passwort wiederholen: '):
                raise SystemExit('Passwörter stimmen nicht überein.')
            with office.lock, office.db:
                if office.db.execute("SELECT 1 FROM users WHERE role='owner'").fetchone():
                    raise SystemExit('Geschäftsführung bereits angelegt.')
                office.add_user(args.email, password, 'owner')
            print('Online-Testkonto angelegt. Authenticator wird bei der ersten App-Anmeldung eingerichtet.')
        else:
            with office.lock, office.db:
                user = office.db.execute('SELECT * FROM users WHERE email=?', (args.email.strip().lower(),)).fetchone()
                if not user:
                    raise SystemExit('Konto nicht gefunden.')
                for table in ('mfa', 'sessions', 'auth_challenges'):
                    office.db.execute(f'DELETE FROM {table} WHERE user_id=?', (user['id'],))
                office.audit(user, 'mfa.operator_reset', user['id'])
            print('Authenticator zurückgesetzt, Sitzungen widerrufen. Nächste Anmeldung erfordert Neueinrichtung.')
    except Problem as error:
        raise SystemExit(error.message)
    finally:
        office.db.close()


if __name__ == '__main__':
    main()
