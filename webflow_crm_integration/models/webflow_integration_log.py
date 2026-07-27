# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class WebflowIntegrationLog(models.Model):
    _name = 'webflow.integration.log'
    _description = 'Webflow Webhook Integration Log'
    _order = 'create_date desc'
    _rec_name = 'webflow_event'

    webflow_event = fields.Char(string='Webflow Event', default='form_submission')
    form_name = fields.Char(string='Form Name')
    payload = fields.Text(string='Payload')
    http_status = fields.Integer(string='HTTP Status', default=200)
    lead_id = fields.Many2one('crm.lead', string='CRM Lead', ondelete='set null')
    processing_time = fields.Float(
        string='Processing Time (s)',
        digits=(12, 4),
    )
    state = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),
        ],
        string='Status',
        default='failed',
        index=True,
    )
    error_message = fields.Text(string='Error Message')
    ip_address = fields.Char(string='Source IP')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    retry_count = fields.Integer(string='Retry Count', default=0)

    @api.model
    def log_request(self, vals):
        """Create a log entry with sudo so the public controller can write it."""
        return self.sudo().create(vals)

    def action_retry(self):
        """Reprocess failed webhook requests from their stored payload."""
        service = self.env['webflow.lead.service']
        for log in self:
            if log.state == 'success':
                continue
            try:
                # Savepoint so a failed create rolls back cleanly and leaves the
                # transaction usable for the error write below.
                with self.env.cr.savepoint():
                    payload = log._parse_payload()
                    lead = service.process_submission(
                        payload=payload,
                        source='retry',
                        log=log,
                    )
                log.write({
                    'state': 'success' if lead else 'skipped',
                    'lead_id': lead.id if lead else False,
                    'error_message': False,
                    'retry_count': log.retry_count + 1,
                })
            except Exception as exc:  # noqa: BLE001 - keep other retries alive
                _logger.exception('Webflow retry failed for log %s', log.id)
                log.write({
                    'state': 'failed',
                    'error_message': str(exc),
                    'retry_count': log.retry_count + 1,
                })
        return True

    def _parse_payload(self):
        self.ensure_one()
        import json
        try:
            return json.loads(self.payload or '{}')
        except (ValueError, TypeError):
            return {}

    @api.model
    def cron_retry_failed(self):
        """Scheduled action: retry failed imports (bounded retry attempts)."""
        max_retries = 5
        failed = self.search([
            ('state', '=', 'failed'),
            ('retry_count', '<', max_retries),
        ], limit=100)
        if failed:
            _logger.info('Webflow: retrying %s failed webhook(s).', len(failed))
            failed.action_retry()
        return True
