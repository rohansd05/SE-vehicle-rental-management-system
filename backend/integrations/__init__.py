"""External services behind interfaces (CLAUDE.md, CO-7 sandbox mode).

Each service has interface.py (abstract base class), mock.py (deterministic,
in-memory) and a factory that picks the implementation from settings, so
tests never make a network call. There is no Maps integration.
"""
