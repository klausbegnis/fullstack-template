"""Canonical PostgreSQL namespaces used by the bounded contexts."""

INFRA_SCHEMA = "infra"
IAM_SCHEMA = "iam"

DOMAIN_SCHEMAS: tuple[str, ...] = (IAM_SCHEMA,)
SCHEMA_NAMES: tuple[str, ...] = (INFRA_SCHEMA, *DOMAIN_SCHEMAS)

__all__ = [
    "INFRA_SCHEMA",
    "IAM_SCHEMA",
    "DOMAIN_SCHEMAS",
    "SCHEMA_NAMES",
]
