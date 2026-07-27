# -*- coding: utf-8 -*-
"""Update default field mappings to the real Webflow form field names.

Only rewrites a mapping if it still holds the original generic value, so any
manual edits an administrator made in the UI are preserved.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# xmlid -> (old generic value, new value matching the live Webflow form)
RENAMES = {
    'map_name': ('Name', 'Contact Name'),
    'map_email': ('Email', 'Contact Email'),
    'map_phone': ('Phone', 'Contact Number'),
    'map_company': ('Company', 'Company Name'),
    'map_message': ('Message', 'Contact Message'),
    'map_service': ('Service', 'service type'),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, (old, new) in RENAMES.items():
        record = env.ref(f'webflow_crm_integration.{xmlid}', raise_if_not_found=False)
        if record and record.webflow_field == old:
            record.webflow_field = new
            _logger.info('Webflow mapping %s: %r -> %r', xmlid, old, new)
