"""Model licence registry and the gate every model load must pass.

    from animeforge.registry import require
    model = require("wan2.1")          # returns the entry, or raises LicenceError

`require` is the only sanctioned way to pick a model. It refuses anything that
is blocked or unverified, and for a conditional model it refuses until every
condition has been acknowledged in configuration. There is deliberately no
fallback: if a model is refused the caller fails, it does not quietly load a
different model with different terms.

    python -m animeforge.registry            # print the table
    python -m animeforge.registry --role voice
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

REGISTRY_FILE = Path(__file__).with_name("models.json")
STATUSES = ("cleared", "conditional", "unverified", "blocked")
REQUIRED = ("id", "role", "name", "repo", "checkpoint", "code_license", "weight_license", "status", "commercial", "conditions", "hardware", "install", "sources", "benchmark")


class LicenceError(RuntimeError):
    """Raised when a model may not be used for monetized output."""


def load(path: Path | None = None) -> dict[str, dict]:
    data = json.loads((path or REGISTRY_FILE).read_text(encoding="utf-8"))
    models = {m["id"]: m for m in data["models"]}
    if len(models) != len(data["models"]):
        raise ValueError("duplicate model id in the registry")
    return models


def problems(models: dict[str, dict] | None = None) -> list[str]:
    """Structural mistakes in the registry itself."""
    out: list[str] = []
    for mid, m in (models or load()).items():
        for key in REQUIRED:
            if key not in m:
                out.append(f"{mid}: missing field '{key}'")
        if m.get("status") not in STATUSES:
            out.append(f"{mid}: status must be one of {STATUSES}")
        if m.get("status") == "conditional" and not m.get("conditions"):
            out.append(f"{mid}: a conditional model must list its conditions")
        if m.get("status") in ("cleared", "conditional") and not m.get("sources"):
            out.append(f"{mid}: a usable model must cite where its licence was read")
    return out


def require(model_id: str, acknowledged: Iterable[str] = (), models: dict[str, dict] | None = None) -> dict:
    """Return the registry entry for a model that may be used, or raise LicenceError.

    `acknowledged` lists the ids of conditional models whose conditions the operator
    has read and accepted (ANIMEFORGE_ACK in the environment, or the config file)."""
    models = models or load()
    if model_id not in models:
        raise LicenceError(f"'{model_id}' is not in the model registry. Add it, with its licences, before using it.")
    m = models[model_id]
    status = m["status"]
    if status == "blocked":
        raise LicenceError(f"{m['name']} is blocked for monetized output: {m['commercial']}")
    if status == "unverified":
        todo = " ".join(m["conditions"]) or "Read its licence and update the registry."
        raise LicenceError(f"{m['name']} has not been cleared: {m['commercial']} To do: {todo}")
    if status == "conditional" and model_id not in set(acknowledged):
        listed = "\n  - ".join(m["conditions"])
        raise LicenceError(f"{m['name']} may be used only under these conditions:\n  - {listed}\nAcknowledge them by adding '{model_id}' to ANIMEFORGE_ACK.")
    return m


def table(role: str | None = None) -> str:
    rows = [m for m in load().values() if not role or m["role"] == role]
    width = max(len(m["id"]) for m in rows) if rows else 0
    return "\n".join(f"{m['id']:<{width}}  {m['status']:<11}  {m['role']:<16}  code: {m['code_license'] or '-'} | weights: {m['weight_license'] or '-'}" for m in sorted(rows, key=lambda m: (STATUSES.index(m["status"]), m["role"], m["id"])))

