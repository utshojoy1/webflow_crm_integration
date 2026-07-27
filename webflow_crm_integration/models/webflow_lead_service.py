# -*- coding: utf-8 -*-
import json
import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_PREFIX = 'webflow_crm_integration'

# Sentinel returned by _coerce_to_field when a value cannot be safely written.
_SKIP = object()


class WebflowLeadService(models.AbstractModel):
    """Stateless service that turns Webflow submissions into CRM leads."""

    _name = 'webflow.lead.service'
    _description = 'Webflow Lead Creation Service'

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    @api.model
    def _get_param(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            f'{PARAM_PREFIX}.{key}', default)

    @api.model
    def _get_settings(self):
        get = self._get_param
        # Allowed companies (first one is where new leads are created).
        company_ids = [int(x) for x in (get('company_ids') or '').split(',')
                       if x.strip().isdigit()]
        if not company_ids:
            legacy = int(get('company_id') or 0)
            company_ids = [legacy] if legacy else []
        company_id = company_ids[0] if company_ids else self.env.company.id
        return {
            'enabled': get('enabled') in ('True', 'true', '1', True),
            'company_id': company_id,
            'company_ids': company_ids or [company_id],
            'team_id': int(get('team_id') or 0) or False,
            'user_id': int(get('user_id') or 0) or False,
            'stage_id': int(get('stage_id') or 0) or False,
            'source_id': int(get('source_id') or 0) or False,
            'tag_ids': [int(x) for x in (get('tag_ids') or '').split(',') if x.strip().isdigit()],
            'duplicate_detection': get('duplicate_detection') in ('True', 'true', '1', True),
            'duplicate_strategy': get('duplicate_strategy') or 'update',
            'notify_salesperson': get('notify_salesperson') in ('True', 'true', '1', True),
            'create_activity': get('create_activity') in ('True', 'true', '1', True),
        }

    # ------------------------------------------------------------------
    # Payload parsing
    # ------------------------------------------------------------------
    @api.model
    def _extract_form_data(self, payload):
        """Normalise Webflow v2 and legacy payloads into (form_name, data dict).

        Webflow v2 form_submission webhook shape::

            {"triggerType": "form_submission",
             "payload": {"name": "Contact Form", "data": {...}}}

        Legacy/direct shapes are also tolerated.
        """
        if not isinstance(payload, dict):
            return '', {}
        inner = payload.get('payload') or payload
        form_name = inner.get('name') or inner.get('formName') or payload.get('name') or ''
        data = inner.get('data') or inner.get('fields') or payload.get('data') or {}
        if not isinstance(data, dict):
            data = {}
        # Expose submission metadata (page URL) to the mapping engine so a
        # "Page URL" mapping can capture it — Webflow sends it outside `data`.
        page_url = inner.get('pageUrl') or inner.get('pageURL') or inner.get('publishedPath')
        if page_url and 'Page URL' not in data:
            data = dict(data, **{'Page URL': page_url})
        return form_name, data

    # ------------------------------------------------------------------
    # Field mapping engine
    # ------------------------------------------------------------------
    @api.model
    def _build_lead_vals(self, form_name, data, settings):
        """Convert incoming form data into crm.lead values using the mappings."""
        company_id = settings['company_id']
        mappings = self.env['webflow.field.mapping'].get_active_mappings(company_id)

        # Case-insensitive lookup of the incoming data.
        lower_data = {str(k).strip().lower(): v for k, v in data.items()}

        vals = {}
        tag_ids = list(settings['tag_ids'])

        for mapping in mappings:
            key = mapping.webflow_field.strip().lower()
            if key not in lower_data:
                continue
            raw = lower_data[key]
            if raw in (None, ''):
                continue
            self._apply_mapping(mapping, raw, vals, tag_ids, company_id)

        # Sensible default opportunity name.
        if not vals.get('name'):
            vals['name'] = (
                data.get('Subject')
                or form_name
                or _('Webflow Lead')
            )

        # Defaults from settings (only when not already set).
        vals.setdefault('type', 'lead')
        if settings['team_id']:
            vals.setdefault('team_id', settings['team_id'])
        if settings['user_id']:
            vals.setdefault('user_id', settings['user_id'])
        if settings['stage_id']:
            vals.setdefault('stage_id', settings['stage_id'])
        if settings['source_id']:
            vals.setdefault('source_id', settings['source_id'])
        vals['company_id'] = company_id

        # Provenance fields.
        vals['webflow_form_name'] = form_name
        if tag_ids:
            vals['tag_ids'] = [(6, 0, list(set(tag_ids)))]
        return vals

    @api.model
    def _apply_mapping(self, mapping, raw, vals, tag_ids, company_id):
        """Write one converted value into ``vals`` according to mapping type.

        Every write is validated against the actual crm.lead field type, so a
        misconfigured mapping (e.g. text into an integer/relational column) is
        skipped with a warning instead of crashing lead creation.
        """
        mtype = mapping.mapping_type
        target = mapping.odoo_field
        value = str(raw).strip() if not isinstance(raw, (list, dict)) else raw

        # Tags are collected separately and never written to ``target``.
        if mtype == 'tag':
            tag = self._get_or_create_tag(value)
            if tag:
                tag_ids.append(tag.id)
            return

        # The target must be a real field on crm.lead.
        field = self.env['crm.lead']._fields.get(target)
        if field is None:
            _logger.warning(
                'Webflow mapping "%s" targets unknown crm.lead field "%s"; skipping.',
                mapping.webflow_field, target)
            return

        # Resolve the value according to the declared mapping type.
        if mtype == 'float':
            resolved = self._to_float(value)
        elif mtype == 'country':
            rec = self._find_country(value)
            resolved = rec.id if rec else None
        elif mtype in ('utm_source', 'utm_medium', 'utm_campaign'):
            rec = self._get_or_create_utm(mtype, value)
            resolved = rec.id if rec else None
        else:
            resolved = value  # char / email / phone

        if resolved in (None, ''):
            return

        # Final type guard against the real column type.
        coerced = self._coerce_to_field(field, resolved)
        if coerced is _SKIP:
            _logger.warning(
                'Webflow value %r is not compatible with crm.lead.%s (%s); skipping.',
                resolved, target, field.type)
            return
        vals[target] = coerced

    @api.model
    def _coerce_to_field(self, field, value):
        """Return ``value`` coerced to ``field``'s type, or ``_SKIP`` if impossible."""
        ftype = field.type
        if ftype in ('char', 'text', 'html', 'selection'):
            return str(value)
        if ftype == 'integer':
            try:
                return int(float(str(value)))
            except (ValueError, TypeError):
                return _SKIP
        if ftype in ('float', 'monetary'):
            try:
                return float(value)
            except (ValueError, TypeError):
                return _SKIP
        if ftype == 'boolean':
            return str(value).strip().lower() in ('1', 'true', 'yes', 'on', 'checked')
        if ftype == 'many2one':
            if isinstance(value, int):
                return value
            try:
                return int(value)
            except (ValueError, TypeError):
                comodel = field.comodel_name
                rec = self.env[comodel].search(
                    [('display_name', '=ilike', str(value))], limit=1
                ) if comodel else None
                return rec.id if rec else _SKIP
        # dates, binary, x2many and anything else: don't risk a bad write.
        return _SKIP

    @staticmethod
    def _to_float(value):
        cleaned = ''.join(c for c in str(value) if c.isdigit() or c in '.,-')
        cleaned = cleaned.replace(',', '')
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0

    def _get_or_create_tag(self, name):
        Tag = self.env['crm.tag']
        tag = Tag.search([('name', '=ilike', name)], limit=1)
        return tag or Tag.create({'name': name})

    def _find_country(self, value):
        Country = self.env['res.country']
        return (
            Country.search([('name', '=ilike', value)], limit=1)
            or Country.search([('code', '=ilike', value)], limit=1)
        )

    def _get_or_create_utm(self, mtype, name):
        model_by_type = {
            'utm_source': 'utm.source',
            'utm_medium': 'utm.medium',
            'utm_campaign': 'utm.campaign',
        }
        Model = self.env[model_by_type[mtype]]
        record = Model.search([('name', '=ilike', name)], limit=1)
        return record or Model.create({'name': name})

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------
    @api.model
    def _find_duplicate(self, vals, company_id):
        domain = [('company_id', 'in', [company_id, False])]
        or_terms = []
        if vals.get('email_from'):
            or_terms.append(('email_from', '=ilike', vals['email_from']))
        if vals.get('phone'):
            or_terms.append(('phone', '=', vals['phone']))
        if not or_terms:
            return self.env['crm.lead']
        if len(or_terms) == 2:
            domain += ['|'] + or_terms
        else:
            domain += or_terms
        return self.env['crm.lead'].search(domain, limit=1, order='create_date desc')

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @api.model
    def process_submission(self, payload, source='webhook', log=None):
        """Create or update a CRM lead from a Webflow submission payload.

        :param payload: the parsed JSON body from Webflow.
        :param source: 'webhook' | 'retry' | 'test' (informational).
        :param log: optional webflow.integration.log record to update in place.
        :returns: the crm.lead record, or empty recordset if skipped.
        """
        start = time.time()
        settings = self._get_settings()
        form_name, data = self._extract_form_data(payload)

        vals = self._build_lead_vals(form_name, data, settings)
        Lead = self.env['crm.lead'].with_company(settings['company_id'])

        lead = self.env['crm.lead']
        action = 'created'

        if settings['duplicate_detection']:
            existing = self._find_duplicate(vals, settings['company_id'])
            if existing:
                strategy = settings['duplicate_strategy']
                if strategy == 'skip':
                    self._finalize_log(log, 'skipped', False, start,
                                       form_name, payload)
                    return self.env['crm.lead']
                if strategy == 'update':
                    update_vals = {k: v for k, v in vals.items()
                                   if k not in ('company_id', 'type')}
                    existing.write(update_vals)
                    lead = existing
                    action = 'updated'

        if not lead:
            lead = Lead.create(vals)

        self._post_process(lead, settings, action)
        self._finalize_log(log, 'success', lead, start, form_name, payload)
        return lead

    def _post_process(self, lead, settings, action):
        """Notifications and activities after lead creation/update."""
        if action == 'created':
            lead.message_post(
                body=_('Lead created from a Webflow form submission.'),
            )
        if settings['notify_salesperson'] and lead.user_id:
            lead.message_subscribe(partner_ids=lead.user_id.partner_id.ids)
            lead.message_post(
                body=_('New Webflow lead assigned to you: %s', lead.display_name),
                partner_ids=lead.user_id.partner_id.ids,
            )
        if settings['create_activity'] and lead.user_id:
            lead.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Follow up on Webflow lead'),
                user_id=lead.user_id.id,
            )

    def _finalize_log(self, log, state, lead, start, form_name, payload):
        if not log:
            return
        log.write({
            'state': state,
            'lead_id': lead.id if lead else False,
            'form_name': form_name,
            'processing_time': time.time() - start,
            'http_status': 200,
            'error_message': False,
        })

    # ------------------------------------------------------------------
    # Test connection utilities
    # ------------------------------------------------------------------
    @api.model
    def test_webflow_api(self, api_token, site_id, api_version):
        """Validate credentials against the Webflow Data API."""
        if not api_token:
            return {'success': False, 'message': _('Missing Webflow API token.')}
        if not site_id:
            return {'success': False, 'message': _('Missing Webflow Site ID.')}
        try:
            import requests
        except ImportError:
            return {'success': False,
                    'message': _('The Python "requests" library is not available.')}

        url = f'https://api.webflow.com/v2/sites/{site_id}'
        headers = {
            'Authorization': f'Bearer {api_token}',
            'accept': 'application/json',
            'accept-version': api_version,
        }
        try:
            resp = requests.get(url, headers=headers, timeout=15)
        except Exception as exc:  # noqa: BLE001 - network errors are expected here
            return {'success': False,
                    'message': _('Could not reach Webflow: %s', exc)}

        if resp.status_code == 200:
            try:
                name = resp.json().get('displayName') or site_id
            except ValueError:
                name = site_id
            return {'success': True,
                    'message': _('Connected to Webflow site "%s".', name)}
        if resp.status_code in (401, 403):
            return {'success': False, 'message': _('Invalid API Key or insufficient scope.')}
        if resp.status_code == 404:
            return {'success': False, 'message': _('Invalid Site ID.')}
        return {'success': False,
                'message': _('Webflow returned HTTP %s.', resp.status_code)}

    # ------------------------------------------------------------------
    # Webhook management (Webflow Data API v2)
    # ------------------------------------------------------------------
    @api.model
    def _webflow_requests(self):
        try:
            import requests
            return requests
        except ImportError:
            return None

    @api.model
    def _webflow_api_headers(self, api_token, api_version, with_content=False):
        headers = {
            'Authorization': f'Bearer {api_token}',
            'accept': 'application/json',
            'accept-version': api_version,
        }
        if with_content:
            headers['content-type'] = 'application/json'
        return headers

    @staticmethod
    def _webflow_api_error(resp):
        try:
            body = resp.json()
            detail = body.get('message') or body.get('err') or str(body)
        except (ValueError, AttributeError):
            detail = (resp.text or '')[:300]
        return f'Webflow API HTTP {resp.status_code}: {detail}'

    @api.model
    def list_webhooks(self, api_token, site_id, api_version):
        """Return a human-readable summary of the site's registered webhooks."""
        requests = self._webflow_requests()
        if requests is None:
            return {'success': False,
                    'message': _('The Python "requests" library is not available.')}
        if not api_token or not site_id:
            return {'success': False,
                    'message': _('Webflow API token and Site ID are required.')}
        url = f'https://api.webflow.com/v2/sites/{site_id}/webhooks'
        try:
            resp = requests.get(
                url, headers=self._webflow_api_headers(api_token, api_version),
                timeout=20)
        except Exception as exc:  # noqa: BLE001
            return {'success': False, 'message': _('Could not reach Webflow: %s', exc)}
        if resp.status_code != 200:
            return {'success': False, 'message': self._webflow_api_error(resp)}
        hooks = resp.json().get('webhooks', [])
        if not hooks:
            return {'success': True,
                    'message': _('No webhooks are registered on this site yet.')}
        lines = [f"• {h.get('triggerType')} → {h.get('url')}" for h in hooks]
        return {'success': True,
                'message': _('%(n)s webhook(s) registered:\n%(list)s',
                             n=len(hooks), list='\n'.join(lines))}

    @api.model
    def register_form_webhook(self, api_token, site_id, api_version, webhook_url):
        """Create a form_submission webhook, replacing any stale ones we own.

        Idempotent: existing form_submission webhooks that point at this
        Odoo endpoint are deleted first so the secret stays in sync.
        """
        requests = self._webflow_requests()
        if requests is None:
            return {'success': False,
                    'message': _('The Python "requests" library is not available.')}
        if not api_token or not site_id:
            return {'success': False,
                    'message': _('Webflow API token and Site ID are required.')}

        base = f'https://api.webflow.com/v2/sites/{site_id}/webhooks'
        headers = self._webflow_api_headers(api_token, api_version)

        # 1. List existing webhooks (also validates the token/site).
        try:
            existing = requests.get(base, headers=headers, timeout=20)
        except Exception as exc:  # noqa: BLE001
            return {'success': False, 'message': _('Could not reach Webflow: %s', exc)}
        if existing.status_code != 200:
            return {'success': False, 'message': self._webflow_api_error(existing)}

        # 2. Remove stale form_submission webhooks that target this Odoo endpoint.
        removed = 0
        for hook in existing.json().get('webhooks', []):
            hook_url = hook.get('url') or ''
            if hook.get('triggerType') == 'form_submission' and '/webflow/webhook' in hook_url:
                try:
                    requests.delete(f"{base}/{hook.get('id')}", headers=headers, timeout=20)
                    removed += 1
                except Exception:  # noqa: BLE001 - best effort cleanup
                    pass

        # 3. Create the fresh webhook.
        payload = {'triggerType': 'form_submission', 'url': webhook_url}
        try:
            resp = requests.post(
                base,
                headers=self._webflow_api_headers(api_token, api_version, with_content=True),
                json=payload, timeout=20)
        except Exception as exc:  # noqa: BLE001
            return {'success': False, 'message': _('Could not reach Webflow: %s', exc)}
        if resp.status_code in (200, 201):
            suffix = _(' (%s stale webhook(s) replaced)', removed) if removed else ''
            return {'success': True,
                    'message': _('Form Submission webhook registered in Webflow.') + suffix}
        return {'success': False, 'message': self._webflow_api_error(resp)}
