# -*- coding: utf-8 -*-
import logging
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Prefix used for every ir.config_parameter key owned by this module.
PARAM_PREFIX = 'webflow_crm_integration'

# Default Webflow Data API version.
DEFAULT_API_VERSION = '2.0.0'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ------------------------------------------------------------------
    # General settings
    # ------------------------------------------------------------------
    webflow_enabled = fields.Boolean(
        string='Enable Webflow Integration',
        config_parameter=f'{PARAM_PREFIX}.enabled',
    )
    # Companies this integration serves. Leads are created in the first
    # selected company; the rest define the scope/visibility of the setup.
    # Stored manually (config_parameter does not support Many2many).
    webflow_company_ids = fields.Many2many(
        'res.company',
        string='Companies',
    )
    webflow_team_id = fields.Many2one(
        'crm.team',
        string='Default Sales Team',
        config_parameter=f'{PARAM_PREFIX}.team_id',
    )
    webflow_user_id = fields.Many2one(
        'res.users',
        string='Default Salesperson',
        config_parameter=f'{PARAM_PREFIX}.user_id',
    )
    webflow_stage_id = fields.Many2one(
        'crm.stage',
        string='Default Lead Stage',
        config_parameter=f'{PARAM_PREFIX}.stage_id',
    )
    webflow_tag_ids = fields.Many2many(
        'crm.tag',
        string='Default Tags',
    )
    webflow_source_id = fields.Many2one(
        'utm.source',
        string='Default Lead Source',
        config_parameter=f'{PARAM_PREFIX}.source_id',
    )
    webflow_duplicate_detection = fields.Boolean(
        string='Enable Duplicate Detection',
        config_parameter=f'{PARAM_PREFIX}.duplicate_detection',
    )
    webflow_duplicate_strategy = fields.Selection(
        selection=[
            ('create', 'Create New Lead'),
            ('update', 'Update Existing Lead'),
            ('skip', 'Skip Duplicate'),
        ],
        string='Duplicate Strategy',
        default='update',
        config_parameter=f'{PARAM_PREFIX}.duplicate_strategy',
    )

    # ------------------------------------------------------------------
    # Webflow credentials
    # ------------------------------------------------------------------
    webflow_api_token = fields.Char(
        string='Webflow API Token',
        config_parameter=f'{PARAM_PREFIX}.api_token',
    )
    webflow_site_id = fields.Char(
        string='Site ID',
        config_parameter=f'{PARAM_PREFIX}.site_id',
    )
    webflow_workspace_id = fields.Char(
        string='Workspace ID',
        config_parameter=f'{PARAM_PREFIX}.workspace_id',
    )
    webflow_collection_id = fields.Char(
        string='Collection ID',
        config_parameter=f'{PARAM_PREFIX}.collection_id',
    )
    webflow_form_id = fields.Char(
        string='Form ID',
        config_parameter=f'{PARAM_PREFIX}.form_id',
    )
    webflow_webhook_secret = fields.Char(
        string='Webhook Secret',
        config_parameter=f'{PARAM_PREFIX}.webhook_secret',
    )
    webflow_api_version = fields.Char(
        string='API Version',
        default=DEFAULT_API_VERSION,
        config_parameter=f'{PARAM_PREFIX}.api_version',
    )
    webflow_require_hmac = fields.Boolean(
        string='Require HMAC Signature',
        help='Reject webhook requests whose x-webflow-signature header does not '
             'match the HMAC-SHA256 of the payload signed with the webhook secret.',
        config_parameter=f'{PARAM_PREFIX}.require_hmac',
    )

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    webflow_notify_salesperson = fields.Boolean(
        string='Notify Salesperson',
        config_parameter=f'{PARAM_PREFIX}.notify_salesperson',
    )
    webflow_create_activity = fields.Boolean(
        string='Create Activity',
        config_parameter=f'{PARAM_PREFIX}.create_activity',
    )

    # ------------------------------------------------------------------
    # Computed / display-only fields
    # ------------------------------------------------------------------
    webflow_webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_webflow_webhook_url',
    )

    # Default tags need manual (de)serialisation because config_parameter
    # does not support Many2many fields.
    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()

        # --- Companies (Many2many, stored manually) ---
        company_ids_raw = params.get_param(f'{PARAM_PREFIX}.company_ids', '')
        company_ids = [int(x) for x in company_ids_raw.split(',') if x.strip().isdigit()]
        if not company_ids:
            # Auto-fill: honour the legacy single-company key if present,
            # otherwise pre-select every company the user has access to so a
            # multi-company admin doesn't have to add each one by hand.
            legacy = params.get_param(f'{PARAM_PREFIX}.company_id')
            if legacy and str(legacy).isdigit():
                company_ids = [int(legacy)]
            else:
                company_ids = self.env.companies.ids
        res['webflow_company_ids'] = [(6, 0, company_ids)]

        # --- Default Tags (Many2many, stored manually) ---
        tag_ids_raw = params.get_param(f'{PARAM_PREFIX}.tag_ids', '')
        tag_ids = [int(x) for x in tag_ids_raw.split(',') if x.strip().isdigit()]
        if not tag_ids:
            # Auto-fill only if an obvious "Webflow" tag already exists.
            tag = self.env['crm.tag'].search([('name', '=ilike', 'Webflow')], limit=1)
            tag_ids = tag.ids
        res['webflow_tag_ids'] = [(6, 0, tag_ids)]

        # --- Single-value defaults ---
        # Default Sales Team / Salesperson / Lead Stage / Lead Source are
        # intentionally NOT auto-filled — the admin picks them explicitly.
        return res

    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(
            f'{PARAM_PREFIX}.tag_ids',
            ','.join(str(i) for i in self.webflow_tag_ids.ids),
        )
        company_ids = self.webflow_company_ids.ids
        params.set_param(
            f'{PARAM_PREFIX}.company_ids',
            ','.join(str(i) for i in company_ids),
        )
        # Keep the legacy single-company key in sync (first company) for any
        # code or report still reading it.
        params.set_param(
            f'{PARAM_PREFIX}.company_id',
            str(company_ids[0]) if company_ids else '',
        )

    @api.depends('webflow_enabled')
    def _compute_webflow_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.webflow_webhook_url = f'{base_url}/webflow/webhook'

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_webflow_regenerate_secret(self):
        """Generate a fresh cryptographically-strong webhook secret."""
        self.ensure_one()
        new_secret = secrets.token_urlsafe(32)
        self.env['ir.config_parameter'].sudo().set_param(
            f'{PARAM_PREFIX}.webhook_secret', new_secret)
        self.webflow_webhook_secret = new_secret
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_webflow_test_api(self):
        """Call the Webflow API to validate the API token and Site ID."""
        self.ensure_one()
        status = self.env['webflow.lead.service'].test_webflow_api(
            self.webflow_api_token,
            self.webflow_site_id,
            self.webflow_api_version or DEFAULT_API_VERSION,
        )
        return self._webflow_notify(status)

    def action_webflow_send_test_webhook(self):
        """Simulate an inbound webhook to confirm lead creation works."""
        self.ensure_one()
        try:
            lead = self.env['webflow.lead.service'].process_submission(
                payload={
                    'triggerType': 'form_submission',
                    'payload': {
                        'name': 'Webflow Test Form',
                        'data': {
                            'Name': 'Webflow Test Lead',
                            'Email': 'test@example.com',
                            'Message': 'This is a test webhook from Odoo settings.',
                        },
                    },
                },
                source='test',
            )
            msg = _('Test webhook processed. Lead created: %s', lead.display_name) \
                if lead else _('Test webhook processed but no lead was created.')
            return self._webflow_notify({'success': bool(lead), 'message': msg})
        except Exception as exc:  # noqa: BLE001 - surface any failure to the admin
            _logger.exception('Webflow test webhook failed')
            return self._webflow_notify({'success': False, 'message': str(exc)})

    def _webflow_notify(self, status):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Webflow') + (' ✅' if status.get('success') else ' ❌'),
                'message': status.get('message', ''),
                'type': 'success' if status.get('success') else 'danger',
                'sticky': not status.get('success'),
            },
        }

    def action_webflow_open_docs(self):
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://developers.webflow.com/data/reference/webhooks',
            'target': 'new',
        }

    def _webflow_webhook_endpoint(self):
        """Build the public webhook URL, with the secret in the query string."""
        params = self.env['ir.config_parameter'].sudo()
        base_url = params.get_param('web.base.url')
        url = f'{base_url}/webflow/webhook'
        secret = params.get_param(f'{PARAM_PREFIX}.webhook_secret')
        if secret:
            url = f'{url}?secret={secret}'
        return url

    def action_webflow_register_webhook(self):
        """Create the Form Submission webhook in Webflow automatically."""
        self.ensure_one()
        # Persist current settings first so the registered secret matches the
        # one the controller validates against.
        self.set_values()
        params = self.env['ir.config_parameter'].sudo()
        status = self.env['webflow.lead.service'].register_form_webhook(
            params.get_param(f'{PARAM_PREFIX}.api_token'),
            params.get_param(f'{PARAM_PREFIX}.site_id'),
            params.get_param(f'{PARAM_PREFIX}.api_version') or DEFAULT_API_VERSION,
            self._webflow_webhook_endpoint(),
        )
        return self._webflow_notify(status)

    def action_webflow_list_webhooks(self):
        """List the webhooks currently registered on the Webflow site."""
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        status = self.env['webflow.lead.service'].list_webhooks(
            self.webflow_api_token or params.get_param(f'{PARAM_PREFIX}.api_token'),
            self.webflow_site_id or params.get_param(f'{PARAM_PREFIX}.site_id'),
            self.webflow_api_version or DEFAULT_API_VERSION,
        )
        return self._webflow_notify(status)
