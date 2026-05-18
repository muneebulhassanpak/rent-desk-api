import re
import secrets


def generate_slug(name: str) -> str:
    """Convert a name to a URL-safe slug with a random suffix for uniqueness."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    suffix = secrets.token_hex(3)
    return f"{slug}-{suffix}"
