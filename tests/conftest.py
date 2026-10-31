import pytest

from cipfried.network.xtea import XteaCipher, XteaKey
from tests.helpers import KEY, OTHER_KEY, make_cipher


@pytest.fixture
def key() -> XteaKey:
    return KEY


@pytest.fixture
def other_key() -> XteaKey:
    return OTHER_KEY


@pytest.fixture
def cipher() -> XteaCipher:
    return make_cipher(KEY)


@pytest.fixture
def other_cipher() -> XteaCipher:
    return make_cipher(OTHER_KEY)
