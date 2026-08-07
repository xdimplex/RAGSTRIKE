# Payloads

DummyAttack generates its single payload in code (``payloads()`` in ``plugin.py``), so this
directory is empty by design.

**How a real plugin uses this folder.** Drop JSON, YAML, or TXT files here and call
``self.load_payloads()`` from your ``payloads()`` method. The PayloadLoader accepts:

- ``.yaml`` / ``.yml`` — a list of payload mappings or a top-level ``payloads:`` key.
- ``.json`` — the same shape.
- ``.txt`` — one payload per non-empty line, ``#`` comments ignored.

Filename order is preserved so payload sequences stay reproducible across runs.
