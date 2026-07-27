# -*- coding: utf-8 -*-
import secrets

from odoo import _, api, fields, models

PARAM_PREFIX = 'webflow_crm_integration'
DEFAULT_API_VERSION = '2.0.0'


class WebflowConnectionWizard(models.TransientModel):
    _name = 'webflow.connection.wizard'
    _description = 'Webflow Connection Setup Wizard'

    api_token = fields.Char(string='Webflow API Token')
    site_id = fields.Char(string='Site ID')
    webhook_secret = fields.Char(string='Webhook Secret')
    webhook_url = fields.Char(string='Webhook URL', readonly=True)
    api_version = fields.Char(string='API Version', default=DEFAULT_API_VERSION)
    connection_status = fields.Char(string='Status', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        params = self.env['ir.config_parameter'].sudo()
        base_url = params.get_param('web.base.url')
        res['webhook_url'] = f'{base_url}/webflow/webhook'
        res['api_token'] = params.get_param(f'{PARAM_PREFIX}.api_token') or ''
        res['site_id'] = params.get_param(f'{PARAM_PREFIX}.site_id') or ''
        secret = params.get_param(f'{PARAM_PREFIX}.webhook_secret')
        if not secret:
            secret = secrets.token_urlsafe(32)
            params.set_param(f'{PARAM_PREFIX}.webhook_secret', secret)
        res['webhook_secret'] = secret
        res['api_version'] = params.get_param(f'{PARAM_PREFIX}.api_version') or DEFAULT_API_VERSION
        return res

    def action_save_credentials(self):
        """Persist the credentials entered in the wizard."""
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(f'{PARAM_PREFIX}.api_token', self.api_token or '')
        params.set_param(f'{PARAM_PREFIX}.site_id', self.site_id or '')
        params.set_param(f'{PARAM_PREFIX}.webhook_secret', self.webhook_secret or '')
        params.set_param(f'{PARAM_PREFIX}.api_version',
                         self.api_version or DEFAULT_API_VERSION)
        params.set_param(f'{PARAM_PREFIX}.enabled', 'True')
        return self._reopen()

    def action_test_connection(self):
        """Validate the entered credentials against the Webflow API."""
        self.ensure_one()
        self.action_save_credentials()
        status = self.env['webflow.lead.service'].test_webflow_api(
            self.api_token, self.site_id,
            self.api_version or DEFAULT_API_VERSION)
        self.connection_status = (
            ('✅ ' if status['success'] else '❌ ') + status['message'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Webflow Connection'),
                'message': status['message'],
                'type': 'success' if status['success'] else 'danger',
                'sticky': not status['success'],
                'next': self._reopen(),
            },
        }

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'webflow.connection.wizard',
            'res_id': self.id,
            'views': [(False, 'form')],
            'view_mode': 'form',
            'target': 'new',
        }
