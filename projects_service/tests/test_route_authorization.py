"""Every project-scoped route must carry an authorization dependency.

Per-route checks are the kind of thing that is correct on the day it is written and forgotten
on the next endpoint. This walks the app's own route table instead of trusting a reviewer to
notice, so a new route that takes a project_id and does not check membership fails the build.
"""

import inspect

import pytest

from projects_service.core.access import (
    project_for_member,
    project_for_owner,
)
from projects_service.core.auth import current_admin, current_user, require_service_key
from projects_service.main import app

# Reached by the load balancer's target-group check and the deploy smoke tests, before any
# user exists. Authenticating them would fail every health check.
UNAUTHENTICATED_PATHS = {"/", "/health"}

AUTHZ_DEPENDENCIES = {project_for_member, project_for_owner}
# A peer service is a caller too: sibling scores are pushed by the AI service from a
# background task with no user request in flight, so it presents a service key rather than a
# token. What matters is that the route identifies *someone*.
AUTH_DEPENDENCIES = AUTHZ_DEPENDENCIES | {
    current_user,
    current_admin,
    require_service_key,
}


def _dependency_callables(route) -> set:
    """Every dependency reachable from a route, including nested ones."""
    found = set()
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return found

    stack = [dependant]
    while stack:
        current = stack.pop()
        if current.call is not None:
            found.add(current.call)
        stack.extend(current.dependencies)
    return found


def _all_routes():
    """Every route, flattened.

    FastAPI 0.141 wraps an included router in a single `_IncludedRouter` entry instead of
    splicing its routes into app.routes. Iterating app.routes alone on that version yields
    nothing to check, and a test that finds nothing passes - so this walks into wrappers
    rather than trusting the shape of the version currently installed.
    """
    seen = []
    stack = list(app.routes)
    while stack:
        route = stack.pop()
        nested = getattr(route, "routes", None)
        if nested:
            stack.extend(nested)
            continue
        seen.append(route)
    return seen


def _project_scoped_routes():
    for route in _all_routes():
        path = getattr(route, "path", "")
        if path in UNAUTHENTICATED_PATHS or not hasattr(route, "dependant"):
            continue
        if "{project_id}" in path:
            yield route


def test_the_route_inventory_is_not_empty():
    """The other tests here pass by finding no offenders, so finding nothing at all passes too.

    This is the guard against that: if a FastAPI upgrade changes how routes are exposed, this
    fails loudly instead of the whole file turning into a no-op that reports success.
    """
    assert len(list(_project_scoped_routes())) >= 5, (
        "expected several project-scoped routes; the inventory is not seeing them"
    )


def test_every_project_scoped_route_checks_membership():
    offenders = []
    for route in _project_scoped_routes():
        dependencies = _dependency_callables(route)
        if not (dependencies & AUTHZ_DEPENDENCIES):
            offenders.append(f"{sorted(route.methods)} {route.path}")

    assert not offenders, (
        "These routes take a project_id but never check that the caller may see that "
        "project, so passing someone else's id would be enough to reach their data: "
        + "; ".join(sorted(offenders))
    )


def test_every_non_public_route_is_authenticated():
    offenders = []
    for route in _all_routes():
        path = getattr(route, "path", "")
        if path in UNAUTHENTICATED_PATHS or not hasattr(route, "dependant"):
            continue
        # Auto-generated docs endpoints have no dependant of their own.
        if path.startswith("/openapi") or path in {
            "/docs",
            "/redoc",
            "/docs/oauth2-redirect",
        }:
            continue

        if not (_dependency_callables(route) & AUTH_DEPENDENCIES):
            offenders.append(f"{sorted(route.methods)} {path}")

    assert not offenders, (
        "These routes identify no caller, so they act on behalf of whoever asked: "
        + "; ".join(sorted(offenders))
    )


def test_admin_routes_require_admin_specifically():
    """current_user is not enough on /admin: any signed-in user would pass it."""
    admin_routes = [
        route
        for route in _all_routes()
        if getattr(route, "path", "").startswith("/admin")
    ]
    assert admin_routes, "expected at least one admin route"

    for route in admin_routes:
        assert current_admin in _dependency_callables(route), (
            f"{route.path} must depend on current_admin"
        )


@pytest.mark.parametrize("check", [project_for_member, project_for_owner])
def test_access_checks_take_the_project_id_from_the_path(check):
    """A check that did not read project_id would pass while verifying nothing."""
    assert "project_id" in inspect.signature(check).parameters
