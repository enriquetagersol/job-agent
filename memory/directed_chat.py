"""Maintain the persistent deduplicated company-interest list. Build temporary company-directed search contexts without changing global profile preferences."""

import copy

from profiles.user_profile import normalize_identity, migrate_profile


def add_company(profile, company):
    company = ' '.join(company.split()).strip()
    if not company or len(company) > 120:
        raise ValueError('Indica un nombre de empresa válido.')
    updated = migrate_profile(profile)
    existing = updated['companies_of_interest']
    if normalize_identity(company) in {normalize_identity(name) for name in existing}:
        return updated, False
    existing.append(company)
    return updated, True


def remove_company(profile, company):
    updated = migrate_profile(profile)
    updated['companies_of_interest'] = [name for name in updated['companies_of_interest']
        if normalize_identity(name) != normalize_identity(company)]
    return updated


def directed_context(context, company):
    """Temporary scope, separate from stored preferences and ordinary searches."""
    updated = copy.deepcopy(context)
    if company:
        updated['directed_search'] = {'company': company}
        updated['perfil']['preferencias']['search_company'] = company
    return updated
