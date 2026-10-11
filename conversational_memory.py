"""Explicit conversational search preferences, separate from confirmed CV facts."""
from user_profile import migrate_profile, normalize_identity


def change_preference(profile, text, remember=True):
    if not isinstance(text, str) or type(remember) is not bool:
        raise ValueError('Preferencia inválida.')
    text = ' '.join(text.split())
    if not text or len(text) > 400:
        raise ValueError('Indica una preferencia de búsqueda válida.')
    updated = migrate_profile(profile)
    values = updated.setdefault('conversation_preferences', [])
    existing = any(normalize_identity(value) == normalize_identity(text) for value in values)
    if remember and not existing:
        values.append(text)
    elif not remember and existing:
        updated['conversation_preferences'] = [value for value in values if normalize_identity(value) != normalize_identity(text)]
    return updated, existing != remember
