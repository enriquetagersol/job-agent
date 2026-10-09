"""English Python fields with backward-compatible Spanish JSON aliases."""

from pydantic import BaseModel, ConfigDict

WIRE_ALIASES = {
    'skill': 'skill',
    'field': 'campo',
    'entry_id': 'entrada_id',
    'quote': 'cita',
    'suggestions': 'propuestas',
    'name': 'nombre',
    'points': 'puntos',
    'reason': 'motivo',
    'listing_evidence': 'evidencia_oferta',
    'profile_evidence': 'evidencia_perfil',
    'compatible_option': 'opcion_compatible',
    'compatibility': 'compatibilidad',
    'profile_evidence_quotes': 'evidencias_perfil',
    'listing_evidence_quotes': 'evidencias_oferta',
    'declared_skills': 'skills_declaradas',
    'original_evaluation_json': 'evaluacion_original_json',
    'minimum': 'minimo',
    'maximum': 'maximo',
    'currency': 'moneda',
    'period': 'periodo',
    'kind': 'tipo',
    'evidence': 'evidencia',
    'url': 'enlace',
    'role': 'puesto',
    'company': 'empresa',
    'location': 'ubicacion',
    'documented_responsibility': 'responsabilidad_documentada',
    'documented_requirement': 'requisito_documentado',
    'criteria': 'criterios',
    'documented_salary': 'salario_documentado',
    'gaps': 'gaps',
    'job_listings': 'ofertas',
    'discarded': 'descartadas',
}


class WireModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=lambda name: WIRE_ALIASES.get(name, name))

    def model_dump(self, **kwargs):
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(**kwargs)
