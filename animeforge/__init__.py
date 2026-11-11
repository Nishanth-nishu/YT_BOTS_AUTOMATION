"""AnimeForge: a local-first anime production platform.

Status (2026-11-11): Phase 1 only. What exists and is tested:
  animeforge.audit      hardware and dependency audit
  animeforge.storage    disk-space guard that must pass before any model download
  animeforge.registry   model licence registry and the gate for loading a model
  animeforge.rights     character database and asset rights registry (SQLite)
  animeforge.config     paths and settings

Nothing that needs a GPU exists yet: image generation, animation, the new voice
engines and lip-sync are not implemented, and no model has been benchmarked.
See docs/animeforge/ROADMAP.md for what each phase needs.
"""
