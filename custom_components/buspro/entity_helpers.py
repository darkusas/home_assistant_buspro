"""Helpers shared by the Buspro entity platforms."""


def entity_id_changing(entity):
    """True while Home Assistant removes an entity only to add it again under a new entity_id.

    Renaming an entity_id removes and re-adds the same entity object, so its device must keep
    listening to the bus. During that removal the registry entry already has the new entity_id.
    """
    entry = entity.registry_entry
    return entry is not None and entry.entity_id != entity.entity_id
