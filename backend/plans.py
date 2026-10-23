"""Validation for the first native, unscaled wall drawing workflow."""
import math
import re
from core import Problem


def validate_drawing(walls):
    if not isinstance(walls, list) or len(walls) > 2000:
        raise Problem(400, 'Höchstens 2000 Wände erlaubt')
    ids = set()
    for wall in walls:
        if not isinstance(wall, dict) or set(wall) != {'id', 'points'}:
            raise Problem(400, 'Wand mit ID und zwei Punkten erwartet')
        identifier = wall['id']
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', identifier) or identifier in ids:
            raise Problem(400, 'Eindeutige Wand-ID erwartet')
        ids.add(identifier)
        points = wall['points']
        if not isinstance(points, list) or len(points) != 2:
            raise Problem(400, 'Zwei Wandpunkte erwartet')
        for point in points:
            if (not isinstance(point, list) or len(point) != 2 or
                any(type(n) not in (int, float) or abs(n) > 10000 or not math.isfinite(n) for n in point)):
                raise Problem(400, 'Ungültige Wandkoordinaten')
        if points[0] == points[1]:
            raise Problem(400, 'Wand braucht zwei unterschiedliche Punkte')
    return walls
