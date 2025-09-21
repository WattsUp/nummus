"""Global nummus configuration."""

from __future__ import annotations

import configparser
import enum
from pathlib import Path

_PATH = Path("~").expanduser().joinpath(".nummus", ".config.ini")


class ConfigKey(enum.Enum):
    """Enumeration of configuration properties."""

    SECURE_ICON = "secure-icon"


_DEFAULTS = {
    ConfigKey.SECURE_ICON: "\u26bf",
}

_CACHE: dict[ConfigKey, str] = {}


def get(key: ConfigKey | str | None = None) -> str | dict[ConfigKey, str]:
    """Get global configuration value or values.

    Args:
        key: Key of value to fetch, None will return all as a dict

    Returns:
        String value of key or all as a dict{key: value} if key not given
        Will return default value if configuration does not exist

    """
    if len(_CACHE) == 0:
        config = configparser.ConfigParser()
        config["nummus"] = {k.value: v for k, v in _DEFAULTS.items()}
        config.read(_PATH)
        items = {ConfigKey(k): v for k, v in config["nummus"].items()}
        _CACHE.update(items)

    if key is not None:
        key = ConfigKey(key)
        return _CACHE[key]
    return _CACHE
