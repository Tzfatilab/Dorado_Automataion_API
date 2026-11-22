"""Named local reference resources, independent of biological organism presets."""
from copy import deepcopy
import re

BUILTIN_REFERENCES = {'mouse': 'Mouse', 'human': 'Human', 'zebrafish': 'Zebrafish'}


def new_reference_key(name, existing):
    stem = 'reference_' + (re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_') or 'custom')
    key, number = stem, 2
    while key in existing:
        key = stem + '_' + str(number)
        number += 1
    return key


def reference_library(paths):
    """Read the flat catalog and migrate previously grouped reference choices."""
    references = paths.get('references', {})
    names = paths.get('reference_names', {})
    if not isinstance(references, dict) or not isinstance(names, dict):
        raise ValueError('References must contain names and local file paths.')
    catalog = {}
    for key, path in references.items():
        name = names.get(key, BUILTIN_REFERENCES.get(key, key))
        if (not isinstance(key, str) or not key or not isinstance(name, str) or not name.strip()
                or not isinstance(path, str) or not path.strip()):
            raise ValueError('Each reference needs a nonempty name and file path.')
        catalog[key] = dict(name=name.strip(), path=path)
    grouped = paths.get('reference_options', {})
    if not isinstance(grouped, dict):
        raise ValueError('Invalid legacy reference choices.')
    for organism, options in grouped.items():
        if not isinstance(options, dict):
            raise ValueError('Invalid legacy reference choices.')
        for name, path in options.items():
            if name == 'Default':
                continue
            if not isinstance(name, str) or not name.strip() or not isinstance(path, str) or not path.strip():
                raise ValueError('Each reference needs a name and file path.')
            if any(item['name'] == name and item['path'] == path for item in catalog.values()):
                continue
            if name.casefold() in {item['name'].casefold() for item in catalog.values()}:
                name = organism.title() + ' — ' + name
            key = new_reference_key(name, catalog)
            catalog[key] = dict(name=name, path=path)
    labels = [item['name'].casefold() for item in catalog.values()]
    if len(labels) != len(set(labels)):
        raise ValueError('Reference names must be unique.')
    return catalog


def apply_reference_library(paths, catalog):
    result = deepcopy(paths)
    result['references'] = {key: item['path'] for key, item in catalog.items()}
    result['reference_names'] = {key: item['name'] for key, item in catalog.items()}
    result.pop('reference_options', None)
    return result


def merge_app_references(paths, app_paths):
    """Share general registrations while retaining legacy builtin path overrides."""
    catalog = reference_library(paths)
    shared = reference_library(app_paths)
    for key in list(catalog):
        if key.startswith('reference_') and key not in shared:
            del catalog[key]
    for key, item in shared.items():
        if key not in BUILTIN_REFERENCES:
            catalog[key] = deepcopy(item)
    return apply_reference_library(paths, catalog)


def ensure_reference_presets(config):
    """Create independent general defaults for new references in each profile."""
    catalog = reference_library(config['paths'])
    config['paths'] = apply_reference_library(config['paths'], catalog)
    presets = config.setdefault('organism_specific', {})
    for key in catalog:
        if key not in BUILTIN_REFERENCES:
            presets.setdefault(key, {'tvr_patterns': [], 'nanotel': {'include_km': False}})
    if config.get('lab_info', {}).get('default_organism') not in catalog:
        config['lab_info']['default_organism'] = next(iter(catalog), 'mouse')
