# -*- coding: utf-8 -*-
from odoo import api, fields, models


class WebflowFieldMapping(models.Model):
    _name = 'webflow.field.mapping'
    _description = 'Webflow to CRM Field Mapping'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    webflow_field = fields.Char(
        string='Webflow Field',
        required=True,
        help='The key sent by Webflow in the submission payload (case-insensitive).',
    )
    odoo_field = fields.Char(
        string='Odoo CRM Field',
        required=True,
        help='Technical name of the target field on crm.lead (e.g. email_from).',
    )
    mapping_type = fields.Selection(
        selection=[
            ('char', 'Text'),
            ('email', 'Email'),
            ('phone', 'Phone'),
            ('float', 'Number'),
            ('tag', 'CRM Tag (many2many)'),
            ('country', 'Country'),
            ('utm_source', 'UTM Source'),
            ('utm_medium', 'UTM Medium'),
            ('utm_campaign', 'UTM Campaign'),
        ],
        string='Type',
        default='char',
        required=True,
        help='Controls how the incoming value is converted before being written '
             'to the Odoo field.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help='Leave empty to apply this mapping to every company.',
    )

    _sql_constraints = [
        (
            'webflow_field_company_uniq',
            'unique(webflow_field, company_id)',
            'A mapping already exists for this Webflow field in this company.',
        ),
    ]

    @api.model
    def get_active_mappings(self, company_id=None):
        """Return mappings applicable to the given company plus global ones."""
        if company_id:
            domain = ['|', ('company_id', '=', False), ('company_id', '=', company_id)]
        else:
            domain = [('company_id', '=', False)]
        return self.search(domain)
