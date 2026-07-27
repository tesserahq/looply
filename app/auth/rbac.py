from typing import Awaitable, Callable, Optional
from fastapi import Request
from tessera_sdk.server.dependencies.authorization import authorize

ProjectResolver = Callable[[Request], Awaitable[Optional[str]]]

PREFIX = "looply"


class RBACActions:
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


async def global_domain(_: Request) -> str:
    """
    RBAC domain resolver for resources with no per-tenant domain concept.

    Looply has no existing project/tenant model of its own (unlike Sendly,
    which authorizes per its own project_id). Campaign.project_id is Sendly's
    domain, nullable, and not a Looply tenant boundary, so it isn't a
    meaningful RBAC domain here — authorize against a fixed wildcard domain
    instead, mirroring Sendly's own fallback (`project_id or "*"`).
    """
    return "*"


def build_rbac_dependencies(*, resource: str):
    return {
        "create": authorize(
            resource=f"{PREFIX}.{resource}",
            action=RBACActions.CREATE,
            domain_resolver=global_domain,
        ),
        "read": authorize(
            resource=f"{PREFIX}.{resource}",
            action=RBACActions.READ,
            domain_resolver=global_domain,
        ),
        "update": authorize(
            resource=f"{PREFIX}.{resource}",
            action=RBACActions.UPDATE,
            domain_resolver=global_domain,
        ),
        "delete": authorize(
            resource=f"{PREFIX}.{resource}",
            action=RBACActions.DELETE,
            domain_resolver=global_domain,
        ),
    }
