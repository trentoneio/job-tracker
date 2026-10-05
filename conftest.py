"""Root conftest — makes the repo importable when running bare ``pytest``.

Pytest only adds each test module's directory (``tests/``) to ``sys.path``,
so without this file ``import app`` fails unless pytest is launched as
``python -m pytest``. Importing this conftest puts the repo root on
``sys.path`` for both invocations, so the README's plain ``pytest`` works.
"""
