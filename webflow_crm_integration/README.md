# Webflow CRM Lead Integration

Connect **Webflow Forms** to **Odoo CRM** through secure webhooks. Every Webflow
form submission automatically creates (or updates) a CRM Lead in Odoo.

Compatible with **Odoo 18** and **Odoo 19**, and runs on **Odoo Online (SaaS)**,
**Odoo.sh** and **On-Premise** — it has no external Python dependencies and needs
no server-level access.

---

## Features

- **Integration settings** under *CRM → Configuration → Webflow Integration*
  (enable/disable, company, default sales team, salesperson, stage, tags, source,
  duplicate detection + strategy).
- **Secure credential storage** via `ir.config_parameter` (API token, Site ID,
  Workspace/Collection/Form IDs, webhook secret, API version).
- **Auto-generated webhook URL** + secret, with copy / regenerate / show-hide.
- **Connection wizard** that walks you through connecting Webflow step by step.
- **Test Connection** utilities: validate the API token & Site ID, send a test webhook.
- **Public webhook endpoint** `POST /webflow/webhook` with secret + optional
  HMAC-SHA256 signature validation and best-effort rate limiting.
- **Custom field mapping engine** (Webflow field → Odoo CRM field), editable in the UI.
- **Duplicate detection** by email/phone with *Create / Update / Skip* strategies.
- **Integration logs** with full payload, status, processing time, and one-click retry.
- **Dashboard** with volume, success rate, today's leads, last sync and health status.
- **Scheduled action** retries failed imports every 10 minutes.
- **Notifications**: subscribe/notify the salesperson and create a follow-up activity.

---

## Installation

1. Copy the `webflow_crm_integration` folder into your Odoo `addons` path.
2. Ensure the Python **`requests`** library is available (used by *Test Connection*).
   It ships with the standard Odoo runtime.
3. Restart the Odoo service:
   ```bash
   ./odoo-bin -c odoo.conf -u webflow_crm_integration
   ```
4. In Odoo, enable **Developer Mode**, go to **Apps**, click **Update Apps List**,
   search for *Webflow CRM Lead Integration* and click **Install**.

Dependencies: `crm`, `mail`, `utm` (all standard Odoo modules).

---

## Configuration

Open **CRM → Configuration → Webflow Integration**.

1. Toggle **Enable Webflow Integration**.
2. Fill in the **Webflow Credentials** (API token + Site ID at minimum).
3. Copy the **Webhook URL** and **Webhook Secret** shown in the *Webhook Endpoint*
   section (or run the **Connection Wizard**).
4. Set your defaults (sales team, salesperson, stage, tags, source).
5. (Optional) Turn on **Require HMAC Signature** for stronger security.

---

## Connecting a Webflow Form (User Guide)

1. In Odoo, copy the **Webhook URL**, e.g. `https://your-odoo.com/webflow/webhook`,
   and the **Webhook Secret**.
2. In **Webflow**, open **Project Settings → Integrations** (or use **Webflow Logic /
   form automation** if available on your plan).
3. **Add a webhook** with:
   - **URL** = the Odoo webhook URL.
   - **Trigger** = **Form Submission**.
   - **Secret** = paste the Odoo webhook secret. Send it either as:
     - HTTP header `X-Webhook-Secret: <secret>`, **or**
     - query string, e.g. `.../webflow/webhook?secret=<secret>`.
   - If you enabled **Require HMAC Signature** in Odoo, use Webflow's signed
     webhooks (headers `x-webflow-signature` and `x-webflow-timestamp`).
4. **Publish** your Webflow site.
5. Back in Odoo, click **Send Test Webhook** or submit the real form, then check
   **CRM → Configuration → Webflow Integration → Integration Logs**.

### Default field mapping

| Webflow Field  | Odoo CRM Field       |
| -------------- | -------------------- |
| Contact Name   | Contact Name         |
| Contact Email  | Email                |
| Contact Number | Phone                |
| Company Name   | Company Name         |
| Subject        | Opportunity (name)   |
| Contact Message| Description          |
| service type   | Tags                 |
| Budget         | Expected Revenue     |
| Country        | Country              |
| Page URL       | Source Page URL      |
| UTM Source     | Source (UTM)         |
| UTM Medium     | Medium (UTM)         |
| UTM Campaign   | Campaign (UTM)       |

Rename the **Webflow field** values to match your own form's labels — that's the
most common setup step. Keys are matched case-insensitively, so `Contact Email`,
`contact email`, and `CONTACT EMAIL` all work.

> **Full end-user guide:** see [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) for
> step-by-step configuration, the multi-company defaults + auto-fill behaviour,
> the dashboard, logs/retries, troubleshooting and an FAQ.

---

## Security

- Every request must carry the correct **secret** (header or query string), or a
  valid **HMAC-SHA256** signature when HMAC mode is enabled.
- Requests are **rate-limited** per source IP (best effort, per worker).
- Every request is **logged** with its payload and outcome.
- Configuration is restricted to the **Webflow: Administrator** group
  (system administrators are members by default).
- Credentials are stored via `ir.config_parameter` and never rendered in cleartext
  in list views.

---

## Testing

Run the module's unit tests:

```bash
./odoo-bin -c odoo.conf -d <db> -i webflow_crm_integration --test-enable --stop-after-init
```

The suite covers lead creation, field/UTM/country/budget mapping, duplicate
handling (update & skip), log retry and the dashboard aggregation.

---

## License

LGPL-3.
