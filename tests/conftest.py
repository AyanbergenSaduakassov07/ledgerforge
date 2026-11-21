import pytest

from ledgerforge.env.env import AuditEnv
from ledgerforge.sim.secret import SECRET_ENV

DUP = {"faults": {"duplicate_invoice": 1}}


@pytest.fixture(autouse=True)
def _open_generator(monkeypatch):
    # Tests pin the open (keyless) generator; secret tests set their own key explicitly.
    monkeypatch.delenv(SECRET_ENV, raising=False)


@pytest.fixture
def env():
    e = AuditEnv("train")
    yield e
    e.close()
