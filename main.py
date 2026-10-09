import json
from pathlib import Path


archivo_perfil = Path(__file__).parent / "perfil.json"
perfil = None
campos_nuevos = {
    "experiencia_profesional": "Experiencia profesional",
    "capacidades": "Capacidades",
    "preferencias_laborales": "Preferencias laborales (salario, remoto/presencial y otras condiciones)",
}

if archivo_perfil.exists():
    try:
        perfil = json.loads(archivo_perfil.read_text(encoding="utf-8"))
        if not isinstance(perfil, dict) or not all(
            isinstance(perfil.get(campo), str) for campo in ("puesto", "ubicacion")
        ):
            perfil = None
    except (json.JSONDecodeError, UnicodeDecodeError):
        perfil = None

    if perfil is None:
        print("No se pudo leer el perfil. Introduce tus preferencias de nuevo.")

if perfil is not None:
    print("\nTus preferencias guardadas:")
    print("Puesto:", perfil["puesto"])
    print("Ubicación:", perfil["ubicacion"])
    for campo, etiqueta in campos_nuevos.items():
        if campo in perfil:
            print(etiqueta + ":", perfil[campo])

    cambiar = input("¿Quieres cambiarlas? (s/n): ").strip().lower()
    while cambiar not in ("s", "sí", "si", "n", "no"):
        cambiar = input("Escribe s para cambiar o n para conservar: ").strip().lower()
else:
    cambiar = "s"

guardar = cambiar in ("s", "sí", "si")
if guardar:
    puesto = input("¿Qué puesto buscas? ")
    ubicacion = input("¿En qué ubicación quieres trabajar? ")
    if perfil is None:
        perfil = {}
    perfil.update({"puesto": puesto, "ubicacion": ubicacion})

for campo, etiqueta in campos_nuevos.items():
    if cambiar in ("s", "sí", "si") or campo not in perfil:
        perfil[campo] = input(etiqueta + ": ")
        guardar = True

if guardar:
    archivo_perfil.write_text(
        json.dumps(perfil, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("\nPreferencias guardadas en perfil.json.")
else:
    print("\nConservamos tus preferencias guardadas.")

print("\nTus preferencias de búsqueda:")
print("Puesto:", perfil["puesto"])
print("Ubicación:", perfil["ubicacion"])
for campo, etiqueta in campos_nuevos.items():
    print(etiqueta + ":", perfil[campo])
