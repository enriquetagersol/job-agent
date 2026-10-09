"""Comprobaciones locales para las ofertas que recupere la futura búsqueda."""

from urllib.parse import urlsplit, urlunsplit


def filtrar_ofertas(ofertas):
    """Conserva ofertas con descripción recuperada y enlace HTTP único.

    Cada oferta debe contener enlace, fuente y descripcion_recuperada.
    La futura búsqueda debe rellenar descripcion_recuperada con el texto
    obtenido de la publicación, nunca con texto generado por el modelo.
    """
    resultado = []
    enlaces_vistos = set()
    for oferta in ofertas:
        if not isinstance(oferta, dict):
            continue
        descripcion = oferta.get("descripcion_recuperada")
        enlace = oferta.get("enlace")
        fuente = oferta.get("fuente")
        if not isinstance(descripcion, str) or not descripcion.strip():
            continue
        if not isinstance(fuente, str) or not fuente.strip():
            continue
        if not isinstance(enlace, str):
            continue
        try:
            partes = urlsplit(enlace.strip())
            if partes.scheme.lower() not in ("http", "https") or not partes.hostname:
                continue
            # El fragmento no identifica otra oferta; conserva la consulta,
            # porque puede contener el identificador de la vacante.
            normalizado = urlunsplit((
                partes.scheme.lower(), partes.netloc.lower(),
                partes.path or "/", partes.query, "",
            ))
        except ValueError:
            continue
        if normalizado in enlaces_vistos:
            continue
        enlaces_vistos.add(normalizado)
        resultado.append({**oferta, "enlace": normalizado})
    return resultado
