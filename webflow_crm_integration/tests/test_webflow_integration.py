# -*- coding: utf-8 -*-
import json

from odoo.tests import TransactionCase, tagged

PARAM_PREFIX = 'webflow_crm_integration'


@tagged('post_install', '-at_install')
class TestWebflowIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.params = cls.env['ir.config_parameter'].sudo()
        cls.params.set_param(f'{PARAM_PREFIX}.enabled', 'True')
        cls.params.set_param(f'{PARAM_PREFIX}.webhook_secret', 'test-secret')
        cls.params.set_param(f'{PARAM_PREFIX}.duplicate_detection', 'True')
        cls.params.set_param(f'{PARAM_PREFIX}.duplicate_strategy', 'update')
        cls.service = cls.env['webflow.lead.service']

    def _payload(self, data, form_name='Contact Form'):
        return {
            'triggerType': 'form_submission',
            'payload': {'name': form_name, 'data': data},
        }

    def test_01_create_lead_basic(self):
        payload = self._payload({
            'Contact Name': 'Jane Doe',
            'Contact Email': 'jane@example.com',
            'Contact Number': '+1 555 0100',
            'Contact Message': 'Interested in your services.',
            'Subject': 'Website inquiry',
        })
        lead = self.service.process_submission(payload)
        self.assertTrue(lead, 'A lead should be created.')
        self.assertEqual(lead.contact_name, 'Jane Doe')
        self.assertEqual(lead.email_from, 'jane@example.com')
        self.assertEqual(lead.name, 'Website inquiry')
        self.assertEqual(lead.description, 'Interested in your services.')
        self.assertEqual(lead.webflow_form_name, 'Contact Form')
        self.assertTrue(lead.is_from_webflow)

    def test_02_budget_and_tags(self):
        payload = self._payload({
            'Contact Name': 'Budget Guy',
            'Contact Email': 'budget@example.com',
            'Budget': '$12,500',
            'service type': 'Consulting',
        })
        lead = self.service.process_submission(payload)
        self.assertEqual(lead.expected_revenue, 12500.0)
        self.assertIn('Consulting', lead.tag_ids.mapped('name'))

    def test_03_utm_mapping(self):
        payload = self._payload({
            'Contact Name': 'UTM User',
            'Contact Email': 'utm@example.com',
            'UTM Source': 'newsletter',
            'UTM Medium': 'email',
            'UTM Campaign': 'summer-sale',
        })
        lead = self.service.process_submission(payload)
        self.assertEqual(lead.source_id.name, 'newsletter')
        self.assertEqual(lead.medium_id.name, 'email')
        self.assertEqual(lead.campaign_id.name, 'summer-sale')

    def test_04_duplicate_update(self):
        payload = self._payload({
            'Contact Name': 'Dup User',
            'Contact Email': 'dup@example.com',
            'Contact Message': 'First message',
        })
        lead1 = self.service.process_submission(payload)
        payload2 = self._payload({
            'Contact Name': 'Dup User',
            'Contact Email': 'dup@example.com',
            'Contact Message': 'Second message',
        })
        lead2 = self.service.process_submission(payload2)
        self.assertEqual(lead1.id, lead2.id, 'Duplicate should update the same lead.')
        self.assertEqual(lead2.description, 'Second message')

    def test_05_duplicate_skip(self):
        self.params.set_param(f'{PARAM_PREFIX}.duplicate_strategy', 'skip')
        self.service.process_submission(self._payload({
            'Contact Name': 'Skip User', 'Contact Email': 'skip@example.com'}))
        result = self.service.process_submission(self._payload({
            'Contact Name': 'Skip User', 'Contact Email': 'skip@example.com'}))
        self.assertFalse(result, 'Second submission should be skipped.')
        self.params.set_param(f'{PARAM_PREFIX}.duplicate_strategy', 'update')

    def test_06_country_mapping(self):
        payload = self._payload({
            'Contact Name': 'Country User',
            'Contact Email': 'country@example.com',
            'Country': 'Belgium',
        })
        lead = self.service.process_submission(payload)
        self.assertEqual(lead.country_id.name, 'Belgium')

    def test_07_case_insensitive_keys(self):
        payload = self._payload({
            'contact name': 'Lower Case',
            'CONTACT EMAIL': 'lower@example.com',
        })
        lead = self.service.process_submission(payload)
        self.assertEqual(lead.contact_name, 'Lower Case')
        self.assertEqual(lead.email_from, 'lower@example.com')

    def test_08_log_and_retry(self):
        log = self.env['webflow.integration.log'].create({
            'payload': json.dumps(self._payload({
                'Contact Name': 'Retry User', 'Contact Email': 'retry@example.com'})),
            'state': 'failed',
        })
        log.action_retry()
        self.assertEqual(log.state, 'success')
        self.assertTrue(log.lead_id)

    def test_09_dashboard(self):
        self.service.process_submission(self._payload({
            'Contact Name': 'Dash User', 'Contact Email': 'dash@example.com'}))
        dashboard = self.env['webflow.dashboard'].create({})
        self.assertGreaterEqual(dashboard.total_webhooks, 0)
        self.assertIn(dashboard.health_status,
                      ('ok', 'warning', 'error', 'idle'))
