"""Validate and export a draft vector plan without inventing missing geometry.

Coordinates are Cartesian (positive Y upwards). An uncalibrated sketch stays
unitless in DXF and is visibly marked as unscaled in PDF. All drawing entities
come from the supplied model; labels do not imply inferred room boundaries.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any


ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}')
COLLECTIONS = ('walls', 'doors', 'regions', 'fixtures', 'opening_candidates', 'devices', 'notes')
LAYERS = {
    'WAENDE': 7, 'TUEREN': 4, 'RAEUME': 3, 'EINRICHTUNG': 8,
    'GERAETE': 1, 'NOTIZEN': 7, 'UNGEKLAERT': 30, 'QUELLEN': 8,
}


def _object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f'{name}: Objekt erforderlich')
    return value


def _number(value: Any, name: str, *, minimum=None, maximum=None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name}: endliche Zahl erforderlich')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f'{name}: Zahl außerhalb des erlaubten Bereichs')
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f'{name}: endliche Zahl erforderlich') from None
    if not math.isfinite(result):
        raise ValueError(f'{name}: endliche Zahl erforderlich')
    return result


def _integer(value: Any, name: str, *, minimum=1, maximum=1_000_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f'{name}: ganze Zahl zwischen {minimum} und {maximum} erforderlich')
    return value


def _text(value: Any, name: str, *, maximum=1000) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(character) < 32 and character not in '\n\t' for character in value)):
        raise ValueError(f'{name}: gültiger Text erforderlich')
    return value


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError(f'{name}: gültige ID erforderlich')
    return value


def _point(value: Any, name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f'{name}: genau zwei Koordinaten erforderlich')
    return tuple(_number(component, name, minimum=-1e9, maximum=1e9) for component in value)


def _points(value: Any, name: str, *, minimum=2) -> list[tuple[float, float]]:
    if not isinstance(value, list) or not minimum <= len(value) <= 10_000:
        raise ValueError(f'{name}: mindestens {minimum} Punkte erforderlich')
    points = [_point(point, name) for point in value]
    if any(first == second for first, second in zip(points, points[1:])):
        raise ValueError(f'{name}: aufeinanderfolgende Punkte dürfen nicht identisch sein')
    return points


def _confirmed(item: dict, name: str):
    if not isinstance(item.get('confirmed'), bool):
        raise ValueError(f'{name}: Bestätigungsstatus erforderlich')


def _door_sweep(door: dict) -> float:
    return (door['end_angle'] - door['start_angle']) % 360


def validate_plan(plan: dict) -> None:
    """Raise ValueError for malformed data; never normalize or mutate the plan."""
    _object(plan, 'Plan')
    if plan.get('schema_version') != 1 or isinstance(plan.get('schema_version'), bool):
        raise ValueError('Nicht unterstützte Plan-Schemaversion')
    _id(plan.get('id'), 'Plan-ID')
    _text(plan.get('title'), 'Plantitel', maximum=200)
    if plan.get('status') != 'draft':
        raise ValueError('Der Prototyp verarbeitet ausschließlich Entwürfe')
    if plan.get('units') not in ('unitless', 'mm'):
        raise ValueError('Maßeinheit muss unitless oder mm sein')
    _integer(plan.get('revision'), 'Revision')
    source = _object(plan.get('source'), 'Quelle')
    _text(source.get('kind'), 'Quellenart', maximum=80)
    _text(source.get('scale'), 'Quellenmaßstab', maximum=80)
    identifiers = set()
    for name in COLLECTIONS:
        items = plan.get(name)
        if not isinstance(items, list) or len(items) > 10_000:
            raise ValueError(f'{name}: Liste mit höchstens 10000 Einträgen erforderlich')
        for item in items:
            _object(item, name)
            identifier = _id(item.get('id'), name + '-ID')
            if identifier in identifiers:
                raise ValueError('Geometrie- und Objekt-IDs müssen eindeutig sein')
            identifiers.add(identifier)
    walls = {}
    for wall in plan['walls']:
        _points(wall.get('points'), 'Wandpunkte')
        if wall.get('role') not in ('outer', 'inner'):
            raise ValueError('Wandrolle muss outer oder inner sein')
        _confirmed(wall, 'Wand')
        walls[wall['id']] = wall
    for door in plan['doors']:
        _point(door.get('hinge'), 'Türanschlag')
        _number(door.get('radius'), 'Türradius', minimum=1e-9, maximum=1e9)
        for key in ('start_angle', 'end_angle', 'leaf_angle'):
            _number(door.get(key), 'Türwinkel', minimum=-3600, maximum=3600)
        if math.isclose(_door_sweep(door), 0, abs_tol=1e-9):
            raise ValueError('Türbogen muss einen Öffnungswinkel haben')
        _confirmed(door, 'Tür')
    for region in plan['regions']:
        _text(region.get('label'), 'Bereichsbeschriftung', maximum=200)
        _point(region.get('position'), 'Beschriftungsposition')
        if region.get('kind') not in ('room', 'area'):
            raise ValueError('Bereichsart muss room oder area sein')
        _confirmed(region, 'Bereich')
    for fixture in plan['fixtures']:
        _text(fixture.get('type'), 'Einrichtungsart', maximum=80)
        closed = fixture.get('closed')
        if not isinstance(closed, bool):
            raise ValueError('Einrichtung benötigt einen closed-Status')
        _points(fixture.get('points'), 'Einrichtungspunkte', minimum=3 if closed else 2)
        _confirmed(fixture, 'Einrichtung')
    for opening in plan['opening_candidates']:
        _point(opening.get('position'), 'Ungeklärte Markierung')
        _text(opening.get('note'), 'Ungeklärte Markierung', maximum=500)
        _confirmed(opening, 'Ungeklärte Markierung')
    for device in plan['devices']:
        _text(device.get('type'), 'Geräteart', maximum=80)
        if device.get('wall_id') not in walls:
            raise ValueError('Gerät verweist auf eine nicht vorhandene Wand')
        _number(device.get('along'), 'Wandposition', minimum=0, maximum=1)
        _integer(device.get('quantity'), 'Geräteanzahl', maximum=24)
        _text(device.get('label'), 'Gerätebeschriftung', maximum=200)
        if device.get('mount_height_mm') is not None:
            _number(device['mount_height_mm'], 'Montagehöhe', minimum=0, maximum=1e6)
        if device.get('status') != 'planned':
            raise ValueError('Geräte im Prototyp müssen als planned gekennzeichnet sein')
    for note in plan['notes']:
        _point(note.get('position'), 'Notizposition')
        _text(note.get('text'), 'Notiz', maximum=2000)
    issues = plan.get('issues')
    if not isinstance(issues, list) or len(issues) > 200:
        raise ValueError('Prüfpunkte müssen als Liste vorliegen')
    for issue in issues:
        _text(issue, 'Prüfpunkt', maximum=2000)
    reference = plan.get('scale_reference')
    if reference is not None:
        _object(reference, 'Maßreferenz')
        _text(reference.get('label'), 'Referenzbezeichnung', maximum=200)
        if reference.get('status') == 'unassigned':
            if reference.get('length_mm') is not None:
                _number(reference['length_mm'], 'Referenzlänge', minimum=1e-9, maximum=1e9)
            if reference.get('endpoints') is not None:
                raise ValueError('Nicht zugeordnete Maßreferenz darf keine Endpunkte enthalten')
        elif reference.get('status') == 'assigned':
            _number(reference.get('length_mm'), 'Referenzlänge', minimum=1e-9, maximum=1e9)
            if plan['units'] != 'mm':
                raise ValueError('Zugeordnete Maßreferenz erfordert Millimeter-Koordinaten')
            endpoints = reference.get('endpoints')
            if not isinstance(endpoints, list) or len(endpoints) != 2:
                raise ValueError('Zugeordnete Maßreferenz benötigt zwei Endpunkte')
            first, second = (_point(point, 'Referenzendpunkt') for point in endpoints)
            if not math.isclose(math.dist(first, second), reference['length_mm'], rel_tol=1e-7, abs_tol=1e-7):
                raise ValueError('Referenzendpunkte stimmen nicht mit der Referenzlänge überein')
        else:
            raise ValueError('Maßreferenz benötigt assigned oder unassigned als Status')
    if plan['units'] == 'mm' and (source['scale'] != 'calibrated' or not reference
                                   or reference.get('status') != 'assigned'):
        raise ValueError('Millimeter-Koordinaten benötigen eine zugeordnete, kalibrierte Maßreferenz')
    if plan['units'] == 'unitless' and source['scale'] == 'calibrated':
        raise ValueError('Kalibrierte Koordinaten müssen als Millimeter gekennzeichnet sein')


def _wall_location(wall: dict, along: float) -> tuple[tuple[float, float], float]:
    points = wall['points']
    lengths = [math.dist(first, second) for first, second in zip(points, points[1:])]
    target = sum(lengths) * along
    for index, (first, second, length) in enumerate(zip(points, points[1:], lengths)):
        if target <= length or index == len(lengths) - 1:
            fraction = min(max(target / length, 0), 1)
            point = tuple(first[axis] + (second[axis] - first[axis]) * fraction for axis in (0, 1))
            return point, math.degrees(math.atan2(second[1] - first[1], second[0] - first[0]))
        target -= length
    raise ValueError('Wandposition nicht bestimmbar')


def add_devices(plan: dict, wall_id: str, along: float, quantity: int,
                type: str = 'socket', request_id: str | None = None) -> dict:
    """Add a planned device group with request idempotency and a new revision."""
    validate_plan(plan)
    wall_id = _id(wall_id, 'Wand-ID')
    along = _number(along, 'Wandposition', minimum=0, maximum=1)
    quantity = _integer(quantity, 'Geräteanzahl', maximum=24)
    device_type = _text(type, 'Geräteart', maximum=80).strip()
    request_id = _text(request_id, 'Anfrage-ID', maximum=200)
    if not any(wall['id'] == wall_id for wall in plan['walls']):
        raise ValueError('Gewählte Wand existiert nicht')
    identifier = 'device_' + hashlib.sha256((plan['id'] + '\0' + request_id).encode()).hexdigest()[:24]
    result = deepcopy(plan)
    previous = next((device for device in result['devices'] if device['id'] == identifier), None)
    expected = dict(wall_id=wall_id, along=along, quantity=quantity, type=device_type)
    if previous:
        if any(previous[key] != value for key, value in expected.items()):
            raise ValueError('Anfrage-ID wurde bereits für eine andere Änderung verwendet')
        return result
    label = ('Steckdose' if quantity == 1 else f'{quantity}× Steckdose') if device_type == 'socket' else f'{quantity}× {device_type}'
    result['devices'].append(dict(id=identifier, **expected, label=label,
                                  mount_height_mm=None, status='planned'))
    result['revision'] += 1
    validate_plan(result)
    return result


def calibrate_plan(plan: dict, endpoints: list, length_mm: float) -> dict:
    """Scale only after two explicit reference points and a known length exist.

    This calibrates coordinates, not the accuracy of traced walls or openings.
    Existing confirmation flags, dimensionless device positions, and separately
    entered millimeter mounting heights remain untouched.
    """
    validate_plan(plan)
    if not isinstance(endpoints, (list, tuple)) or len(endpoints) != 2:
        raise ValueError('Kalibrierung benötigt zwei explizite Referenzpunkte')
    first, second = (_point(point, 'Referenzpunkt') for point in endpoints)
    distance = math.dist(first, second)
    if distance <= 1e-9:
        raise ValueError('Referenzpunkte müssen eine messbare Kante begrenzen')
    length_mm = _number(length_mm, 'Referenzlänge', minimum=1e-9, maximum=1e9)
    factor = _number(length_mm / distance, 'Kalibrierungsfaktor', minimum=1e-12, maximum=1e12)
    result = deepcopy(plan)

    def point(value):
        return [value[0] * factor, value[1] * factor]

    for wall in result['walls']:
        wall['points'] = [point(value) for value in wall['points']]
    for door in result['doors']:
        door['hinge'] = point(door['hinge'])
        door['radius'] *= factor
    for region in result['regions']:
        region['position'] = point(region['position'])
    for fixture in result['fixtures']:
        fixture['points'] = [point(value) for value in fixture['points']]
    for item in result['opening_candidates'] + result['notes']:
        item['position'] = point(item['position'])
    label = (result.get('scale_reference') or {}).get('label', 'Referenzkante')
    result['scale_reference'] = dict(label=label, length_mm=length_mm,
                                     endpoints=[point(first), point(second)], status='assigned')
    result['source']['scale'] = 'calibrated'
    step = dict(factor=factor, from_units=plan['units'],
                original_endpoints=[list(first), list(second)])
    history = result['source'].get('calibration_history', [])
    if not isinstance(history, list) or len(history) >= 100:
        raise ValueError('Kalibrierungshistorie ist nicht gültig')
    if not history and result['source'].get('calibration'):
        previous = _object(result['source']['calibration'], 'Vorherige Kalibrierung')
        history = [{key: previous.get(key) for key in ('factor', 'from_units', 'original_endpoints')}]
    cumulative = factor
    for previous in history:
        _object(previous, 'Kalibrierungsschritt')
        cumulative *= _number(previous.get('factor'), 'Kalibrierungsfaktor', minimum=1e-12, maximum=1e12)
        if previous.get('from_units') not in ('unitless', 'mm'):
            raise ValueError('Kalibrierungsschritt benötigt eine Quellenmaßeinheit')
        old_endpoints = previous.get('original_endpoints')
        if not isinstance(old_endpoints, list) or len(old_endpoints) != 2:
            raise ValueError('Kalibrierungsschritt benötigt zwei Quellenpunkte')
        for old_point in old_endpoints:
            _point(old_point, 'Früherer Referenzpunkt')
    if not math.isfinite(cumulative):
        raise ValueError('Kumulierte Kalibrierung ist nicht endlich')
    result['source']['calibration_history'] = history + [step]
    result['source']['calibration'] = dict(step, cumulative_factor=cumulative)
    result['units'] = 'mm'
    result['revision'] += 1
    validate_plan(result)
    return result


def _bounds(plan: dict) -> tuple[float, float, float, float]:
    points = []
    for item in plan['walls'] + plan['fixtures']:
        points.extend(item['points'])
    for item in plan['regions'] + plan['opening_candidates'] + plan['notes']:
        points.append(item['position'])
    for door in plan['doors']:
        x, y = door['hinge']
        radius = door['radius']
        points.extend(((x - radius, y - radius), (x + radius, y + radius)))
    if not points:
        return 0, 0, 100, 100
    minimum_x, maximum_x = min(point[0] for point in points), max(point[0] for point in points)
    minimum_y, maximum_y = min(point[1] for point in points), max(point[1] for point in points)
    span = max(maximum_x - minimum_x, maximum_y - minimum_y, 1e-6)
    padding = span * .06
    return minimum_x - padding, minimum_y - padding, maximum_x + padding, maximum_y + padding


def _size(plan: dict) -> float:
    minimum_x, minimum_y, maximum_x, maximum_y = _bounds(plan)
    return max(maximum_x - minimum_x, maximum_y - minimum_y) * .008


def _line_text(value: str) -> str:
    return ' / '.join(value.replace('\t', ' ').splitlines())


def _scale_label(plan: dict) -> str:
    if plan['units'] == 'unitless':
        if (plan.get('scale_reference') or {}).get('status') == 'unassigned':
            return 'Unskaliert – Maßreferenz noch nicht zugeordnet'
        return 'Unskaliert – Maße fehlen'
    return 'Maßeinheit: mm – Referenzmaß und Geometrie prüfen'


def _source_lines(plan: dict) -> list[str]:
    lines = [f"{plan['title']} | Entwurf | Revision {plan['revision']}", _scale_label(plan),
             f"Quelle: {plan['source']['kind']} | Maßstab: {plan['source']['scale']}",
             'Wandstärken und nicht angegebene Öffnungen werden nicht ergänzt.',
             'Gerätesymbole zeigen geplante Positionen, keine bestätigte Montage.']
    reference = plan.get('scale_reference')
    if reference:
        status = 'zugeordnet' if reference['status'] == 'assigned' else 'noch nicht zugeordnet'
        length = (f"{reference['length_mm']:g} mm" if reference.get('length_mm') is not None
                  else 'Länge noch offen')
        if reference.get('length_mm') is not None and reference['length_mm'] >= 1000:
            length += f" ({reference['length_mm'] / 1000:g} m)"
        lines.append(f"Referenz: {reference['label']} = {length} ({status})")
    return lines


def export_dxf(plan: dict, path: str | os.PathLike) -> Path:
    """Write actual editable R2010 entities and blocks, then audit the document."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    validate_plan(plan)
    document = ezdxf.new('R2010', setup=True)
    document.header['$INSUNITS'] = 4 if plan['units'] == 'mm' else 0
    document.header['$MEASUREMENT'] = 1 if plan['units'] == 'mm' else 0
    for name, color in LAYERS.items():
        document.layers.new(name, dxfattribs={'color': color})
    document.styles.new('SMARTPLAN', dxfattribs={'font': 'DejaVuSans.ttf'})
    model = document.modelspace()
    symbol = _size(plan)
    height = symbol * 1.8

    def text(value, position, layer, *, centered=False, size=height):
        entity = model.add_text(_line_text(value), dxfattribs={
            'layer': layer, 'height': size, 'style': 'SMARTPLAN'})
        entity.set_placement(position, align=TextEntityAlignment.MIDDLE_CENTER if centered
                             else TextEntityAlignment.LEFT)
        return entity

    def polyline(points, layer, *, closed=False):
        points = [tuple(point) for point in points]
        if len(points) == 2 and not closed:
            return model.add_line(points[0], points[1], dxfattribs={'layer': layer})
        if points[0] == points[-1]:
            points = points[:-1]
            closed = True
        return model.add_lwpolyline(points, close=closed, dxfattribs={'layer': layer})

    for wall in plan['walls']:
        polyline(wall['points'], 'WAENDE')
    for door in plan['doors']:
        hinge, radius = door['hinge'], door['radius']
        model.add_arc(hinge, radius, door['start_angle'] % 360, door['end_angle'] % 360,
                      dxfattribs={'layer': 'TUEREN'})
        angle = math.radians(door['leaf_angle'])
        leaf = (hinge[0] + radius * math.cos(angle), hinge[1] + radius * math.sin(angle))
        model.add_line(hinge, leaf, dxfattribs={'layer': 'TUEREN'})
    for region in plan['regions']:
        text(region['label'], region['position'], 'RAEUME', centered=True)
    for fixture in plan['fixtures']:
        polyline(fixture['points'], 'EINRICHTUNG', closed=fixture['closed'])
    for opening in plan['opening_candidates']:
        x, y = opening['position']
        model.add_circle((x, y), symbol * 1.3, dxfattribs={'layer': 'UNGEKLAERT'})
        text('?', (x, y), 'UNGEKLAERT', centered=True, size=symbol * 1.7)
        text(opening['note'], (x + symbol * 2, y + symbol * 2), 'UNGEKLAERT', size=height * .75)
    walls = {wall['id']: wall for wall in plan['walls']}
    for device in plan['devices']:
        position, angle = _wall_location(walls[device['wall_id']], device['along'])
        name = 'SP_DEVICE_' + hashlib.sha256(device['type'].encode()).hexdigest()[:12]
        if name not in document.blocks:
            block = document.blocks.new(name)
            # One location marker represents the device request. Quantity is
            # metadata/label, not an inferred physical combination or spacing.
            if device['type'] == 'socket':
                block.add_circle((0, 0), symbol, dxfattribs={'layer': '0'})
                block.add_line((-symbol * .45, -symbol * .35),
                               (-symbol * .45, symbol * .35), dxfattribs={'layer': '0'})
                block.add_line((symbol * .45, -symbol * .35),
                               (symbol * .45, symbol * .35), dxfattribs={'layer': '0'})
            else:
                block.add_lwpolyline([(-symbol, -symbol), (symbol, -symbol),
                                      (symbol, symbol), (-symbol, symbol)],
                                     close=True, dxfattribs={'layer': '0'})
        model.add_blockref(name, position, dxfattribs={'layer': 'GERAETE', 'rotation': angle})
        text(device['label'] + ' · geplant', (position[0] + symbol * 2, position[1] - symbol * 3),
             'GERAETE', size=height * .75)
    for note in plan['notes']:
        text(note['text'], note['position'], 'NOTIZEN', size=height * .85)
    minimum_x, minimum_y, _, _ = _bounds(plan)
    for index, line in enumerate(_source_lines(plan)):
        text(line, (minimum_x, minimum_y - height * (2 + index * 1.5)), 'QUELLEN', size=height * .8)
    for index, issue in enumerate(plan['issues']):
        text('Prüfpunkt: ' + issue, (minimum_x, minimum_y - height * (12 + index * 1.5)),
             'UNGEKLAERT', size=height * .8)
    audit = document.audit()
    if audit.has_errors or audit.has_fixes:
        raise ValueError('DXF-Prüfung fehlgeschlagen; Export wurde nicht gespeichert')
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    document.saveas(destination)
    return destination


def _pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [os.environ.get('SMARTPLAN_PLAN_FONT'),
                  '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                  '/usr/share/fonts/TTF/DejaVuSans.ttf',
                  str(Path(__file__).resolve().parents[2] / 'app/assets/fonts/Inter.ttf')]
    for value in candidates:
        if value and Path(value).is_file():
            name = 'SmartplanPlan_' + hashlib.sha256(str(value).encode()).hexdigest()[:10]
            try:
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, value))
                return name
            except Exception:
                continue
    return 'Helvetica'


def export_pdf(plan: dict, path: str | os.PathLike) -> Path:
    """Write a readable A4 landscape draft from the same model as the DXF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfgen import canvas

    validate_plan(plan)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    width, height = landscape(A4)
    sheet = canvas.Canvas(str(destination), pagesize=(width, height), pageCompression=1)
    sheet.setTitle(plan['title'] + ' – Entwurf')
    sheet.setAuthor('Smartplan Office')
    font = _pdf_font()
    sheet.setFillColor(colors.HexColor('#162137'))
    sheet.setFont(font, 19)
    title = _line_text(plan['title'])
    while pdfmetrics.stringWidth(title, font, 19) > width - 190 and len(title) > 12:
        title = title[:-2]
    if title != _line_text(plan['title']):
        title = title.rstrip() + '…'
    sheet.drawString(36, height - 42, title)
    sheet.setFont(font, 11)
    sheet.drawRightString(width - 36, height - 40, 'Entwurf')
    sheet.setFont(font, 10)
    sheet.setFillColor(colors.HexColor('#a45212'))
    sheet.drawString(36, height - 65, _scale_label(plan))
    sheet.setFillColor(colors.HexColor('#5d6573'))
    sheet.setFont(font, 8)
    sheet.drawRightString(width - 36, height - 65, f"Revision {plan['revision']} · {plan['id']}")
    if plan.get('scale_reference'):
        sheet.drawString(36, height - 81, _source_lines(plan)[-1])
    minimum_x, minimum_y, maximum_x, maximum_y = _bounds(plan)
    available = (width - 88, height - 164)
    scale = min(available[0] / (maximum_x - minimum_x), available[1] / (maximum_y - minimum_y))
    offset_x = (width - (maximum_x - minimum_x) * scale) / 2 - minimum_x * scale
    offset_y = 72 + (available[1] - (maximum_y - minimum_y) * scale) / 2 - minimum_y * scale

    def position(value):
        return value[0] * scale + offset_x, value[1] * scale + offset_y

    def wrap(value, maximum_width, size):
        lines, line = [], ''
        for word in value.split():
            if line and pdfmetrics.stringWidth(line + ' ' + word, font, size) > maximum_width:
                lines.append(line)
                line = ''
            # Even a single unbroken user label must not run off the page.
            while pdfmetrics.stringWidth(word, font, size) > maximum_width:
                fragment, measured = '', 0
                for character in word:
                    character_width = pdfmetrics.stringWidth(character, font, size)
                    if fragment and measured + character_width > maximum_width:
                        break
                    fragment += character
                    measured += character_width
                lines.append(fragment)
                word = word[len(fragment):]
            line = (line + ' ' + word).strip()
        if line:
            lines.append(line)
        return lines or ['']

    overflow_labels = []

    def label(value, point, *, centered=False, size=9, color=colors.HexColor('#24324a')):
        value = _line_text(value)
        x, y = position(point)
        lines = wrap(value, min(240, width - 80), size)
        if len(lines) > 3:
            overflow_labels.append(value)
            lines = lines[:3]
            while pdfmetrics.stringWidth(lines[-1] + '…', font, size) > 240:
                lines[-1] = lines[-1][:-1]
            lines[-1] += '…'
        sheet.setFont(font, size)
        text_width = max(pdfmetrics.stringWidth(line, font, size) for line in lines)
        if centered:
            x -= text_width / 2
        x = min(max(x, 38), width - 38 - text_width)
        leading = size + 2
        y = min(max(y, 74 + (len(lines) - 1) * leading), height - 98)
        sheet.setFillColor(colors.white)
        sheet.rect(x - 2, y - (len(lines) - 1) * leading - 2,
                   text_width + 4, size + 3 + (len(lines) - 1) * leading, fill=1, stroke=0)
        sheet.setFillColor(color)
        for index, line in enumerate(lines):
            sheet.drawString(x, y - index * leading, line)

    for wall in plan['walls']:
        sheet.setStrokeColor(colors.HexColor('#263044'))
        sheet.setLineWidth(1.8 if wall['role'] == 'outer' else 1.2)
        outline = sheet.beginPath()
        outline.moveTo(*position(wall['points'][0]))
        for point in wall['points'][1:]:
            outline.lineTo(*position(point))
        sheet.drawPath(outline)
    for door in plan['doors']:
        x, y = position(door['hinge'])
        radius = door['radius'] * scale
        sheet.setStrokeColor(colors.HexColor('#487c9a'))
        sheet.setLineWidth(.8)
        sheet.arc(x - radius, y - radius, x + radius, y + radius,
                  startAng=door['start_angle'], extent=_door_sweep(door))
        angle = math.radians(door['leaf_angle'])
        sheet.line(x, y, x + radius * math.cos(angle), y + radius * math.sin(angle))
    for fixture in plan['fixtures']:
        sheet.setStrokeColor(colors.HexColor('#83939f'))
        sheet.setLineWidth(.8)
        outline = sheet.beginPath()
        outline.moveTo(*position(fixture['points'][0]))
        for point in fixture['points'][1:]:
            outline.lineTo(*position(point))
        if fixture['closed']:
            outline.close()
        sheet.drawPath(outline)
    for region in plan['regions']:
        label(region['label'], region['position'], centered=True, size=10)
    symbol = _size(plan)
    walls = {wall['id']: wall for wall in plan['walls']}
    for device in plan['devices']:
        point, angle = _wall_location(walls[device['wall_id']], device['along'])
        sheet.saveState()
        sheet.translate(*position(point))
        sheet.rotate(angle)
        radius = symbol * scale
        sheet.setStrokeColor(colors.HexColor('#ca5a19'))
        sheet.setLineWidth(.9)
        if device['type'] == 'socket':
            sheet.circle(0, 0, radius, fill=0)
            for delta in (-.45, .45):
                sheet.line(delta * radius, -.35 * radius, delta * radius, .35 * radius)
        else:
            sheet.rect(-radius, -radius, 2 * radius, 2 * radius, fill=0)
        sheet.restoreState()
        label(device['label'] + ' · geplant', (point[0] + symbol * 2, point[1] - symbol * 4), size=7)
    for opening in plan['opening_candidates']:
        label('?', opening['position'], centered=True, size=12, color=colors.HexColor('#ad4a17'))
    for note in plan['notes']:
        label(note['text'], note['position'], size=7)
    sheet.setFillColor(colors.HexColor('#697181'))
    sheet.setFont(font, 7)
    sheet.drawString(36, 45, 'Darstellung auf das Blatt eingepasst – kein Druckmaßstab.')
    sheet.drawString(36, 32, 'Wandstärken und ungeklärte Öffnungen sind nicht ergänzt. Gerätesymbole: geplant.')
    sheet.drawRightString(width - 36, 32, f"Offene Prüfpunkte: {len(plan['issues']) + len(plan['opening_candidates'])}")
    details = list(plan['issues'])
    for note, count in Counter(item['note'] for item in plan['opening_candidates']).items():
        details.append(f"Ungeklärte Markierung ({count}×): {note}" if count > 1
                       else 'Ungeklärte Markierung: ' + note)
    details += ['Vollständige Beschriftung: ' + value for value in overflow_labels]
    if plan.get('scale_reference'):
        details = [_source_lines(plan)[-1]] + details
    if details:
        sheet.showPage()
        sheet.setFillColor(colors.HexColor('#162137'))
        sheet.setFont(font, 16)
        sheet.drawString(36, height - 42, 'Entwurf – offene Punkte und Maßreferenz')
        cursor = height - 73
        sheet.setFont(font, 10)
        for index, detail in enumerate(details, 1):
            lines = wrap(f'{index}. ' + _line_text(detail), width - 80, 10)
            for line in lines:
                if cursor < 40:
                    sheet.showPage()
                    sheet.setFont(font, 10)
                    sheet.setFillColor(colors.HexColor('#162137'))
                    cursor = height - 42
                sheet.drawString(40, cursor, line)
                cursor -= 15
            cursor -= 7
    sheet.save()
    return destination


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Entwurfsplan aus JSON als bearbeitbares DXF und PDF exportieren')
    parser.add_argument('plan', type=Path, help='JSON-Modell; Eingabedatei bleibt unverändert')
    parser.add_argument('--out-dir', required=True, type=Path, help='Zielverzeichnis für PDF/DXF')
    arguments = parser.parse_args(argv)
    try:
        raw = arguments.plan.read_text(encoding='utf-8')
        if len(raw) > 8_000_000:
            raise ValueError('Planmodell ist zu groß')
        plan = json.loads(raw)
        validate_plan(plan)
        stem = re.sub(r'[^A-Za-z0-9_-]', '_', plan['id'])
        export_dxf(plan, arguments.out_dir / (stem + '.dxf'))
        export_pdf(plan, arguments.out_dir / (stem + '.pdf'))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f'Export fehlgeschlagen: {error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
