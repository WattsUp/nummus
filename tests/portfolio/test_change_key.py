from __future__ import annotations

import pytest

from nummus import encryption
from nummus import exceptions as exc
from nummus.models import Config, ConfigKey
from nummus.portfolio import Portfolio


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_change_db_key(
    capsys: pytest.CaptureFixture,
    empty_portfolio_encrypted: tuple[Portfolio, str],
    rand_str: str,
) -> None:
    new_key = rand_str
    p, old_key = empty_portfolio_encrypted
    with p.begin_session() as s:
        web_key_enc = (
            s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).one()[0]
        )
    web_key = p.decrypt_s(web_key_enc)

    p.change_key(new_key)

    captured = capsys.readouterr()
    assert not captured.out
    # tqdm in here
    assert captured.err

    with p.begin_session() as s:
        web_key_enc = (
            s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).one()[0]
        )
    new_web_key = p.decrypt_s(web_key_enc)
    assert new_web_key == web_key
    assert new_web_key != new_key

    # Unlocking with new_key works
    Portfolio(p.path, new_key)

    # Unlocking with key doesn't work
    with pytest.raises(exc.UnlockingError):
        Portfolio(p.path, old_key)


def test_change_db_key_short(empty_portfolio: Portfolio) -> None:
    with pytest.raises(exc.InvalidKeyError):
        empty_portfolio.change_key("a")


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_change_web_key(
    empty_portfolio_encrypted: tuple[Portfolio, str],
    rand_str: str,
) -> None:
    new_key = rand_str
    p, db_key = empty_portfolio_encrypted
    p.change_web_key(new_key)

    with p.begin_session() as s:
        web_key_enc = (
            s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).one()[0]
        )
    web_key = p.decrypt_s(web_key_enc)
    assert web_key == new_key
    assert web_key != db_key


def test_change_web_key_short(empty_portfolio: Portfolio) -> None:
    with pytest.raises(exc.InvalidKeyError):
        empty_portfolio.change_web_key("a")
