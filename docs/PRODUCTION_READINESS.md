# Production Readiness Checklist

## Completed in repository
- typed API contracts
- request IDs
- structured logging
- Prometheus metrics
- health/readiness endpoints
- input bounds
- data contracts
- leakage-safe forecasting split
- model and optimizer version fields
- explicit unmet-demand objective
- non-root Docker runtime definition
- CI test/compile/dependency checks
- Kubernetes templates

## Required before real operations
- SSO/RBAC and authorization model
- managed secrets and key rotation
- private network and TLS
- persistent run/audit database
- asynchronous optimization queue
- real routing/traffic feeds
- model registry and artifact lineage
- drift and data-quality monitoring
- load/chaos testing
- backup and disaster recovery
- calibrated costs, capacities, SLAs and business rules
- human approval workflow for operational changes
- security scanning and dependency governance
