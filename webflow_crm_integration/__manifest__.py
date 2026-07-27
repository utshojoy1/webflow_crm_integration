# -*- coding: utf-8 -*-
{
    'name': 'Webflow CRM Integration',
    'price': 49.99,
    'currency': 'USD',
    'version': '18.0.1.0.1',
    'category': 'Sales/CRM',
    'summary': 'Integrate Webflow Forms with Odoo CRM via secure webhooks.',
    'description': """
Webflow CRM Lead Integration
============================
Connect Webflow Forms to Odoo CRM using webhooks.

* Configure Webflow credentials inside Odoo (stored via ir.config_parameter).
* Auto-generate a unique webhook URL + secret to paste into Webflow.
* Public webhook controller that creates/updates CRM leads on every submission.
* Custom field mapping engine (Webflow field -> Odoo CRM field).
* Duplicate detection by email/phone with configurable strategy.
* Integration logs with retry support.
* Dashboard with health metrics.
* Connection wizard + Test Connection utilities.

Compatible with Odoo 18 and 19.
Runs on Odoo Online (SaaS), Odoo.sh, and on-premises; no external
dependencies and no server-level access required.
""",
    'author': 'Utsho Joy',
    'maintainer': 'Utsho Joy',
    'website': 'https://utshojoy.netlify.app/',
    'license': 'LGPL-3',
    'depends': ['crm', 'mail', 'utm'],
    'data': [
        'security/webflow_security.xml',
        'security/ir.model.access.csv',
        'data/webflow_field_mapping_data.xml',
        'data/ir_cron_data.xml',
        'views/webflow_integration_log_views.xml',
        'views/webflow_field_mapping_views.xml',
        'views/webflow_dashboard_views.xml',
        'wizard/webflow_connection_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/crm_lead_views.xml',
        'views/webflow_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
