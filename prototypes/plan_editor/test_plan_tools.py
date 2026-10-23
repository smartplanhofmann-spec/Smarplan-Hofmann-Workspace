"""Round-trip checks using invented rectangles, labels, and measurements only.

Run with ``python -m unittest discover -s prototypes/plan_editor -v``.
No user sketch, room names, image data, or measured project values belong here.
"""

from copy import deepcopy
import math
from pathlib import Path
import tempfile
import unittest

import ezdxf
from pypdf import PdfReader
from pypdf.generic import ContentStream

from plan_tools import (
    add_devices,
    calibrate_plan,
    export_dxf,
    export_pdf,
    validate_plan,
)


def synthetic_plan():
    """An arbitrary 100-by-60 rectangle, without an asserted physical scale."""
    return {
        "schema_version": 1,
        "id": "synthetic-test",
        "title": "Synthetischer Plan Äöü",
        "status": "draft",
        "units": "unitless",
        "revision": 1,
        "source": {"kind": "hand_sketch", "scale": "unknown"},
        "walls": [
            {
                "id": "wall-rectangle",
                "points": [[0, 0], [100, 0], [100, 60], [0, 60], [0, 0]],
                "role": "outer",
                "confirmed": False,
            }
        ],
        "doors": [
            {
                "id": "door-test",
                "hinge": [10, 0],
                "radius": 8,
                "start_angle": 0,
                "end_angle": 90,
                "leaf_angle": 90,
                "confirmed": False,
            }
        ],
        "regions": [
            {
                "id": "region-test",
                "label": "Raum Äöü Test",
                "position": [50, 40],
                "kind": "room",
                "confirmed": False,
            }
        ],
        "fixtures": [
            {
                "id": "fixture-test",
                "type": "kitchen_counter",
                "points": [[20, 20], [40, 20], [40, 30], [20, 30]],
                "closed": True,
                "confirmed": False,
            }
        ],
        "opening_candidates": [
            {
                "id": "opening-test",
                "position": [100, 50],
                "note": "Synthetische Markierung prüfen",
                "confirmed": False,
            }
        ],
        "devices": [],
        "notes": [
            {
                "id": "note-test",
                "position": [45, 15],
                "text": "Nur synthetische Testdaten. Maße fehlen.",
            }
        ],
        "issues": ["Synthetischer Prüfhinweis: keine bekannten Maße."],
    }


def with_device(plan=None, *, quantity=2):
    return add_devices(
        synthetic_plan() if plan is None else plan,
        "wall-rectangle",
        0.4,
        quantity,
        request_id="synthetic-device-request",
    )


def rounded_point(point):
    return tuple(round(float(value), 7) for value in tuple(point)[:2])


def drawn_edges(entities):
    """Read the actual editable DXF edges without relying on entity handles."""
    edges = []
    for entity in entities:
        if entity.dxftype() == "LINE":
            edges.append((rounded_point(entity.dxf.start), rounded_point(entity.dxf.end)))
        elif entity.dxftype() == "LWPOLYLINE":
            points = [rounded_point(point) for point in entity.get_points("xy")]
            if entity.closed and points[-1] != points[0]:
                points.append(points[0])
            edges.extend(zip(points, points[1:]))
    return edges


def pdf_path_points(page, reader):
    """Inspect final page coordinates, including nested PDF transformations."""
    matrix = (1, 0, 0, 1, 0, 0)
    stack = []
    points = []
    for operands, operator in ContentStream(page.get_contents(), reader).operations:
        if operator == b"q":
            stack.append(matrix)
        elif operator == b"Q":
            matrix = stack.pop()
        elif operator == b"cm":
            a, b, c, d, e, f = matrix
            aa, bb, cc, dd, ee, ff = map(float, operands)
            matrix = (
                a * aa + c * bb,
                b * aa + d * bb,
                a * cc + c * dd,
                b * cc + d * dd,
                a * ee + c * ff + e,
                b * ee + d * ff + f,
            )
        elif operator in (b"m", b"l", b"c", b"v", b"y", b"re"):
            values = list(map(float, operands))
            if operator == b"re":
                x, y, width, height = values
                coordinates = [(x, y), (x + width, y + height)]
            else:
                coordinates = list(zip(values[::2], values[1::2]))
            a, b, c, d, e, f = matrix
            points.extend((a * x + c * y + e, b * x + d * y + f) for x, y in coordinates)
    return points


class ValidationTests(unittest.TestCase):
    def test_synthetic_model_is_valid_and_validation_does_not_mutate_it(self):
        plan = synthetic_plan()
        original = deepcopy(plan)
        self.assertIsNone(validate_plan(plan))
        self.assertEqual(plan, original)

    def test_coordinates_must_be_finite_in_every_geometry_collection(self):
        locations = (
            ("walls", "points"),
            ("doors", "hinge"),
            ("regions", "position"),
            ("fixtures", "points"),
            ("opening_candidates", "position"),
            ("notes", "position"),
        )
        for collection, field in locations:
            for invalid in (math.nan, math.inf, -math.inf, 10**400):
                with self.subTest(collection=collection, invalid=invalid):
                    plan = synthetic_plan()
                    point = plan[collection][0][field]
                    if field == "points":
                        point = point[0]
                    point[0] = invalid
                    with self.assertRaises(ValueError):
                        validate_plan(plan)

    def test_ids_are_nonempty_strings_and_duplicates_are_rejected(self):
        for invalid in ("", "   ", None, 12):
            with self.subTest(plan_id=invalid):
                plan = synthetic_plan()
                plan["id"] = invalid
                with self.assertRaises(ValueError):
                    validate_plan(plan)
        for collection in ("walls", "doors", "regions", "fixtures", "opening_candidates", "notes"):
            for invalid in ("", "   ", None, 12):
                with self.subTest(collection=collection, invalid=invalid):
                    plan = synthetic_plan()
                    plan[collection][0]["id"] = invalid
                    with self.assertRaises(ValueError):
                        validate_plan(plan)
        plan = synthetic_plan()
        plan["walls"].append(deepcopy(plan["walls"][0]))
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_door_radius_must_be_positive_and_finite(self):
        for invalid in (-1, 0, math.nan, math.inf, True):
            with self.subTest(radius=invalid):
                plan = synthetic_plan()
                plan["doors"][0]["radius"] = invalid
                with self.assertRaises(ValueError):
                    validate_plan(plan)

    def test_devices_require_existing_walls_valid_along_and_integer_quantity(self):
        mutations = [
            ("wall_id", "missing-wall"),
            *[("along", value) for value in (-0.01, 1.01, math.nan, math.inf, True)],
            *[("quantity", value) for value in (0, -1, 1.5, "2", True, False)],
        ]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                plan = with_device()
                plan["devices"][0][field] = value
                with self.assertRaises(ValueError):
                    validate_plan(plan)

    def test_renaming_units_to_mm_requires_an_assigned_calibrated_reference(self):
        for reference in (None, {"label": "Synthetische Referenzkante", "endpoints": None, "length_mm": 1000, "status": "unassigned"}):
            with self.subTest(reference=reference):
                plan = synthetic_plan()
                plan["units"] = "mm"
                if reference is not None:
                    plan["scale_reference"] = reference
                self.assertEqual(plan["source"]["scale"], "unknown")
                with self.assertRaises(ValueError):
                    validate_plan(plan)


class DeviceCommandTests(unittest.TestCase):
    def test_add_devices_copies_model_and_changes_only_device_state_and_revision(self):
        plan = synthetic_plan()
        original = deepcopy(plan)
        result = with_device(plan)
        self.assertEqual(plan, original)
        self.assertIsNot(result, plan)
        self.assertEqual(result["revision"], 2)
        self.assertEqual(len(result["devices"]), 1)
        device = result["devices"][0]
        self.assertEqual(device["type"], "socket")
        self.assertEqual(device["wall_id"], "wall-rectangle")
        self.assertEqual(device["along"], 0.4)
        self.assertEqual(device["quantity"], 2)
        self.assertEqual(device["label"], "2× Steckdose")
        self.assertNotIn("doppel", device["label"].lower())
        self.assertEqual(device["status"], "planned")
        self.assertIsNone(device["mount_height_mm"])
        for key in original:
            if key not in ("devices", "revision"):
                self.assertEqual(result[key], original[key], key)
        result["walls"][0]["points"][0][0] = -100
        result["regions"][0]["label"] = "Geänderter synthetischer Text"
        self.assertEqual(plan, original)

    def test_same_request_retries_are_idempotent_and_ids_are_deterministic(self):
        original = synthetic_plan()
        result = with_device(original)
        self.assertEqual(with_device(original), result)
        self.assertEqual(with_device(result), result)
        self.assertEqual(result["revision"], 2)
        another_plan = synthetic_plan()
        another_plan["id"] = "another-synthetic-plan"
        self.assertNotEqual(with_device(another_plan)["devices"][0]["id"], result["devices"][0]["id"])

    def test_reusing_request_id_with_different_body_is_rejected(self):
        plan = with_device()
        original = deepcopy(plan)
        with self.assertRaises(ValueError):
            add_devices(plan, "wall-rectangle", 0.4, 3, request_id="synthetic-device-request")
        self.assertEqual(plan, original)

    def test_new_request_appends_device_and_increments_revision_once(self):
        first = with_device()
        second = add_devices(first, "wall-rectangle", 0.7, 1, request_id="another-request")
        self.assertEqual(second["revision"], 3)
        self.assertEqual(len(second["devices"]), 2)
        self.assertNotEqual(second["devices"][0]["id"], second["devices"][1]["id"])
        self.assertEqual(first["revision"], 2)
        self.assertEqual(len(first["devices"]), 1)

    def test_invalid_command_arguments_are_rejected_without_mutation(self):
        cases = [
            {"wall_id": "missing-wall"},
            *[{"along": value} for value in (-0.1, 1.1, math.nan, math.inf, True)],
            *[{"quantity": value} for value in (0, -1, 1.5, "2", True, False)],
            *[{"request_id": value} for value in (None, "", "   ")],
        ]
        for override in cases:
            with self.subTest(override=override):
                plan = synthetic_plan()
                original = deepcopy(plan)
                arguments = {"wall_id": "wall-rectangle", "along": 0.4, "quantity": 2, "request_id": "test-request"}
                arguments.update(override)
                with self.assertRaises(ValueError):
                    add_devices(plan, **arguments)
                self.assertEqual(plan, original)

    def test_wall_endpoints_are_valid_positions(self):
        for along in (0, 1):
            with self.subTest(along=along):
                plan = add_devices(synthetic_plan(), "wall-rectangle", along, 1, request_id="endpoint-request")
                self.assertIsNone(validate_plan(plan))


class CalibrationTests(unittest.TestCase):
    def test_recalibration_preserves_original_transform_history(self):
        original = synthetic_plan()
        first = calibrate_plan(original, [[0, 0], [100, 0]], 1000)
        second = calibrate_plan(first, [[0, 0], [1000, 0]], 2000)
        self.assertEqual(len(second['source']['calibration_history']), 2)
        self.assertEqual(second['source']['calibration_history'][0]['from_units'], 'unitless')
        self.assertEqual(second['source']['calibration_history'][0]['original_endpoints'], [[0, 0], [100, 0]])
        self.assertEqual(second['source']['calibration_history'][1]['from_units'], 'mm')
        self.assertEqual(second['source']['calibration']['cumulative_factor'], 20)
        self.assertEqual(second['walls'][0]['points'][2], [2000, 1200])
        self.assertEqual(first['source']['calibration']['cumulative_factor'], 10)

    def test_explicit_synthetic_measurement_scales_all_geometry_without_confirming_it(self):
        plan = with_device()
        plan["devices"][0]["mount_height_mm"] = 300
        plan["scale_reference"] = {"label": "Synthetische Referenzkante", "endpoints": None, "length_mm": None, "status": "unassigned"}
        original = deepcopy(plan)
        result = calibrate_plan(plan, [[0, 0], [100, 0]], 1000)
        self.assertEqual(plan, original)
        self.assertEqual(result["units"], "mm")
        self.assertEqual(result["source"]["scale"], "calibrated")
        self.assertEqual(result["revision"], plan["revision"] + 1)
        self.assertEqual(result["scale_reference"]["label"], "Synthetische Referenzkante")
        self.assertEqual(result["scale_reference"]["endpoints"], [[0, 0], [1000, 0]])
        self.assertEqual(result["scale_reference"]["length_mm"], 1000)
        for collection, field in (("walls", "points"), ("fixtures", "points")):
            for before, after in zip(plan[collection], result[collection]):
                self.assertEqual(after[field], [[x * 10, y * 10] for x, y in before[field]])
                self.assertEqual(after["confirmed"], before["confirmed"])
        for collection, field in (("doors", "hinge"), ("regions", "position"), ("opening_candidates", "position"), ("notes", "position")):
            for before, after in zip(plan[collection], result[collection]):
                self.assertEqual(after[field], [value * 10 for value in before[field]])
                if "confirmed" in before:
                    self.assertEqual(after["confirmed"], before["confirmed"])
        self.assertEqual(result["doors"][0]["radius"], plan["doors"][0]["radius"] * 10)
        self.assertEqual(result["doors"][0]["leaf_angle"], plan["doors"][0]["leaf_angle"])
        self.assertEqual(result["devices"][0]["along"], 0.4)
        self.assertEqual(result["devices"][0]["mount_height_mm"], 300)
        self.assertIsNone(validate_plan(result))

    def test_unassigned_scale_reference_is_valid_and_does_not_assert_a_scale(self):
        plan = synthetic_plan()
        plan["scale_reference"] = {"label": "Synthetische Referenzkante", "endpoints": None, "length_mm": None, "status": "unassigned"}
        self.assertIsNone(validate_plan(plan))
        self.assertEqual(plan["units"], "unitless")
        self.assertEqual(plan["source"]["scale"], "unknown")

    def test_calibration_rejects_zero_edge_and_invalid_real_lengths(self):
        cases = [([[0, 0], [0, 0]], 1000), ([[0, 0], [100, 0]], 0), ([[0, 0], [100, 0]], -1), ([[0, 0], [100, 0]], math.nan), ([[0, 0], [100, 0]], math.inf)]
        for endpoints, length in cases:
            with self.subTest(endpoints=endpoints, length=length):
                plan = synthetic_plan()
                original = deepcopy(plan)
                with self.assertRaises(ValueError):
                    calibrate_plan(plan, endpoints, length)
                self.assertEqual(plan, original)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.plan = with_device()

    def read_dxf(self, plan=None, filename="synthetic.dxf"):
        plan = self.plan if plan is None else plan
        path = self.output / filename
        self.assertEqual(export_dxf(plan, path), path)
        return ezdxf.readfile(path)

    def assert_pdf_paths_inside_pages(self, reader):
        total_points = 0
        for page_number, page in enumerate(reader.pages, 1):
            with self.subTest(page=page_number):
                points = pdf_path_points(page, reader)
                total_points += len(points)
                for x, y in points:
                    self.assertTrue(math.isfinite(x) and math.isfinite(y))
                    self.assertGreaterEqual(x, -1)
                    self.assertGreaterEqual(y, -1)
                    self.assertLessEqual(x, float(page.mediabox.width) + 1)
                    self.assertLessEqual(y, float(page.mediabox.height) + 1)
        self.assertGreater(total_points, 8)

    def test_dxf_round_trip_contains_editable_entities_required_layers_and_original_walls(self):
        original = deepcopy(self.plan)
        document = self.read_dxf()
        self.assertEqual(self.plan, original)
        self.assertEqual(document.dxfversion, "AC1024")  # AutoCAD R2010
        self.assertEqual(document.header["$INSUNITS"], 0)
        self.assertFalse(document.audit().errors)
        layers = {layer.dxf.name for layer in document.layers}
        self.assertTrue({"WAENDE", "TUEREN", "RAEUME", "GERAETE", "NOTIZEN", "UNGEKLAERT", "QUELLEN", "EINRICHTUNG"}.issubset(layers))
        model = document.modelspace()
        self.assertTrue({"LINE", "LWPOLYLINE", "ARC", "TEXT", "INSERT"}.issubset({entity.dxftype() for entity in model}))
        expected_edges = []
        for wall in self.plan["walls"]:
            points = [rounded_point(point) for point in wall["points"]]
            expected_edges.extend(zip(points, points[1:]))
        self.assertCountEqual(drawn_edges(model.query('*[layer=="WAENDE"]')), expected_edges)
        self.assertTrue(model.query('LWPOLYLINE[layer=="EINRICHTUNG"]'))
        self.assertTrue(model.query('*[layer=="UNGEKLAERT"]'))
        self.assertTrue(model.query('TEXT[layer=="QUELLEN"]'))
        texts = [entity.dxf.text for entity in model.query("TEXT")]
        self.assertIn("Raum Äöü Test", texts)
        self.assertTrue(any("Maße fehlen" in text for text in texts))
        self.assertFalse(model.query("DIMENSION"))
        arcs = list(model.query('ARC[layer=="TUEREN"]'))
        self.assertEqual(len(arcs), 1)
        self.assertEqual(rounded_point(arcs[0].dxf.center), (10, 0))
        self.assertAlmostEqual(arcs[0].dxf.radius, 8)
        self.assertAlmostEqual(arcs[0].dxf.start_angle, 0)
        self.assertAlmostEqual(arcs[0].dxf.end_angle, 90)
        leaf_edges = drawn_edges(model.query('LINE[layer=="TUEREN"]'))
        self.assertIn(((10, 0), (10, 8)), leaf_edges)

    def test_device_insert_uses_polyline_arclength_and_one_position_symbol_with_quantity(self):
        document = self.read_dxf()
        inserts = list(document.modelspace().query('INSERT[layer=="GERAETE"]'))
        self.assertEqual(len(inserts), 1)
        insert = inserts[0]
        # Rectangle perimeter 320: .4 * 320 = 128, beyond the first corner.
        self.assertEqual(rounded_point(insert.dxf.insert), (100, 28))
        self.assertAlmostEqual(insert.dxf.rotation % 360, 90)
        self.assertAlmostEqual(insert.dxf.xscale, 1)
        self.assertAlmostEqual(insert.dxf.yscale, 1)
        # The transformed tangent and its normal stay unit length.
        angle = math.radians(insert.dxf.rotation)
        tangent = (insert.dxf.xscale * math.cos(angle), insert.dxf.xscale * math.sin(angle))
        normal = (-insert.dxf.yscale * math.sin(angle), insert.dxf.yscale * math.cos(angle))
        self.assertAlmostEqual(math.hypot(*tangent), 1)
        self.assertAlmostEqual(math.hypot(*normal), 1)
        circles = list(document.blocks[insert.dxf.name].query("CIRCLE"))
        self.assertEqual(len(circles), 1)
        self.assertEqual(rounded_point(circles[0].dxf.center), (0, 0))
        self.assertGreater(circles[0].dxf.radius, 0)
        labels = [entity.dxf.text for entity in document.modelspace().query('TEXT[layer=="GERAETE"]')]
        self.assertTrue(any("2× Steckdose" in label for label in labels))
        self.assertTrue(all("doppel" not in label.lower() for label in labels))

    def test_calibrated_dxf_declares_mm_and_uses_scaled_geometry(self):
        plan = calibrate_plan(self.plan, [[0, 0], [100, 0]], 1000)
        document = self.read_dxf(plan, "synthetic-mm.dxf")
        self.assertEqual(document.header["$INSUNITS"], 4)
        insert = next(iter(document.modelspace().query('INSERT[layer=="GERAETE"]')))
        self.assertEqual(rounded_point(insert.dxf.insert), (1000, 280))
        self.assertFalse(document.audit().errors)

    def test_pdf_round_trip_is_a4_landscape_with_readable_german_draft_content(self):
        original = deepcopy(self.plan)
        path = self.output / "synthetic.pdf"
        self.assertEqual(export_pdf(self.plan, path), path)
        self.assertEqual(self.plan, original)
        reader = PdfReader(path)
        self.assertGreaterEqual(len(reader.pages), 1)
        page = reader.pages[0]
        self.assertAlmostEqual(float(page.mediabox.width), 841.8898, delta=1)
        self.assertAlmostEqual(float(page.mediabox.height), 595.2756, delta=1)
        text = page.extract_text()
        self.assertIn(self.plan["title"], text)
        self.assertIn("Entwurf", text)
        self.assertIn("Unskaliert", text)
        self.assertIn("Maße fehlen", text)
        self.assertIn("Raum Äöü Test", text)
        self.assertIn(self.plan["notes"][0]["text"], text)
        self.assertIn(self.plan["devices"][0]["label"], text)
        self.assertNotIn("100 mm", text)
        self.assertNotIn("60 mm", text)

    def test_pdf_fits_large_synthetic_geometry_inside_the_page(self):
        # A deliberately large invented rectangle forces a fit-to-page transform.
        plan = calibrate_plan(self.plan, [[0, 0], [100, 0]], 10000)
        path = self.output / "synthetic-large.pdf"
        export_pdf(plan, path)
        reader = PdfReader(path)
        self.assert_pdf_paths_inside_pages(reader)

    def test_known_unassigned_reference_stays_unscaled_in_pdf_and_dxf(self):
        plan = deepcopy(self.plan)
        plan["scale_reference"] = {"label": "Synthetische Referenzkante", "endpoints": None, "length_mm": 1000, "status": "unassigned"}
        original = deepcopy(plan)
        self.assertIsNone(validate_plan(plan))
        document = self.read_dxf(plan, "synthetic-unassigned.dxf")
        self.assertEqual(document.header["$INSUNITS"], 0)
        path = self.output / "synthetic-unassigned.pdf"
        export_pdf(plan, path)
        first_page = PdfReader(path).pages[0].extract_text()
        self.assertIn("Unskaliert", first_page)
        self.assertIn("Maßreferenz noch nicht zugeordnet", first_page)
        self.assertIn("Synthetische Referenzkante", first_page)
        self.assertIn("1000 mm", first_page)
        self.assertEqual(plan, original)

    def test_repeated_opening_notes_are_counted_once_in_pdf_details(self):
        plan = deepcopy(self.plan)
        note = "Synthetische Markierung prüfen"
        plan["opening_candidates"] = [
            {"id": f"synthetic-opening-{index}", "position": [100, y], "note": note, "confirmed": False}
            for index, y in enumerate((10, 30, 50), 1)
        ]
        path = self.output / "synthetic-repeated-notes.pdf"
        export_pdf(plan, path)
        reader = PdfReader(path)
        self.assertGreater(len(reader.pages), 1)
        details = " ".join(page.extract_text() for page in reader.pages[1:])
        self.assertIn(f"Ungeklärte Markierung (3×): {note}", details)
        self.assertEqual(details.count(note), 1)

    def test_long_edge_labels_wrap_and_keep_complete_text_in_pdf_appendix(self):
        plan = deepcopy(self.plan)
        long_note = ("SynthetischeNotizÄöüß0123456789 " * 80)[:2000]
        long_label = ("SynthetischesLabelÄöüß0123456789" * 10)[:200]
        self.assertEqual(len(long_note), 2000)
        self.assertEqual(len(long_label), 200)
        plan["notes"][0].update(position=[100, 60], text=long_note)
        plan["regions"][0].update(position=[100, 60], label=long_label)
        original = deepcopy(plan)
        path = self.output / "synthetic-long-labels.pdf"
        export_pdf(plan, path)
        reader = PdfReader(path)
        self.assertGreater(len(reader.pages), 1)
        first_page = reader.pages[0].extract_text()
        self.assertIn("…", first_page)
        self.assertNotIn(long_note, first_page)
        appendix = "".join("".join(page.extract_text().split()) for page in reader.pages[1:])
        self.assertIn("".join(long_note.split()), appendix)
        self.assertIn("".join(long_label.split()), appendix)
        self.assert_pdf_paths_inside_pages(reader)
        self.assertEqual(plan, original)


if __name__ == "__main__":
    unittest.main()
