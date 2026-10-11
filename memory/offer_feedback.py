"""Persist independent offer feedback and its history. Consume distinct explicit discard signals to adjust effective priorities, support undo/manual overrides and select local replacement batches."""

import copy
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from uuid import uuid4

from shared.local_storage import read_json, save_json

SIGNAL_THRESHOLD = 3
LEVELS = ("Baja", "Media", "Alta")
CRITERION_FIELDS = {"location": "importancia_ubicacion", "work_mode": "importancia_modalidad", "salary": "importancia_salario"}
REASONS = {"location": "Ubicación", "work_mode": "Modalidad", "salary": "Salario", "responsibilities": "Responsabilidades", "company": "Empresa", "seniority": "Nivel", "other": "Otro"}


def now():
    return datetime.now(timezone.utc).isoformat()


def vacancy_id(listing):
    """Reuse the evaluator's exact vacancy identity, falling back to canonical URLs."""
    identity = tuple(" ".join(str(listing.get(field, "")).casefold().split())
                     for field in ("empresa", "puesto", "ubicacion"))
    if all(identity) and "no documentado" not in identity:
        # This is the same exact grouping already used for evaluated vacancies.
        return hashlib.sha256(repr(identity).encode()).hexdigest()
    url = listing["enlace"]
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in ("gclid", "fbclid")]
    canonical = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(sorted(query)), ""))
    return hashlib.sha256(canonical.encode()).hexdigest()


def declared_priorities(profile):
    return {c: profile.get(field) for c, field in CRITERION_FIELDS.items()}


def load_feedback(path, profile):
    state = read_json(path, None)
    if state is None:
        state = {"version": 1, "threshold": SIGNAL_THRESHOLD, "declared": declared_priorities(profile),
                 "offers": {}, "signals": [], "adjustments": [], "history": []}
    if not isinstance(state, dict) or state.get("version") != 1:
        raise ValueError("No se pudieron leer las acciones guardadas.")
    if sync_manual_priorities(state, profile):
        save_json(path, state)
    return state


def log_event(state, action, **details):
    state["history"].append({"action": action, "date": now(), **details})


def reset_criterion(state, criterion, cause="reset"):
    for adjustment in state["adjustments"]:
        if adjustment["criterion"] == criterion and adjustment["active"]:
            adjustment["active"] = False
    for signal in state["signals"]:
        if signal["reason"] == criterion:
            signal["consumed"] = True
    log_event(state, cause, criterion=criterion)


def sync_manual_priorities(state, profile, edited=()):
    declared = declared_priorities(profile)
    changed = False
    for criterion in CRITERION_FIELDS:
        if state["declared"].get(criterion) != declared[criterion] or criterion in edited:
            reset_criterion(state, criterion, "manual_edit")
            state["history"][-1].update(previous=state["declared"].get(criterion), current=declared[criterion])
            changed = True
    state["declared"] = declared
    return changed


def effective_priorities(state):
    effective = {c: value or "Media" for c, value in state["declared"].items()}
    for adjustment in state["adjustments"]:
        if adjustment["active"]:
            c = adjustment["criterion"]
            effective[c] = adjustment["to"] if adjustment["kind"] == "correction" else LEVELS[min(2, LEVELS.index(effective[c]) + 1)]
    return effective


def effective_profile(state, profile):
    result = copy.deepcopy(profile)
    for c, value in effective_priorities(state).items():
        result[CRITERION_FIELDS[c]] = value
    return result


def apply_adjustments(state):
    threshold = state["threshold"]
    if type(threshold) is not int or threshold < 1:
        raise ValueError("Umbral de aprendizaje inválido.")
    for criterion in CRITERION_FIELDS:
        candidates = [s for s in state["signals"] if s["active"] and not s["consumed"] and
                      s["reason"] == criterion and s["scope"] == "global"]
        unique = {s["vacancy_id"]: s for s in candidates}
        previous = effective_priorities(state)[criterion]
        if len(unique) < threshold or previous == "Alta":
            continue
        signals = list(unique.values())[:threshold]
        # The adjustment starts a new evidence period, including when the
        # configurable threshold was changed after signals were recorded.
        for signal in candidates:
            signal["consumed"] = True
        adjustment = {"id": uuid4().hex, "criterion": criterion, "from": previous,
                      "to": LEVELS[LEVELS.index(previous) + 1], "signals": [s["id"] for s in signals],
                      "active": True, "kind": "automatic", "date": now()}
        state["adjustments"].append(adjustment)
        log_event(state, "priority_increased", adjustment_id=adjustment["id"], criterion=criterion,
                  previous=previous, current=adjustment["to"])


def set_offer_action(state, listing, action, enabled=True, reason=None, text="", scope="specific"):
    if action not in ("saved", "interested", "discarded"):
        raise ValueError("Acción inválida.")
    if type(enabled) is not bool or not isinstance(text, str):
        raise ValueError("Acción o comentario inválidos.")
    if reason is not None and reason not in REASONS or scope not in ("specific", "global"):
        raise ValueError("Motivo inválido.")
    key = vacancy_id(listing)
    record = state["offers"].setdefault(key, {"listing": copy.deepcopy(listing), "saved": False,
                                             "interested": False, "discarded": False})
    record["listing"] = copy.deepcopy(listing)
    if record[action] == enabled:
        return
    record[action] = enabled
    record["date"] = now()
    if action == "discarded":
        if enabled:
            record.update(reason=reason, text=text.strip(), scope=scope, discarded_date=now())
            signal = {"id": uuid4().hex, "vacancy_id": key, "reason": reason,
                      "scope": scope, "date": now(), "active": True, "consumed": False}
            # Repeated undo/discard cycles of one vacancy never create fresh evidence.
            if any(s["vacancy_id"] == key and s["consumed"] for s in state["signals"]):
                signal["consumed"] = True
            state["signals"].append(signal)
            apply_adjustments(state)
        else:
            removed = {s["id"] for s in state["signals"] if s["vacancy_id"] == key and s["active"]}
            for signal in state["signals"]:
                if signal["id"] in removed:
                    signal["active"] = False
            for adjustment in state["adjustments"]:
                if removed.intersection(adjustment["signals"]) and adjustment["active"]:
                    adjustment["active"] = False
                    log_event(state, "adjustment_withdrawn", adjustment_id=adjustment["id"])
    log_event(state, action if enabled else "undo_" + action, vacancy_id=key, reason=reason)


def undo_adjustment(state, identifier):
    adjustment = next(a for a in state["adjustments"] if a["id"] == identifier)
    adjustment["active"] = False
    # Consumed signals remain consumed, preventing immediate repetition.
    log_event(state, "undo_adjustment", adjustment_id=identifier)


def correct_priority(state, criterion, level):
    if criterion not in CRITERION_FIELDS or level not in LEVELS:
        raise ValueError("Prioridad inválida.")
    previous = effective_priorities(state)[criterion]
    reset_criterion(state, criterion, "correct_priority")
    state["history"][-1].update(previous=previous, current=level)
    state["adjustments"].append({"id": uuid4().hex, "criterion": criterion, "from": previous,
        "to": level, "signals": [], "active": True, "kind": "correction", "date": now()})


def available_batch(ranked, state, hidden=(), size=5):
    result, seen = [], set(hidden)
    for item in ranked:
        key = vacancy_id(item["oferta"].model_dump())
        if key in seen or state["offers"].get(key, {}).get("discarded"):
            continue
        seen.add(key)
        result.append(item)
        if len(result) == size:
            break
    return result
