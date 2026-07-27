# -*- coding: utf-8 -*-
from datetime import datetime, time

from odoo import api, fields, models


class WebflowDashboard(models.TransientModel):
    _name = 'webflow.dashboard'
    _description = 'Webflow Integration Dashboard'

    total_webhooks = fields.Integer(string='Total Webhooks', readonly=True)
    successful_imports = fields.Integer(string='Successful Imports', readonly=True)
    failed_imports = fields.Integer(string='Failed Imports', readonly=True)
    skipped_imports = fields.Integer(string='Skipped', readonly=True)
    todays_leads = fields.Integer(string="Today's Leads", readonly=True)
    last_sync = fields.Datetime(string='Last Sync', readonly=True)
    health_status = fields.Selection(
        selection=[
            ('ok', 'Healthy'),
            ('warning', 'Degraded'),
            ('error', 'Unhealthy'),
            ('idle', 'No Activity'),
        ],
        string='Webhook Health',
        readonly=True,
    )
    success_rate = fields.Float(string='Success Rate (%)', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        Log = self.env['webflow.integration.log']

        total = Log.search_count([])
        success = Log.search_count([('state', '=', 'success')])
        failed = Log.search_count([('state', '=', 'failed')])
        skipped = Log.search_count([('state', '=', 'skipped')])

        today_start = datetime.combine(fields.Date.context_today(self), time.min)
        todays_leads = self.env['crm.lead'].search_count([
            ('is_from_webflow', '=', True),
            ('create_date', '>=', today_start),
        ])

        last_log = Log.search([], order='create_date desc', limit=1)

        rate = (success / total * 100.0) if total else 0.0
        if total == 0:
            health = 'idle'
        elif rate >= 90.0:
            health = 'ok'
        elif rate >= 60.0:
            health = 'warning'
        else:
            health = 'error'

        res.update({
            'total_webhooks': total,
            'successful_imports': success,
            'failed_imports': failed,
            'skipped_imports': skipped,
            'todays_leads': todays_leads,
            'last_sync': last_log.create_date if last_log else False,
            'success_rate': rate,
            'health_status': health,
        })
        return res

    def action_view_logs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Webflow Logs',
            'res_model': 'webflow.integration.log',
            'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'list,form',
        }

    def action_view_failed(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Failed Webhooks',
            'res_model': 'webflow.integration.log',
            'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'list,form',
            'domain': [('state', '=', 'failed')],
        }

    def action_refresh(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Webflow Dashboard',
            'res_model': 'webflow.dashboard',
            'views': [(False, 'form')],
            'view_mode': 'form',
            'target': 'current',
        }
