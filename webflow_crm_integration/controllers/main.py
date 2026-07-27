# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import logging
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PARAM_PREFIX = 'webflow_crm_integration'

# Simple in-memory rate limiter: {ip: [timestamps]}. Best-effort per worker.
_RATE_BUCKET = {}
_RATE_LIMIT = 60          # max requests
_RATE_WINDOW = 60         # per seconds


class WebflowWebhookController(http.Controller):

    @http.route(
        '/webflow/webhook',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def webflow_webhook(self, **kwargs):
        """Public endpoint that receives Webflow form submissions."""
        start = time.time()
        params = request.env['ir.config_parameter'].sudo()

        # 0. Integration must be enabled.
        if params.get_param(f'{PARAM_PREFIX}.enabled') not in ('True', 'true', '1'):
            return self._json_response(403, {'error': 'Integration disabled'})

        # 1. Rate limiting (best effort).
        ip = request.httprequest.remote_addr or 'unknown'
        if self._is_rate_limited(ip):
            return self._json_response(429, {'error': 'Too many requests'})

        # 2. Read raw body (needed for HMAC verification).
        raw_body = request.httprequest.get_data() or b''

        # 3. Authenticate the request.
        auth_error = self._authenticate(raw_body, kwargs, params)
        if auth_error:
            self._create_log(raw_body, ip, 'failed', 401, auth_error)
            return self._json_response(401, {'error': auth_error})

        # 4. Parse JSON payload.
        try:
            payload = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        except (ValueError, UnicodeDecodeError):
            self._create_log(raw_body, ip, 'failed', 400, 'Invalid JSON payload')
            return self._json_response(400, {'error': 'Invalid JSON'})

        # 5. Create the log entry up-front so failures are always recorded.
        log = self._create_log(raw_body, ip, 'failed', 200, None)

        # 6. Process the submission.
        try:
            lead = request.env['webflow.lead.service'].sudo().process_submission(
                payload=payload,
                source='webhook',
                log=log,
            )
            return self._json_response(200, {
                'status': 'ok',
                'lead_id': lead.id if lead else None,
                'processing_time': round(time.time() - start, 4),
            })
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the caller
            _logger.exception('Webflow webhook processing failed')
            if log:
                log.sudo().write({
                    'state': 'failed',
                    'error_message': str(exc),
                    'http_status': 500,
                })
            return self._json_response(500, {'error': 'Processing error'})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _authenticate(self, raw_body, kwargs, params):
        """Return an error string when the request is not authenticated."""
        secret = params.get_param(f'{PARAM_PREFIX}.webhook_secret')
        if not secret:
            return 'Webhook secret not configured'

        require_hmac = params.get_param(f'{PARAM_PREFIX}.require_hmac') in (
            'True', 'true', '1')
        headers = request.httprequest.headers

        if require_hmac:
            signature = headers.get('x-webflow-signature')
            timestamp = headers.get('x-webflow-timestamp')
            if not signature or not timestamp:
                return 'Missing HMAC signature headers'
            content = f'{timestamp}:{raw_body.decode("utf-8", "ignore")}'
            expected = hmac.new(
                secret.encode('utf-8'),
                content.encode('utf-8'),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                return 'Invalid HMAC signature'
            return None

        # Shared-secret mode: accept header or query param.
        provided = (
            headers.get('X-Webhook-Secret')
            or kwargs.get('secret')
        )
        if not provided or not hmac.compare_digest(str(provided), str(secret)):
            return 'Invalid webhook secret'
        return None

    def _is_rate_limited(self, ip):
        now = time.time()
        bucket = _RATE_BUCKET.setdefault(ip, [])
        # Drop timestamps outside the window.
        bucket[:] = [t for t in bucket if now - t < _RATE_WINDOW]
        if len(bucket) >= _RATE_LIMIT:
            return True
        bucket.append(now)
        return False

    def _create_log(self, raw_body, ip, state, status, error):
        try:
            payload_text = raw_body.decode('utf-8', 'ignore') if raw_body else ''
            return request.env['webflow.integration.log'].sudo().log_request({
                'payload': payload_text[:100000],
                'ip_address': ip,
                'state': state,
                'http_status': status,
                'error_message': error,
            })
        except Exception:  # noqa: BLE001 - logging must never break the response
            _logger.exception('Failed to write Webflow integration log')
            return request.env['webflow.integration.log'].sudo()

    def _json_response(self, status, body):
        return request.make_json_response(body, status=status)
