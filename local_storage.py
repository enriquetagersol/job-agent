"""Backward-compatible profiles and private local evaluations."""

import hashlib
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROFILE_FILE = BASE_DIR / 'user_profile.json'
EVALUATIONS_FILE = BASE_DIR / '.local_data' / 'evaluations.json'
DATA_VERSION = 3


def migrate_legacy_files(base_dir):
    """Rename private files without rewriting data or overwriting existing files."""
    base_dir = Path(base_dir)
    for old_name, new_name in (("perfil.json", "user_profile.json"), ("perfil.tmp", "user_profile.tmp")):
        old_file, new_file = base_dir / old_name, base_dir / new_name
        if old_file.exists() and not new_file.exists():
            old_file.rename(new_file)
    old_dir, new_dir = base_dir / ".datos", base_dir / ".local_data"
    if old_dir.exists() and not new_dir.exists():
        old_dir.rename(new_dir)
    if old_dir.exists():
        new_dir.mkdir(exist_ok=True)
        for old_file in old_dir.iterdir():
            destination = new_dir / old_file.name
            if old_file.is_file() and not destination.exists():
                old_file.rename(destination)
        if not any(old_dir.iterdir()):
            old_dir.rmdir()
    for old_name, new_name in (("evaluaciones.json", "evaluations.json"), ("diagnostico.json", "diagnostics.json")):
        old_file, new_file = new_dir / old_name, new_dir / new_name
        if old_file.exists() and not new_file.exists():
            old_file.rename(new_file)


def read_json(file_path, default=None):
    if not file_path.exists():
        return default
    return json.loads(file_path.read_text(encoding="utf-8"))


def save_json(file_path, content):
    file_path = Path(file_path)
    if file_path.resolve() == PROFILE_FILE.resolve() and isinstance(content, dict):
        from career_history import validate_entry
        previous = read_json(file_path, {})
        for field in ("experiencias", "formacion", "proyectos"):
            for entry in content.get(field, []):
                old_entry = next((e for e in previous.get(field, []) if e.get("id") == entry.get("id")), None)
                if entry != old_entry:
                    validate_entry(field, entry)
    if file_path.resolve() == PROFILE_FILE.resolve() and isinstance(content, dict) and content.get("version_perfil") == 3:
        from user_profile import validate_profile
        validate_profile(content, previous=read_json(file_path, {}))
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = file_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(file_path)


def load_profile():
    migrate_legacy_files(PROFILE_FILE.parent)
    profile = read_json(PROFILE_FILE, {})
    if not isinstance(profile, dict):
        raise ValueError("Perfil inválido")
    return profile


def search_context(profile):
    from user_profile import migrate_profile, profile_for_model
    current = migrate_profile(profile)
    from career_history import employer_to_exclude
    return {"perfil": profile_for_model(current),
            "empresa_excluida": employer_to_exclude(current).strip() if current["excluir_empresa_actual"] else ""}


def context_fingerprint(context):
    content = json.dumps({"version": DATA_VERSION, **context}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def load_evaluations():
    migrate_legacy_files(EVALUATIONS_FILE.parent.parent)
    data = read_json(EVALUATIONS_FILE, None)
    if data is not None and (not isinstance(data, dict) or data.get("version") != DATA_VERSION):
        return None
    return data


def save_evaluations(context, result):
    data = {"version": DATA_VERSION, "huella": context_fingerprint(context),
             "contexto": context, **result}
    save_json(EVALUATIONS_FILE, data)
    return data
