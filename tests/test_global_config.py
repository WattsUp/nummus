from __future__ import annotations

from nummus import global_config
from tests.base import TestBase


class TestGlobalConfig(TestBase):
    def test_get(self) -> None:
        config_path = self._TEST_ROOT.joinpath("config.ini")
        original_path = global_config._PATH  # noqa: SLF001

        try:
            global_config._PATH = config_path  # noqa: SLF001

            # Clear cache
            global_config._CACHE.clear()  # noqa: SLF001

            # Config file doesn't exist so expect defaults
            config = global_config.get()
            if isinstance(config, dict):
                for k, v in global_config._DEFAULTS.items():  # noqa: SLF001
                    self.assertEqual(config.pop(k), v)
                self.assertEqual(len(config), 0)
            else:
                self.fail("config was not a dict")

            with config_path.open("w", encoding="utf-8") as file:
                file.write("[nummus]\n")

            # Empty section should still be defaults
            config = global_config.get()
            if isinstance(config, dict):
                for k, v in global_config._DEFAULTS.items():  # noqa: SLF001
                    self.assertEqual(config.pop(k), v)
                self.assertEqual(len(config), 0)
            else:
                self.fail("config was not a dict")

            secure_icon = self.random_string()
            with config_path.open("w", encoding="utf-8") as file:
                file.write(f"[nummus]\nsecure-icon = {secure_icon}\n")

            self.assertEqual(
                global_config.get(global_config.ConfigKey.SECURE_ICON),
                secure_icon,
            )
            self.assertEqual(
                global_config.get("secure-icon"),
                secure_icon,
            )
        finally:
            global_config._PATH = original_path  # noqa: SLF001
