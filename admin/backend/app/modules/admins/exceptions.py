"""Admin Management errors."""

from app.core.exceptions import Conflict, PermissionDenied


class SuperAdminProtected(PermissionDenied):
    code = "super_admin_protected"
    message = "Only a Super Admin can do that to a Super Admin."


class SuperAdminDeletionForbidden(PermissionDenied):
    code = "super_admin_deletion_forbidden"
    message = "A Super Admin cannot be deleted. Remove Super Admin status through the CLI first."


class SelfActionForbidden(PermissionDenied):
    code = "self_action_forbidden"
    message = "You cannot do that to your own account."


class TargetMorePrivileged(PermissionDenied):
    code = "target_more_privileged"
    message = "You cannot manage an account that has access you do not have."


class LastSuperAdmin(Conflict):
    code = "last_super_admin"
    message = "The last active Super Admin cannot be deactivated."


class DuplicateIdentity(Conflict):
    code = "duplicate_identity"
    message = "That email or username is already in use."
