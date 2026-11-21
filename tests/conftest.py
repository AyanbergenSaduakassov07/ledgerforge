import pytest

from ledgerforge.env.env import AuditEnv

DUP = {"faults": {"duplicate_invoice": 1}}


@pytest.fixture
def env():
    e = AuditEnv("train")
    yield e
    e.close()
