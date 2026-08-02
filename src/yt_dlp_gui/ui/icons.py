"""Lazy qtawesome loader -- defers icon-font loading past the first paint/event-loop tick."""
from __future__ import annotations

_qtawesome_mod = None


def _qta():
    global _qtawesome_mod
    if _qtawesome_mod is None:
        import qtawesome as qta

        _qtawesome_mod = qta
    return _qtawesome_mod


def icon(name: str):
    return _qta().icon(name)
