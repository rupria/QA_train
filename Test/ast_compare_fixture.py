"""Persistent baseline used to verify Git diff and AST comparison.

Keep this file in Git. Comparison checks use its history instead of creating
and deleting a new fixture for every update.
"""

FIXTURE_REVISION = 2
DEFAULT_LIMIT = 2


class TestItem:
    """Small domain object with a method call for AST relationship checks."""

    def __init__(self, name: str, active: bool = True, category: str = "general"):
        self.name = name
        self.active = active
        self.category = category

    def display_name(self) -> str:
        return self.name.strip()

    def label(self) -> str:
        return f"{self.category.lower()}:{self.display_name()}"


def select_active(items: list[TestItem], limit: int = DEFAULT_LIMIT) -> list[str]:
    """Return active item names up to the requested limit."""
    selected = []
    for item in items:
        if item.active:
            selected.append(item.label())
        if len(selected) >= limit:
            break
    return selected


def build_summary(items: list[TestItem]) -> dict[str, object]:
    """Build deterministic output that can be inspected without I/O."""
    names = select_active(items)
    return {
        "revision": FIXTURE_REVISION,
        "count": len(names),
        "names": names,
        "limit_reached": len(names) == DEFAULT_LIMIT,
    }
