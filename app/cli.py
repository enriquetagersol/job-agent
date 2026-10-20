"""CLI de datos para el agente (comandos de Claude Code). Usa la misma capa que la app web.

Ejemplos:
  python3 -I app/cli.py resumen
  python3 -I app/cli.py candidaturas [--estado enviada]
  python3 -I app/cli.py ofertas [--pendientes] [--sin-aprender]
  python3 -I app/cli.py urls-vistas                      # para no repetir ofertas en /buscar
  python3 -I app/cli.py importar-ofertas fichas.json --informe resultados/AAAA-MM-DD.md
  python3 -I app/cli.py decidir o012 "no interesa" --motivo "tiene cuota"
  python3 -I app/cli.py aprendidas o012 o013             # tras aplicar el aprendizaje de /revisar
  python3 -I app/cli.py nueva-candidatura "Empresa" "Puesto" --estado enviada --url ... --detalle ...
  python3 -I app/cli.py actualizar c016 --estado enviada --nota "Aplicada con CV adaptado" \
        --cv cv/adaptados/.../CV.pdf --proximo "2026-10-25|Follow-up si no hay respuesta" \
        --fecha-novedad 2026-10-20     # fecha real de la novedad (si no, se usa la de hoy)
  python3 -I app/cli.py sugerir c016 | --todas           # recalcula el próximo paso sugerido
Al apuntar una novedad (--nota o --estado) sin --proximo, el próximo paso lo sugiere Job Agent.
Si la novedad sale de un correo, añade --origen correo (la app la marca con 📧).

importar-ofertas espera un JSON con una lista de objetos con las claves del modelo Oferta
(ver app/datos.py): url, empresa, puesto, encaje, estado_analisis, motivo_descarte, datos,
empresa_desc, sencillo{que_harias, que_piden, que_ofrecen, por_que_encaja, gaps, candidatura},
puntuacion, rasgos.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datos  # noqa: E402
import sugerencias_ia  # noqa: E402


def _imprimir(x):
    print(json.dumps(x, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("resumen")
    p = sub.add_parser("candidaturas"); p.add_argument("--estado")
    p = sub.add_parser("ofertas"); p.add_argument("--pendientes", action="store_true")
    p.add_argument("--sin-aprender", action="store_true")
    sub.add_parser("urls-vistas")
    p = sub.add_parser("importar-ofertas"); p.add_argument("fichero"); p.add_argument("--informe", default="")
    p = sub.add_parser("decidir"); p.add_argument("id"); p.add_argument("valor", choices=datos.DECISIONES)
    p.add_argument("--motivo", default="")
    p = sub.add_parser("aprendidas"); p.add_argument("ids", nargs="+")
    p = sub.add_parser("nueva-candidatura"); p.add_argument("empresa"); p.add_argument("puesto")
    p.add_argument("--estado", default="por_aplicar", choices=datos.ESTADOS)
    for k in ("url", "detalle", "contacto", "cv", "oferta"):
        p.add_argument(f"--{k}", default="")
    p = sub.add_parser("actualizar"); p.add_argument("id")
    p.add_argument("--estado", choices=datos.ESTADOS)
    for k in ("detalle", "contacto", "url", "cv", "nota", "proximo", "fecha-aplicacion", "fecha-novedad", "origen"):
        p.add_argument(f"--{k}")
    p = sub.add_parser("sugerir"); p.add_argument("ids", nargs="*"); p.add_argument("--todas", action="store_true")
    a = ap.parse_args()

    if a.cmd == "resumen":
        m = datos.metricas()
        _imprimir({k: m[k] for k in ("por_estado", "total_aplicadas", "tasa_respuesta", "pendientes_decidir",
                                     "decisiones_sin_aprender")})
        s = datos.seguimiento()
        print(f"Sin novedad ≥{s['umbral_dias']} días: " + ", ".join(f"{c['empresa']} ({c['dias']}d)" if c["dias"] is not None
                                                                  else f"{c['empresa']} (fecha desconocida)"
                                                                  for c in s["sin_novedad"]))
    elif a.cmd == "candidaturas":
        _imprimir([c for c in datos.candidaturas() if not a.estado or c["estado"] == a.estado])
    elif a.cmd == "ofertas":
        os_ = datos.ofertas()
        if a.pendientes:
            os_ = [o for o in os_ if o["estado_analisis"] == "recomendada" and not o.get("decision")]
        if a.sin_aprender:
            os_ = [o for o in os_ if (o.get("decision") or {}).get("aprendida") is False]
        _imprimir(os_)
    elif a.cmd == "urls-vistas":
        urls = {o["url"] for o in datos.ofertas()} | {c["url"] for c in datos.candidaturas() if c.get("url")}
        print("\n".join(sorted(u for u in urls if u)))
    elif a.cmd == "importar-ofertas":
        nuevas = json.load(open(a.fichero, encoding="utf-8"))
        print("añadidas %d · actualizadas %d" % datos.importar_ofertas(nuevas, a.informe))
    elif a.cmd == "decidir":
        _imprimir(datos.decidir_oferta(a.id, a.valor, a.motivo))
    elif a.cmd == "aprendidas":
        datos.marcar_decisiones_aprendidas(set(a.ids)); print("ok")
    elif a.cmd == "nueva-candidatura":
        _imprimir(datos.crear_candidatura(a.empresa, a.puesto, a.estado, url=a.url, detalle=a.detalle,
                                          contacto=a.contacto, cv_adaptado=a.cv, oferta_id=a.oferta or None))
    elif a.cmd == "actualizar":
        campos = {k: v for k, v in {"estado": a.estado, "detalle": a.detalle, "contacto": a.contacto,
                                    "url": a.url, "cv_adaptado": a.cv,
                                    "fecha_aplicacion": a.fecha_aplicacion}.items() if v is not None}
        if a.proximo is not None:
            f, _, t = a.proximo.partition("|")
            campos["proximo_paso"] = {"fecha": f.strip(), "texto": t.strip()} if t.strip() else None
        # --fecha-novedad: fecha real de la novedad (p. ej. la del correo), no la de hoy
        c = datos.actualizar_candidatura(a.id, nota=a.nota, fecha_nota=a.fecha_novedad, origen=a.origen, **campos)
        if sugerencias_ia.hay_novedad(campos, a.nota):  # próximo paso sugerido por Job Agent
            c["proximo_paso"] = sugerencias_ia.sugerir(a.id)
        _imprimir(c)
    elif a.cmd == "sugerir":
        _imprimir(sugerencias_ia.sugerir_todas() if a.todas else {i: sugerencias_ia.sugerir(i) for i in a.ids})


if __name__ == "__main__":
    main()
