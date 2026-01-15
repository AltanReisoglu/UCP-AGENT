# Copyright 2026 UCP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""UCP."""

from abc import ABC
from typing import Any
from a2a.server.agent_execution import RequestContext
from a2a.types import AgentCard, AgentExtension

class A2AExtensionBase(ABC):
    """Base class for A2A extensions."""

    URI: str

    def __init__(self, description: str = "", params: dict[str, Any] | None = None):
        self._description = description
        self._params = params


    def get_extension_uri(self) -> str:
        """
        Returns:
            str: Extension URI
        """
        return self.URI

    def get_agent_extension(self) -> AgentExtension:
        """
        Returns:
            AgentExtension: Agent Extension for this extension.
        """
        return AgentExtension(
            uri=self.get_extension_uri(), description=self._description, required=False, params=self._params
        )

    def add_to_agent_card(self, card: AgentCard) -> AgentCard:
        if card.capabilities.extensions is None:
            card.capabilities.extensions = []
        card.capabilities.extensions.append(self.get_agent_extension())
        return card

    def activate(self, context: RequestContext) -> None:
        """Possibly activate this extension, depending on the request context."""
        if not context.requested_extensions:
            return

        if self.get_extension_uri() in context.requested_extensions:
            context.add_activated_extension(self.get_extension_uri())