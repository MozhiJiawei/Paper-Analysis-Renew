from __future__ import annotations


class RouteNotImplementedError(NotImplementedError):
    """Raised when a route is intentionally scaffolded but not implemented yet."""


class RouteContractError(ValueError):
    """Raised when route outputs violate the scaffold contract."""
