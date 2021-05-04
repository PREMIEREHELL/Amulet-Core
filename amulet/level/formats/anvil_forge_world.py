from __future__ import annotations

from .anvil_world import AnvilFormat
from amulet.utils.format_utils import check_all_exist, load_leveldat


class AnvilForgeFormat(AnvilFormat):
    @staticmethod
    def is_valid(path: str) -> bool:
        if not check_all_exist(path, "level.dat"):
            return False

        try:
            level_dat_root = load_leveldat(path)
        except:
            return False

        if "Data" not in level_dat_root:
            return False

        if "FML" in level_dat_root:
            return True

        return False

    @property
    def game_version_string(self) -> str:
        try:
            return f'Java Forge {self.root_tag["Data"]["Version"]["Name"].value}'
        except Exception:
            return f"Java Forge Unknown Version"


export = AnvilForgeFormat
