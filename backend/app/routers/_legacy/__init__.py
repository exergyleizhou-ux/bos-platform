"""DEPRECATED — Legacy operational routers (Phase 0.5).

These routes were moved here on 2026-05-16 as part of the BOS Platform
Phase 0.5 reorganization. They are not part of the V5 9-group target API
(BOS Core 7 layers) and are scheduled for a 6-month evaluation period
before either being removed or split into a separate ``bos-ops``
service.

URL prefixes are intentionally unchanged so that existing frontend
callers keep working. Mount calls in ``app.routers.__init__`` flag every
endpoint here with ``deprecated=True`` so OpenAPI surfaces the status.

Do NOT add new endpoints to this package.
"""
