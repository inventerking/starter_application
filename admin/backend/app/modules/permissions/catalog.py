"""Importing this module loads every permission declaration into the registry."""

from app.modules.admins import permissions as _admins  # noqa: F401
from app.modules.audit import permissions as _audit  # noqa: F401
from app.modules.permissions import definitions as _definitions  # noqa: F401
from app.modules.roles import permissions as _roles  # noqa: F401
