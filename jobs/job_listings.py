"""Filter locally supplied job listings for description availability and duplicate URLs. Support the command-line recommendation workflow with retrieval prerequisites."""

from urllib.parse import urlsplit, urlunsplit


def filter_listings(job_listings):
    """Keep listings with a retrieved description and a unique HTTP URL.

    Each listing must contain enlace, fuente and descripcion_recuperada.
    Search must populate descripcion_recuperada with text
    retrieved from the publication, never with model-generated text.
    """
    result = []
    seen_urls = set()
    for listing in job_listings:
        if not isinstance(listing, dict):
            continue
        description = listing.get("descripcion_recuperada")
        url = listing.get("enlace")
        source = listing.get("fuente")
        if not isinstance(description, str) or not description.strip():
            continue
        if not isinstance(source, str) or not source.strip():
            continue
        if not isinstance(url, str):
            continue
        try:
            parts = urlsplit(url.strip())
            if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
                continue
            # The URL fragment does not identify another listing; preserve the query,
            # which may contain the vacancy identifier.
            normalized = urlunsplit((
                parts.scheme.lower(), parts.netloc.lower(),
                parts.path or "/", parts.query, "",
            ))
        except ValueError:
            continue
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        result.append({**listing, "enlace": normalized})
    return result
