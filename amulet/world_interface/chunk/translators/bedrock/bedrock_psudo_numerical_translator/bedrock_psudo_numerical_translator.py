from __future__ import annotations

from typing import Union, Tuple

from amulet.world_interface.chunk.translators import Translator


class BedrockPaletteTranslator(Translator):
    def _translator_key(
        self, version_number: Tuple[int, int, int]
    ) -> Tuple[str, Tuple[int, int, int]]:
        return "bedrock", version_number

    @staticmethod
    def is_valid(key):
        if key[0] != "leveldb":
            return False
        if not (1, 2, 13) <= key[1] <= (1, 13, 0):
            return False
        return True


TRANSLATOR_CLASS = BedrockPaletteTranslator
