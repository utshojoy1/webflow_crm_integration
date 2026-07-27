# Webflow CRM Lead Integration — User Guide

This guide walks you through connecting a **Webflow form** to **Odoo CRM** so that
every submission automatically becomes a CRM lead. It is written for the Odoo
administrator who sets the integration up and for the sales users who work the
leads afterwards.

> Compatible with **Odoo 18 and 19**. Module: `webflow_crm_integration`.

---

## 1. What it does

```
Webflow form  ──►  POST /webflow/webhook  ──►  Odoo lead service  ──►  CRM Lead
   (submit)          (secret / HMAC)            (field mapping,
                                                 duplicate check)
```

- A visitor submits a form on your published Webflow site.
- Webflow sends the submission to Odoo's secure webhook endpoint.
- Odoo validates the request, maps the fields, and **creates or updates** a CRM
  lead — applying your default sales team, salesperson, stage, source and tags.
- Every request is logged, and failures are retried automatically.

---

## 2. Where everything lives

Everything is under **CRM → Configuration → Webflow Integration**:

| Menu | Purpose |
|------|---------|
| **Configuration** | The main settings page (enable, defaults, credentials, webhook, notifications). |
| **Connection Wizard** | A guided, step-by-step way to connect Webflow. |
| **Dashboard** | Health metrics: volume, success rate, today's leads, last sync. |
| **Field Mappings** | Define how Webflow fields map to CRM lead fields. |
| **Integration Logs** | Every webhook request, with payload, status and one-click retry. |

### Who can access it

| Group | Can do |
|-------|--------|
| **Webflow: User** | View the Dashboard and Integration Logs. |
| **Webflow: Administrator** | Everything, including settings, credentials and mappings. |

System administrators are Webflow Administrators automatically. Assign the groups
under **Settings → Users & Companies → Users**.

---

## 3. Quick start (about 5 minutes)

1. **CRM → Configuration → Webflow Integration → Configuration.**
2. Turn on **Enable Webflow Integration**.
3. Under **Webflow Credentials**, paste your **API Token** and **Site ID**, then
   click **Test Webflow API** — you should see a green ✅ confirmation.
4. Under **Webhook Endpoint**, click **Register Webhook in Webflow** (Automatic
   setup). This creates the Form Submission webhook in Webflow for you, URL and
   secret included.
5. Click **Send Test Webhook** — a test lead should appear, and a **Success** row
   should show in **Integration Logs**.
6. Publish your Webflow site and submit the real form to confirm.

That's it. The sections below explain each option in detail and cover the manual
setup path if you prefer not to share an API token.

---

## 4. Configuration in detail

Open **CRM → Configuration → Webflow Integration → Configuration**.

### 4.1 General

**Enable Webflow Integration** — the master switch. While this is **off**, the
webhook endpoint rejects all requests (`HTTP 403`), so nothing is created.

### 4.2 Defaults (applied to every imported lead)

| Setting | Meaning |
|---------|---------|
| **Companies** | The companies this integration serves. New leads are created in the **first** selected company; the rest define scope. (Shown only in multi-company databases.) |
| **Default Sales Team** | Sales team assigned to new leads. |
| **Default Salesperson** | Owner assigned to new leads. |
| **Default Lead Stage** | Starting CRM stage. |
| **Default Lead Source** | UTM source stamped on the lead (unless the form sends its own). |
| **Default Tags** | Tags added to every imported lead. |

**Auto-fill.** The first time you open the settings, a couple of fields are
pre-populated to save you a step:

- **Companies** → every company you have access to (or your previous single-company setting if upgrading).
- **Default Tags** → a tag named "Webflow" if one already exists, otherwise left as-is.

**Default Sales Team, Default Salesperson, Default Lead Stage and Default Lead
Source are left blank on purpose** — choose them explicitly for your setup.

Auto-filled values are only suggestions until you click **Save**, and any value
you have already saved is never overwritten. Change any of them freely.

### 4.3 Duplicate detection

| Setting | Meaning |
|---------|---------|
| **Enable Duplicate Detection** | Check for an existing lead before creating a new one. |
| **Duplicate Strategy** | What to do on a match: **Create New Lead**, **Update Existing Lead**, or **Skip Duplicate**. |

Matches are found by **email** or **phone** within the target company. *Update*
refreshes the existing lead's fields; *Skip* ignores the submission (and logs it
as *Skipped*).

### 4.4 Webflow credentials

| Field | Notes |
|-------|-------|
| **Webflow API Token** | A token from your Webflow workspace with **webhook scope**. Stored securely, shown masked. |
| **Site ID** | Your Webflow Site ID. |
| **Workspace ID / Collection ID / Form ID** | Optional; for reference and future features. |
| **API Version** | Defaults to `2.0.0` (Webflow Data API v2). Leave as-is unless told otherwise. |

Buttons:
- **Test Webflow API** — validates the token + Site ID against Webflow.
- **Open Documentation** — opens Webflow's webhook docs.

### 4.5 Webhook endpoint

| Field | Notes |
|-------|-------|
| **Webhook URL** | The public endpoint, e.g. `https://your-odoo.com/webflow/webhook`. Copy it into Webflow. |
| **Webhook Secret** | Shared secret used to authenticate requests. Copy / regenerate as needed. |
| **Require HMAC Signature** | Stricter validation using Webflow's signed webhooks — see [Security](#8-security). |

Actions are grouped:

- **Automatic setup** (in the recommended order)
  - **Open Setup Wizard** — the guided connection flow; a good first stop.
  - **Register Webhook in Webflow** — uses your API token to create the Form
    Submission webhook automatically (URL + secret included). Requires a token
    with webhook scope. *Turn off "Require HMAC Signature" for this
    query-string secret method.*
  - **Verify / List Webhooks** — lists the webhooks currently registered on the
    site so you can confirm.
- **Manual setup & utilities**
  - **Regenerate Secret** — issues a fresh secret (remember to update Webflow).
  - **Send Test Webhook** — simulates a submission to confirm lead creation.

### 4.6 Notifications

| Setting | Meaning |
|---------|---------|
| **Notify Salesperson** | Subscribes and notifies the assigned salesperson on each new lead. |
| **Create Activity** | Schedules a "Follow up on Webflow lead" to-do activity for the salesperson. |

---

## 5. Connecting a Webflow form

You have two paths. **Automatic** is fastest; **Manual** avoids sharing an API token.

### Option A — Automatic (recommended)

1. (Optional) Click **Open Setup Wizard** for a guided walkthrough — it's the
   first button in the *Automatic setup* group.
2. Enter your **API Token** and **Site ID**, then **Test Webflow API**.
3. Click **Register Webhook in Webflow**. Existing Form Submission webhooks that
   point at this Odoo endpoint are replaced, so the secret stays in sync.
4. Click **Verify / List Webhooks** to confirm it is registered.
5. **Publish** your Webflow site.

### Option B — Manual

1. Copy the **Webhook URL** and **Webhook Secret** from Odoo (or run the
   **Connection Wizard**).
2. In Webflow, open **Project Settings → Integrations / Webhooks** (or use Webflow
   Logic / form automation on plans that support it).
3. Add a webhook with:
   - **Trigger** = **Form Submission**
   - **URL** = the Odoo webhook URL. To pass the secret in the URL, append it as a
     query string: `.../webflow/webhook?secret=YOUR_SECRET`.
   - Or send the secret as the HTTP header `X-Webhook-Secret: YOUR_SECRET`.
4. **Publish** your Webflow site.
5. Submit the form (or use **Send Test Webhook**) and check **Integration Logs**.

---

## 6. Field mapping

Go to **CRM → Configuration → Webflow Integration → Field Mappings**.

Each row maps one **Webflow field name** to a **CRM lead field**. Matching is
**case-insensitive**, so `Contact Email`, `contact email`, and `CONTACT EMAIL`
all work.

### Default mappings shipped with the module

| Webflow field | CRM lead field | Type |
|---------------|----------------|------|
| Contact Name | Contact Name | Text |
| Contact Email | Email | Email |
| Contact Number | Phone | Phone |
| Company Name | Company Name | Text |
| Subject | Opportunity / Lead name | Text |
| Contact Message | Description | Text |
| service type | Tags | CRM Tag |
| Budget | Expected Revenue | Number |
| Country | Country | Country |
| Page URL | Source Page URL | Text |
| UTM Source | Source | UTM Source |
| UTM Medium | Medium | UTM Medium |
| UTM Campaign | Campaign | UTM Campaign |

> These names match a specific Webflow form. **Rename the "Webflow field" values
> to match your own form's field labels** — that is the single most common setup
> step. Reorder with the drag handle; deactivate a row with its toggle.

### Mapping types

| Type | Behaviour |
|------|-----------|
| **Text / Email / Phone** | Written as-is to the target field. |
| **Number** | Cleaned (`$12,500` → `12500`) and written to a numeric field. |
| **CRM Tag** | Finds or creates a `crm.tag` and adds it to the lead. |
| **Country** | Matches a country by name or ISO code. |
| **UTM Source / Medium / Campaign** | Finds or creates the matching UTM record. |

Every write is validated against the real CRM field type. A misconfigured
mapping (e.g. text into a number field) is **skipped with a warning** rather than
crashing the whole submission.

### Capturing the submission page

Webflow sends the page URL outside the form data. The module exposes it as a
field named **`Page URL`**, mapped by default to **Source Page URL** on the lead.

---

## 7. Testing your setup

- **Send Test Webhook** (settings) — creates a sample lead end-to-end.
- **Integration Logs** — every request appears here. A green **Success** row with a
  linked lead means it worked.
- Submit the **real form** on the published site and confirm the lead appears in
  **CRM → Leads** (use the **From Webflow** filter).

---

## 8. Dashboard

**CRM → Configuration → Webflow Integration → Dashboard** shows:

- **Total / Successful / Failed / Skipped** webhook counts.
- **Success Rate (%)** and a **Health** badge:
  - **Healthy** ≥ 90% success
  - **Degraded** ≥ 60%
  - **Unhealthy** < 60%
  - **No Activity** when nothing has been received yet
- **Today's Leads** and **Last Sync**.
- Buttons to jump to **All Logs** or **Failed Only**.

Click **Refresh** to recompute.

---

## 9. Integration logs & retries

Each log row records the event, form name, status, HTTP code, linked lead,
processing time, retry count, source IP, the raw payload, and any error message.

- **Retry** (button on failed/skipped rows) re-processes the stored payload.
- A **scheduled action** automatically retries failed imports **every 10 minutes**,
  up to **5 attempts** per record. So a transient error usually recovers on its own.

---

## 10. Troubleshooting

| Symptom | Likely cause & fix |
|---------|--------------------|
| Webhook returns **403 Integration disabled** | Turn on **Enable Webflow Integration**. |
| **401 Invalid webhook secret** | The secret in Webflow doesn't match Odoo. Copy it again, or **Regenerate Secret** and update Webflow. |
| **401 Missing HMAC signature** | **Require HMAC Signature** is on but Webflow isn't sending a signed webhook. Either use Webflow's signed webhooks, or turn HMAC off and use the shared-secret method. |
| **429 Too many requests** | Rate limit hit (60 requests/minute per IP). Normal traffic won't trigger this. |
| Lead created but **fields empty** | Your Webflow field names don't match the **Field Mappings**. Rename the mappings to match your form. Check the log payload to see the exact keys Webflow sent. |
| **Test Webflow API** fails with 401/403 | Invalid API token or missing webhook scope. |
| **Test Webflow API** fails with 404 | Wrong Site ID. |
| `"requests" library not available` | The Python `requests` package is missing from the Odoo runtime (only affects the API/registration buttons, not inbound webhooks). |
| Duplicates piling up | Turn on **Duplicate Detection** and pick **Update** or **Skip**. |

To see exactly what Webflow sent, open the failing row in **Integration Logs** and
read the **Payload** tab.

---

## 11. Security

- Every inbound request must carry the correct **secret** (header or query string),
  or a valid **HMAC-SHA256** signature when HMAC mode is enabled.
- **HMAC mode** verifies the `x-webflow-signature` / `x-webflow-timestamp` headers.
  It only works if your Webflow signing key equals the configured secret — for the
  simple query-string method, leave HMAC **off**.
- Requests are **rate-limited** per source IP (best effort, per worker).
- Credentials are stored via `ir.config_parameter`, shown masked, and never printed
  in list views.
- Configuration is limited to the **Webflow: Administrator** group.

---

## 12. FAQ

**Does this send data back to Webflow?**
No. Odoo only receives submissions. The API token is used only to test the
connection and to register/list webhooks.

**Can I use more than one form or site?**
Yes. Point multiple Webflow forms at the same webhook URL. Use **Field Mappings**
that cover all the field names your forms use.

**Which company gets the lead in a multi-company setup?**
The **first** company in the **Companies** list. The others define the scope of
the setup.

**Will re-installing/upgrading lose my mappings?**
No. Default mappings are marked `noupdate`, so your edits are preserved across
upgrades.

---

*Module: `webflow_crm_integration` · Author: Utsho Joy · License: LGPL-3*
