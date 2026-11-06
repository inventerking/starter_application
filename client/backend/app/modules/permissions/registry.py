"""The controlled permission registry.

Modules declare their permissions here at import time. Authorization code accepts only
PermissionDefinition objects, so an arbitrary string can never become a permission check.
"""

import re
from dataclasses import dataclass

_RESOURCE = re.compile(r"^[a-z][a-z_]*(\.[a-z][a-z_]*)*$")
_ACTION = re.compile(r"^[a-z][a-z_]*$")


@dataclass(frozen=True)
class PermissionDefinition:
    resource: str
    action: str
    description: str

    @property
    def code(self) -> str:
        return f"{self.resource}.{self.action}"


class PermissionRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, PermissionDefinition] = {}

    def register(self, resource: str, action: str, description: str) -> PermissionDefinition:
        if not _RESOURCE.match(resource) or not _ACTION.match(action):
            raise ValueError(f"Invalid permission name: {resource}.{action}")
        definition = PermissionDefinition(resource, action, description)
        if definition.code in self._definitions:
            raise ValueError(f"Duplicate permission: {definition.code}")
        self._definitions[definition.code] = definition
        return definition

    def all(self) -> list[PermissionDefinition]:
        return list(self._definitions.values())


registry = PermissionRegistry()
