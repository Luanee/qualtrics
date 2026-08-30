from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import QualtricsClient


class APIDomain:
    def __init__(self, client: QualtricsClient) -> None:
        self._client = client
