import re
from typing import Annotated

from pydantic import AfterValidator

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(value: str) -> str:
    """Remove HTML tags from a string."""
    return _TAG_RE.sub("", value).strip()


def _sanitize(value: str) -> str:
    return strip_html(value)


# Use as a type annotation: `name: SanitizedStr` or `notes: SanitizedStr | None`
SanitizedStr = Annotated[str, AfterValidator(_sanitize)]
