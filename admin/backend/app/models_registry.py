"""Imports every model of this domain so that Base.metadata is complete for Alembic."""

from app.modules.admins import models as _admins  # noqa: F401
from app.modules.audit import models as _audit  # noqa: F401
from app.modules.authentication import models as _authentication  # noqa: F401
from app.modules.mfa import models as _mfa  # noqa: F401
from app.modules.permissions import models as _permissions  # noqa: F401
from app.modules.roles import models as _roles  # noqa: F401
