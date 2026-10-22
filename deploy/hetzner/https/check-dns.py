"""Verify all public DNS answers against addresses configured on this VM."""
import ipaddress
import json
import socket
import subprocess


def main():
    host = 'office.smartplan-hofmann.de'
    interfaces = json.loads(subprocess.check_output(
        ['ip', '-j', 'address', 'show', 'scope', 'global']))
    local = set()
    for interface in interfaces:
        for address in interface.get('addr_info', []):
            # iproute2 output may contain entries without a local address.
            # Ignoring those must never grant access to a foreign DNS address.
            value = address.get('local')
            if value:
                local.add(str(ipaddress.ip_address(value)))
    if not local:
        raise SystemExit('Keine lokalen globalen IP-Adressen erkannt. Ausgabe von ip -j address prüfen.')
    answers = {str(ipaddress.ip_address(answer[4][0])) for answer in
               socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not answers or not answers.issubset(local):
        raise SystemExit('DNS zeigt nicht ausschließlich auf diese VM. A- und AAAA-Einträge prüfen.')
    print('DNS passt zu dieser VM:', ', '.join(sorted(answers)))


if __name__ == '__main__':
    main()
