# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    webflow_form_name = fields.Char(
        string='Webflow Form',
        help='Name of the Webflow form that generated this lead.',
        readonly=True,
        copy=False,
    )
    webflow_source_url = fields.Char(
        string='Source Page URL',
        help='URL of the Webflow page where the form was submitted.',
        readonly=True,
        copy=False,
    )
    is_from_webflow = fields.Boolean(
        string='From Webflow',
        compute='_compute_is_from_webflow',
        store=True,
    )

    @api.depends('webflow_form_name')
    def _compute_is_from_webflow(self):
        for lead in self:
            lead.is_from_webflow = bool(lead.webflow_form_name)
