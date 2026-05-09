# Secret Vault Integration Plan

## Goal

Move production secrets from `.env` files to a managed secret vault.

## Recommended Providers

- AWS Secrets Manager
- Azure Key Vault
- GCP Secret Manager
- HashiCorp Vault

## Integration Steps

1. Create a secret inventory (DB URL, JWT secret, Twilio, AI provider keys).
2. Provision vault secrets per environment (`dev`, `staging`, `prod`).
3. Grant service identity access via least-privilege IAM roles.
4. Add startup secret loader for runtime config population.
5. Remove plaintext secrets from deployment manifests and CI variables.
6. Rotate secrets and validate zero-downtime rollout.

## Runtime Pattern

- Fetch secrets at startup and cache in memory.
- Never log secret values.
- Use versioned secret references for safe rotation.

## Rollback Plan

- Keep last known-good secret version.
- Revert service to prior secret version if health checks fail.
