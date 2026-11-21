# Third-party notices

Runtime: **none**. LedgerForge uses only the Python 3.11 standard library at run and evaluation time.
No code, data or vocabulary was copied from other projects. All company, vendor and product names are
invented (`src/ledgerforge/sim/profiles.py`).

Development-only dependencies (pinned in `uv.lock`, not redistributed):

| Package | Version | Licence | Use |
|---|---|---|---|
| pytest | 9.2.0 | MIT | tests |
| ruff | 0.17.6 | MIT | lint/format |
| jsonschema | 4.26.0 | MIT | schema contract tests |
| attrs, iniconfig, pluggy, referencing, rpds-py, jsonschema-specifications | per uv.lock | MIT | transitive |
| packaging | per uv.lock | Apache-2.0 OR BSD-2-Clause | transitive |
| Pygments | per uv.lock | BSD-2-Clause | transitive |
| typing_extensions | per uv.lock | PSF-2.0 | transitive |

Build backend: hatchling (MIT). Container base image `python:3.11-slim` (PSF + Debian licences) and
the `uv` binary (MIT OR Apache-2.0) are pulled at build time only.
