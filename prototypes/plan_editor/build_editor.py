"""Render the offline plan editor with an embedded model; standard library only."""
import argparse
import json
from pathlib import Path


def render_editor(plan, path):
    """Write a standalone HTML editor and return its output Path.

    Models can contain private project data. Callers choose their own output
    location; no project model or media is copied into the source directory.
    """
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("Planmodell mit schema_version=1 erforderlich")
    encoded = json.dumps(plan, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    # JSON lives in an HTML script data block. Escape HTML delimiters so even a
    # title containing </script> stays data rather than becoming executable HTML.
    encoded = (encoded.replace("&", "\\u0026").replace("<", "\\u003c")
               .replace(">", "\\u003e").replace("\u2028", "\\u2028")
               .replace("\u2029", "\\u2029"))
    template = Path(__file__).with_name("editor.html").read_text(encoding="utf-8")
    if template.count("__PLAN_JSON__") != 1:
        raise RuntimeError("Eindeutiger Modell-Platzhalter fehlt")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace("__PLAN_JSON__", encoded), encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description="Lokalen Planeditor als HTML erzeugen")
    parser.add_argument("model", type=Path, help="Planmodell als JSON")
    parser.add_argument("output", type=Path, help="Ziel der eigenständigen HTML-Datei")
    arguments = parser.parse_args()
    plan = json.loads(arguments.model.read_text(encoding="utf-8"))
    render_editor(plan, arguments.output)
    print(arguments.output)


if __name__ == "__main__":
    main()
