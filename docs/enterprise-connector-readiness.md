# AANA Enterprise Connector Readiness

The enterprise connector readiness layer turns AANA's connector contracts into concrete setup requirements for the `enterprise_ops_pilot` package.

It covers seven live connector families:

- CRM/support
- ticketing
- email send
- IAM/access
- CI/CD
- deployment
- data export

Generate the readiness artifact:

```powershell
python scripts/aana_cli.py enterprise-connectors --output examples/enterprise_ops_connector_readiness.json
```

The AIx audit runner also writes the same artifact into its output directory:

```text
eval_outputs/aix_audit/enterprise_ops_pilot/enterprise-connector-readiness.json
```

## What The Layer Defines

Each connector declares:

- connector ID and display name
- pilot surface
- mapped adapters
- source system examples
- required evidence
- auth and least-privilege scopes
- redaction requirements
- freshness requirements
- rate limits
- setup steps
- smoke tests
- failure routes
- shadow-mode requirements
- go-live blockers

## Default Safety Position

All live connector execution is disabled by default.

Before customer approval:

- unapproved live connector usage routes to `defer`
- write operations are disabled in shadow mode
- tokens and secrets cannot enter audit logs
- raw private content cannot enter audit logs
- evidence text must be redacted, summarized, or fingerprinted
- production use requires domain-owner signoff, security review, observability, human-review operations, and measured shadow-mode results

## Connector Summary

| Connector | Surface | Example systems | Primary route before approval |
| --- | --- | --- | --- |
| `crm_support` | support/customer communications | Salesforce, Zendesk, HubSpot, custom CRM | `defer` |
| `ticketing` | support/customer communications | Zendesk, Jira Service Management, ServiceNow, Linear | `defer` |
| `email_send` | support/customer communications | Gmail, Outlook, SendGrid, SMTP relay | `defer` |
| `iam` | data/access controls | Okta, Entra ID, AWS IAM, Google Cloud IAM | `defer` |
| `ci` | DevOps/release controls | GitHub Actions, GitLab CI, CircleCI, Buildkite, Jenkins | `defer` |
| `deployment` | DevOps/release controls | Argo CD, Spinnaker, Kubernetes, GitHub Deployments | `defer` |
| `data_export` | data/access controls | Snowflake, BigQuery, Databricks, Redshift, S3/GCS | `defer` |

## Customer Implementation Flow

1. Select the connectors needed for the pilot scope.
2. Assign each connector a customer system owner.
3. Approve read-only shadow-mode access.
4. Map customer records into redacted evidence objects.
5. Run connector smoke tests.
6. Run AANA AIx Audit in shadow mode.
7. Review AIx Report, dashboard metrics, and evidence gaps.
8. Decide whether to continue shadow mode, remediate, or approve limited enforcement.

This layer makes connector setup concrete, but it does not move production ownership away from the customer. Customer security, compliance, domain owners, and system owners still approve live access and production use.
