"""Shared helpers for MeritDrop direct mode tests."""

import sys

import pytest

# A fixed "now" for deterministic time travel. Unix 1767225600.
BASE_ISO = "2030-01-01T00:00:00Z"


def to_hex(addr_bytes):
    """Convert address bytes to hex matching contract output."""
    if hasattr(addr_bytes, "as_hex"):
        return addr_bytes.as_hex
    from genlayer.py.types import Address

    return Address(addr_bytes).as_hex


def set_time(iso_str: str) -> None:
    """Pin the contract's view of block time.

    The direct VM's ``warp()`` does not refresh ``message_raw['datetime']``,
    which is what the contract's ``_now()`` reads, so we mutate it directly.
    """
    import genlayer.gl as gl

    gl.message_raw["datetime"] = iso_str


@pytest.fixture(autouse=True)
def _reset_block_time():
    """Keep block time deterministic across tests.

    ``genlayer.gl`` is imported once per session, so ``message_raw['datetime']``
    leaks between tests. Reset it to a fixed base before and after each test, so
    a test that travels past a deadline cannot leave the clock there for the
    next one.
    """
    _reset()
    yield
    _reset()


def _reset():
    if "genlayer.gl" in sys.modules:
        gl = sys.modules["genlayer.gl"]
        if getattr(gl, "message_raw", None) is not None:
            gl.message_raw["datetime"] = BASE_ISO
