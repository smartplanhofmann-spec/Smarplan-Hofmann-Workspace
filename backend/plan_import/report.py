"""Standalone, offline review of source previews and uncertain candidates."""
import base64
import html
import json
import math


def _escape(value):
    return html.escape(str(value), quote=True)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Non-finite candidate coordinate")
    if not 0 <= value <= 1:
        raise ValueError("Candidate coordinate outside the source preview")
    return value


def build_review(png_bytes, result):
    """No remote resources, raw OCR HTML, or executable document contents."""
    width, height = result["preview"]["width"], result["preview"]["height"]
    analysis = result["analysis"]
    lines = []
    for item in analysis["line_candidates"]:
        x1, y1 = (_number(v) for v in item["start"])
        x2, y2 = (_number(v) for v in item["end"])
        lines.append(
            f'<line x1="{x1*width:.3f}" y1="{y1*height:.3f}" '
            f'x2="{x2*width:.3f}" y2="{y2*height:.3f}"/>'
        )
    boxes, rows = [], []
    texts = [("Drucktext-OCR", word) for word in analysis["text_candidates"]]
    texts += [("PDF-Text", word) for word in result.get("pdf_text", [])]
    for index, (kind, word) in enumerate(texts):
        left, top, right, bottom = (_number(v) for v in word["bbox"])
        if left > right or top > bottom:
            raise ValueError("Inverted candidate box")
        boxes.append(
            f'<rect id="box-{index}" x="{left*width:.3f}" y="{top*height:.3f}" '
            f'width="{(right-left)*width:.3f}" height="{(bottom-top)*height:.3f}"/>'
        )
        rows.append(
            f'<button class="word" data-box="box-{index}" type="button">'
            f'<small>{kind}</small>{_escape(word["text"])}</button>'
        )
    warnings = "".join(f"<li>{_escape(value)}</li>" for value in result.get("warnings", []))
    metadata = _escape(json.dumps(result["source"], ensure_ascii=False, indent=2, allow_nan=False))
    image_data = base64.b64encode(png_bytes).decode("ascii")
    template = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>Planimport · Prüfung</title>
<style>
:root{font-family:system-ui,sans-serif;color:#172b3b;background:#eef3f6}*{box-sizing:border-box}
body{margin:0}header{padding:22px 28px;background:#fff;border-bottom:1px solid #d7e0e6}
h1{font-size:24px;margin:4px 0 10px}p{line-height:1.5;margin:7px 0}
.badge{font-size:12px;font-weight:650;color:#765116;background:#fff3d5;border-radius:20px;padding:5px 10px}
.controls{display:flex;flex-wrap:wrap;align-items:center;gap:18px;margin-top:18px;font-size:14px}
main{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:18px;padding:18px}
.viewer{height:72vh;overflow:auto;background:#dbe4e9;padding:18px;border-radius:12px}
svg{display:block;width:100%;height:auto;background:white;box-shadow:0 4px 22px #17334725}
.lines{stroke:#078d78;stroke-width:1.4;fill:none;opacity:.75}
.textboxes{stroke:#d4870f;stroke-width:1.3;fill:#ffe4a014}
.selected{stroke:#d52e5f!important;stroke-width:3!important;fill:#d52e5f26}
aside{max-height:72vh;overflow:auto;background:white;border-radius:12px;padding:16px}
h2{font-size:17px;margin:0 0 10px}.word{display:block;background:#f7f9fb;border:1px solid #e0e8ed;border-radius:7px;width:100%;padding:9px;text-align:left;margin:7px 0;cursor:pointer;color:inherit}
small{display:block;color:#647782;font-size:11px;margin-bottom:3px}
details{margin:0 18px 18px;padding:14px 18px;background:white;border-radius:10px}
summary{cursor:pointer}pre{white-space:pre-wrap;word-break:break-all;font-size:12px}
li{font-size:13px;margin:5px 0}@media(max-width:800px){main{grid-template-columns:1fr}header{padding:18px}.viewer{height:62vh}aside{max-height:35vh}}
</style></head><body>
<header><span class="badge">Zur Prüfung · nicht maßstäblich</span><h1>Planimport</h1>
<p>Die ausgewählte Quelle bleibt erhalten. Grün markiert automatisch gefundene Linien; Gelb markiert Textstellen.</p>
<p>Linien sind noch keine bestätigten Wände. Handschrift, Durchstreichungen und Maße wurden nicht fachlich interpretiert.</p>
<div class="controls">
<label><input id="lines-switch" type="checkbox" checked> Linienvorschläge</label>
<label><input id="text-switch" type="checkbox"> Textstellen</label>
<label>Zoom <input id="zoom" type="range" min="100" max="300" value="100" step="25"></label>
<span>__LINECOUNT__ Linien · __TEXTCOUNT__ Textstellen</span>
</div></header>
<main><section class="viewer" aria-label="Quellvorschau mit Erkennungsebenen">
<svg id="canvas" role="img" aria-label="Erkennung auf der erhaltenen Quellvorschau" viewBox="0 0 __WIDTH__ __HEIGHT__">
<image width="__WIDTH__" height="__HEIGHT__" href="data:image/png;base64,__IMAGE__"/>
<g id="line-layer" class="lines">__LINES__</g>
<g id="text-layer" class="textboxes" style="display:none">__BOXES__</g>
</svg></section><aside><h2>Erkannte Textstellen</h2><p>Zum Hervorheben anklicken und mit der Quelle vergleichen.</p>__ROWS__</aside></main>
<details><summary>Hinweise zur Erkennung und Herkunft</summary><ul>__WARNINGS__</ul><pre>__METADATA__</pre></details>
<script>
const lines=document.getElementById('line-layer'), texts=document.getElementById('text-layer');
document.getElementById('lines-switch').addEventListener('change',function(){lines.style.display=this.checked?'':'none'});
document.getElementById('text-switch').addEventListener('change',function(){texts.style.display=this.checked?'':'none'});
document.getElementById('zoom').addEventListener('input',function(){document.getElementById('canvas').style.width=this.value+'%'});
document.querySelectorAll('.word').forEach(function(button){button.addEventListener('click',function(){
document.querySelectorAll('.selected').forEach(function(node){node.classList.remove('selected')});
texts.style.display='';document.getElementById('text-switch').checked=true;
document.getElementById(button.dataset.box).classList.add('selected');
})});
</script></body></html>"""
    replacements = {
        "__LINECOUNT__": str(len(lines)), "__TEXTCOUNT__": str(len(texts)),
        "__WIDTH__": str(width), "__HEIGHT__": str(height), "__IMAGE__": image_data,
        "__LINES__": "".join(lines), "__BOXES__": "".join(boxes),
        "__ROWS__": "".join(rows) or "<p>Keine Textstellen erkannt.</p>",
        "__WARNINGS__": warnings, "__METADATA__": metadata,
    }
    # Replace all slots in one pass: imported text can never become a template.
    import re
    return re.sub(r"__[A-Z]+__", lambda m: replacements[m.group()], template).encode("utf-8")
