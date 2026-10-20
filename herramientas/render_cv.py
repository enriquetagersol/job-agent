"""Genera un CV en PDF (una página, estilo del CV original) a partir de un JSON con el formato
de cv/cv_maestro.json. Usa Chrome en modo headless, sin dependencias externas.

Uso:
  python3 -I herramientas/render_cv.py <cv.json> <salida.pdf>

En el JSON, los bullets pueden ser texto o {"texto": ...}. Se ignoran las claves que empiezan
por "_" y la marca "(extra)". Opcional: "orden" = lista de secciones
(resumen, experiencia, proyectos, educacion, skills) y "idioma" = "en" | "es".
Si el CV no cabe en una página, reduce la letra hasta 9 pt y avisa si aun así no cabe.
"""
import html, json, os, re, subprocess, sys, tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TITULOS = {
    "en": {"resumen": "", "experiencia": "Professional Experience", "proyectos": "Projects",
           "educacion": "Education", "skills": "Skills & Languages", "cert": "Certifications"},
    "es": {"resumen": "", "experiencia": "Experiencia profesional", "proyectos": "Proyectos",
           "educacion": "Formación", "skills": "Skills e idiomas", "cert": "Certificaciones"},
}


def e(t):
    return html.escape(re.sub(r"\s*\(extra\)", "", t or "").strip())


def texto(b):
    return b["texto"] if isinstance(b, dict) else b


def construir(cv, pt):
    t = TITULOS.get(cv.get("idioma", "en"), TITULOS["en"])
    sec = {}
    sec["resumen"] = f'<p class="resumen">{e(cv.get("resumen"))}</p>' if cv.get("resumen") else ""

    filas = []
    for x in cv.get("experiencia", []):
        cab = f'{e(x["empresa"]).upper()}' + (f' — {e(x["equipo"])}' if x.get("equipo") else "")
        filas.append(f'<div class="item"><div class="cab"><b>{cab}</b> &nbsp;|&nbsp; <b>{e(x["cargo"])}</b>'
                     f' &nbsp;|&nbsp; <b>{e(x["fechas"])}</b></div>')
        bs = [texto(b) for b in x.get("bullets", [])]
        if len(bs) == 1 and not x.get("forzar_lista"):
            filas.append(f'<p>{e(bs[0])}</p>')
        elif bs:
            filas.append("<ul>" + "".join(f"<li>{e(b)}</li>" for b in bs) + "</ul>")
        filas.append("</div>")
    sec["experiencia"] = f'<h2>{t["experiencia"]}</h2>' + "".join(filas) if filas else ""

    pr = []
    for p in cv.get("proyectos", []):
        enl = f' {e(p["enlace"])}' if p.get("enlace") else ""
        pr.append(f'<p class="item"><b>{e(p["nombre"])} — {e(p["contexto"])}</b> &nbsp;|&nbsp; {e(p["texto"])}{enl}</p>')
    sec["proyectos"] = f'<h2>{t["proyectos"]}</h2>' + "".join(pr) if pr else ""

    ed = [f'<p class="item">{e(x["centro"])} &nbsp;|&nbsp; {e(x["titulo"])} ({e(x["fecha"])})</p>'
          for x in cv.get("educacion", [])]
    sec["educacion"] = f'<h2>{t["educacion"]}</h2>' + "".join(ed) if ed else ""

    sk = " • ".join(f'{e(s["categoria"])}: {", ".join(e(i) for i in s["items"])}' for s in cv.get("skills", []))
    extra = ""
    if cv.get("certificaciones"):
        extra += f'<p>{t["cert"]}: {", ".join(e(c) for c in cv["certificaciones"])}</p>'
    if cv.get("idiomas"):
        extra += f'<p>{e(cv["idiomas"])}</p>'
    sec["skills"] = f'<h2>{t["skills"]}</h2><p>{sk}</p>{extra}'

    orden = cv.get("orden") or ["resumen", "experiencia", "proyectos", "educacion", "skills"]
    cuerpo = "".join(sec.get(s, "") for s in orden)
    contacto = " &nbsp;|&nbsp; ".join(e(c) for c in cv.get("contacto", []))
    return f"""<!doctype html><html lang="{cv.get('idioma', 'en')}"><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 11mm 13mm; }}
body {{ font-family: Georgia, 'Times New Roman', serif; font-size: {pt}pt; line-height: 1.22; color: #111; margin: 0; }}
h1 {{ text-align: center; font-size: {pt * 2.1:.1f}pt; letter-spacing: .5px; margin: 0 0 2px; }}
.contacto {{ text-align: center; margin: 0 0 4px; }}
.resumen {{ text-align: justify; margin: 0 0 2px; }}
h2 {{ color: #1f3a5f; font-size: {pt * 1.12:.1f}pt; text-transform: uppercase; border-bottom: 1px solid #8a9bb3;
      margin: 7px 0 3px; padding-bottom: 1px; }}
p {{ margin: 0 0 2px; text-align: justify; }}
.item {{ margin-bottom: 3px; }}
.cab {{ margin-top: 2px; }}
ul {{ margin: 1px 0 3px 15px; padding: 0; }}
li {{ margin: 0 0 1px; text-align: justify; }}
</style></head><body><h1>{e(cv['nombre']).upper()}</h1><p class="contacto">{contacto}</p>{cuerpo}</body></html>"""


def paginas(pdf):
    datos = open(pdf, "rb").read()
    return len(re.findall(rb"/Type\s*/Page[^s]", datos))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    cv = json.load(open(sys.argv[1]))
    salida = os.path.abspath(sys.argv[2])
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    html_path = os.path.splitext(salida)[0] + ".html"
    for pt in (10, 9.7, 9.4, 9.2, 9):
        with open(html_path, "w") as f:
            f.write(construir(cv, pt))
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={salida}", "file://" + html_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        n = paginas(salida)
        if n <= 1:
            print(f"OK: 1 página, letra {pt} pt → {salida}")
            return
    print(f"AVISO: no cabe en una página ({n} páginas con 9 pt). Recorta contenido → {salida}")


if __name__ == "__main__":
    main()
