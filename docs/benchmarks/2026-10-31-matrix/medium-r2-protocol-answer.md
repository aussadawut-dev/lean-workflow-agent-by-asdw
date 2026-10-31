██████████████░░░░░░ 71% review — Check source evidence and limitations

The source removes the Gmail OAuth/API connector while retaining ordinary Gmail-hosted SMTP.

**Removed HTTP endpoints.** The regression test enumerates these five method/path pairs and expects `404` for each:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

Evidence: `application/apps/api/src/routes/gmail-removed.test.ts#L5`. The application registration list contains no Gmail registrar, and unmatched requests have a JSON `404` fallback: `application/apps/api/src/app.ts#L337`, `application/apps/api/src/app.ts#L431`. Ordinary SMTP configuration and test-email routes remain: `application/apps/api/src/modules/connectors/connector-settings.controller.ts#L189`.

**Exact stored-secret cleanup.** The migration executes:

```sql
DELETE FROM "connector_secrets"
WHERE "field" IN ('gmail-settings', 'gmail-grant')
   OR "field" LIKE 'gmail-state:%';
```

Thus it deletes entire rows with either exact field name, or a field beginning `gmail-state:`—including the bare prefix, since `%` permits an empty suffix. There is **no workspace or connector-type restriction**. All other field values remain untouched by this statement, including `smtpPassword` and `emailApiKey`; it does not update connector configuration or other tables. `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql#L1`

The companion test creates six secrets under connector type `AI`, executes that SQL, and expects only `emailApiKey` and `smtpPassword` to remain. It covers two state suffixes, but not multiple workspaces/types, the empty suffix, or near-match names; those broader predicate conclusions follow from the SQL itself. `application/prisma/gmail-secret-cleanup.test.ts#L13`

**Ordinary `smtp.gmail.com` behavior.** Transport selection defaults to SMTP unless stored `mailTransport` is exactly `"API"`. The SMTP settings path retrieves `smtpPassword` and returns ordinary SMTP fields without `emailApi`. `application/packages/server/src/modules/connectors/connector-settings.service.ts#L194`, `application/packages/server/src/modules/connectors/smtp-settings.usecases.ts#L15`

The sender chooses HTTP email delivery only when `config.emailApi` is supplied. Otherwise it validates SMTP settings, requires a password when a username exists, resolves the host, opens a TCP/TLS connection, and performs SMTP authentication and delivery. Neither the Gmail hostname nor `GMAIL_API_ENABLED` selects a Gmail API branch. `application/packages/server/src/infrastructure/providers/smtp-client.ts#L183`, `application/packages/server/src/infrastructure/providers/smtp-client.ts#L217`

The focused regression test sets `GMAIL_API_ENABLED=1`, uses `smtp.gmail.com:587` with STARTTLS, supplies no password, and expects `SMTP_PASSWORD_MISSING` with no `fetch` call. This specifically covers early rejection, not successful Gmail delivery. `application/packages/server/src/smtp-gmail-host.test.ts#L4`

**Limits:** These are source conclusions and test assertions inspected offline. I executed no tests or migration and checked no deployed system. Migration application, actual HTTP responses, credentials, network access, and successful SMTP delivery remain unverified; middleware may reject requests before the unmatched-route fallback.
