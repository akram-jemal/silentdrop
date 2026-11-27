"""Observable outcomes shared by the CLI and interactive interface."""

from dataclasses import dataclass
from enum import Enum

from .catalog import Service


class Verdict(str, Enum):
    LOADED = "Page loaded"
    PLAYED = "Video played"
    BLOCK_PAGE = "Network block page detected"
    UNVERIFIED = "Couldn't verify"


@dataclass(frozen=True)
class Result:
    service: Service
    verdict: Verdict
    summary: str
    details: tuple[str, ...]
