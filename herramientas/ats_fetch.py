"""Descarga ofertas de las APIs públicas de empleo (Ashby, Greenhouse, Lever, Workable, Teamtailor,
Recruitee y Personio) de las empresas
listadas en empresas.json, filtra por título y ubicación, y guarda cada oferta con su descripción
completa en <salida>/ofertas/<id>.txt más un índice <salida>/candidatas.json.

Uso:
  python3 -I herramientas/ats_fetch.py <salida> --titulo "<regex>" --ubicacion "<regex>"
"""
import argparse, concurrent.futures as cf, datetime, html, json, os, re, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|director|head|lead|vp|chief|manager,|engineering manager"
                    r"|intern|internship|werkstudent|working student)\b", re.I)


try:  # algunos Python (p. ej. el de python.org) no traen certificados: usa los de certifi si está
    import certifi
    import ssl
    _CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _CTX = None


def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25, context=_CTX) as r:
            return json.load(r)
    except Exception:
        return None


def strip(h):
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"<[^>]+>", "\n", html.unescape(h or ""))).strip()


def ashby(c):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{c}?includeCompensation=true")
    res = []
    for j in (d or {}).get("jobs", []):
        loc = " / ".join([j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []])
        if j.get("isRemote"):
            loc += " (remote)"
        res.append(dict(company=c, title=j.get("title", ""), location=loc, url=j.get("jobUrl"),
                        date=(j.get("publishedAt") or "")[:10],
                        salary=(j.get("compensation") or {}).get("compensationTierSummary") or "",
                        emp=j.get("employmentType", ""), text=j.get("descriptionPlain", "")))
    return res


def greenhouse(c):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{c}/jobs?content=true")
    return [dict(company=c, title=j.get("title", ""), location=(j.get("location") or {}).get("name", ""),
                 url=j.get("absolute_url"), date=(j.get("updated_at") or "")[:10], salary="", emp="",
                 text=strip(j.get("content", ""))) for j in (d or {}).get("jobs", [])]


def lever(c):
    res = []
    for j in get(f"https://api.lever.co/v0/postings/{c}?mode=json") or []:
        cat = j.get("categories", {})
        lists = "\n".join(l.get("text", "") + "\n" + strip(l.get("content", "")) for l in j.get("lists", []))
        sr = j.get("salaryRange") or {}
        sal = f"{sr.get('min')}-{sr.get('max')} {sr.get('currency', '')} {sr.get('interval', '')}" if sr else ""
        loc = " / ".join(cat.get("allLocations") or [cat.get("location", "")])
        if j.get("workplaceType"):
            loc += f" ({j['workplaceType']})"
        date = datetime.datetime.utcfromtimestamp(j["createdAt"] / 1000).strftime("%Y-%m-%d") if j.get("createdAt") else ""
        text = "\n\n".join([j.get("descriptionPlain", ""), lists, j.get("additionalPlain", "")]).strip()
        res.append(dict(company=c, title=j.get("text", ""), location=loc, url=j.get("hostedUrl"), date=date,
                        salary=sal, emp=cat.get("commitment", ""), text=text))
    return res


def workable(c):
    d = get(f"https://apply.workable.com/api/v1/widget/accounts/{c}?details=true")
    res = []
    for j in (d or {}).get("jobs", []):
        loc = ", ".join(x for x in [j.get("city"), j.get("country")] if x)
        if j.get("telecommuting"):
            loc += " (remote)"
        res.append(dict(company=c, title=j.get("title", ""), location=loc, url=j.get("url") or j.get("shortlink"),
                        date=(j.get("published_on") or j.get("created_at") or "")[:10], salary="",
                        emp=j.get("employment_type", ""), text=strip(j.get("description", ""))))
    return res


def _texto(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25, context=_CTX) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception:
        return None


def teamtailor(c):
    import xml.etree.ElementTree as ET
    x = _texto(f"https://{c}.teamtailor.com/jobs.rss")
    if not x or "<rss" not in x:
        return []
    ns = {"tt": "https://teamtailor.com/locations"}
    res = []
    try:
        canal = ET.fromstring(x).find("channel")
    except ET.ParseError:
        return []
    for it in canal.findall("item"):
        locs = [", ".join(t for t in [l.findtext("tt:city", "", ns), l.findtext("tt:country", "", ns)] if t)
                for l in it.findall("tt:locations/tt:location", ns)]
        remoto = (it.findtext("remoteStatus") or "").strip()
        loc = " / ".join(l for l in locs if l) + (f" ({remoto})" if remoto and remoto != "none" else "")
        fecha = ""
        try:
            fecha = datetime.datetime.strptime((it.findtext("pubDate") or "")[:16], "%a, %d %b %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
        res.append(dict(company=c, title=(it.findtext("title") or "").strip(), location=loc, url=it.findtext("link"),
                        date=fecha, salary="", emp="", text=strip(it.findtext("description") or "")))
    return res


def recruitee(c):
    d = get(f"https://{c}.recruitee.com/api/offers/")
    res = []
    for o in (d or {}).get("offers", []):
        loc = o.get("location") or ", ".join(x for x in [o.get("city"), o.get("country")] if x)
        if o.get("remote"):
            loc += " (remote)"
        res.append(dict(company=c, title=o.get("title", ""), location=loc, url=o.get("careers_url"),
                        date=(o.get("published_at") or "")[:10], salary="", emp=o.get("employment_type_code", ""),
                        text=strip((o.get("description") or "") + "\n" + (o.get("requirements") or ""))))
    return res


def personio(c):
    import xml.etree.ElementTree as ET
    x = _texto(f"https://{c}.jobs.personio.de/xml")
    if not x or "<position" not in x:
        return []
    try:
        raiz = ET.fromstring(x)
    except ET.ParseError:
        return []
    res = []
    for p in raiz.findall("position"):
        partes = [f"{d.findtext('name', '')}\n{d.findtext('value', '')}" for d in p.findall("jobDescriptions/jobDescription")]
        res.append(dict(company=c, title=(p.findtext("name") or "").strip(), location=(p.findtext("office") or "").strip(),
                        url=f"https://{c}.jobs.personio.de/job/{p.findtext('id')}",
                        date=(p.findtext("createdAt") or "")[:10], salary="",
                        emp=(p.findtext("employmentType") or ""), text=strip("\n\n".join(partes))))
    return res


def descargar(titulo, ubicacion):
    """Descarga las ofertas de todas las empresas de empresas.json y devuelve las que encajan con
    las regex de título y ubicación (sin duplicados). Cada oferta trae el texto completo."""
    titulo = re.compile(titulo, re.I) if isinstance(titulo, str) else titulo
    ubic = re.compile(ubicacion, re.I) if isinstance(ubicacion, str) else ubicacion
    empresas = json.load(open(os.path.join(AQUI, "empresas.json")))
    fn = {"ashby": ashby, "greenhouse": greenhouse, "lever": lever, "workable": workable,
          "teamtailor": teamtailor, "recruitee": recruitee, "personio": personio}
    tareas = [(fn[ats], c) for ats in fn for c in empresas.get(ats, [])]
    todas, boards = [], 0
    with cf.ThreadPoolExecutor(24) as ex:
        for r in ex.map(lambda t: t[0](t[1]), tareas):
            if r:
                boards += 1
                todas += r
    vistas, keep = set(), []
    for j in todas:
        if not (ubic.search(j["location"]) and titulo.search(j["title"])):
            continue
        k = (j["company"], j["title"].lower(), j["location"].lower())
        if k in vistas:
            continue
        vistas.add(k)
        j["senior"] = bool(SENIOR.search(j["title"]))
        keep.append(j)
    return keep, {"boards": boards, "empresas": len(tareas), "total": len(todas)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("salida")
    ap.add_argument("--titulo", required=True, help="regex de títulos a incluir")
    ap.add_argument("--ubicacion", required=True, help="regex de ubicaciones a incluir")
    a = ap.parse_args()
    keep, est = descargar(a.titulo, a.ubicacion)
    os.makedirs(os.path.join(a.salida, "ofertas"), exist_ok=True)
    for i, j in enumerate(keep):
        j["id"] = f"o{i:03d}"
        with open(os.path.join(a.salida, "ofertas", j["id"] + ".txt"), "w") as f:
            f.write(f"EMPRESA: {j['company']}\nPUESTO: {j['title']}\nUBICACION: {j['location']}\nURL: {j['url']}\n"
                    f"FECHA: {j['date']}\nSALARIO: {j['salary'] or 'no publicado'}\n"
                    f"CONTRATO: {j['emp'] or 'desconocido'}\n\n{j['text']}\n")
    json.dump([{k: v for k, v in j.items() if k != "text"} for j in keep],
              open(os.path.join(a.salida, "candidatas.json"), "w"), indent=1, ensure_ascii=False)
    n_senior = sum(j["senior"] for j in keep)
    print(f"boards con datos: {est['boards']}/{est['empresas']} · ofertas totales: {est['total']} · "
          f"filtradas: {len(keep)} (senior/lead/prácticas: {n_senior})")


if __name__ == "__main__":
    main()
