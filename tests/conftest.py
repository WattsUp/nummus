from __future__ import annotations

import random
import string

import pytest


class RandomString:

    @classmethod
    def __call__(cls, length: int = 20) -> str:
        return "".join(random.choice(string.ascii_letters) for _ in range(length))


@pytest.fixture
def rand_str() -> RandomString:
    """Returns a random string generator.

    Returns:
        RandomString generator
    """
    return RandomString()
