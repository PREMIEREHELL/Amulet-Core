from __future__ import annotations

import numpy

from amulet.world_interface.chunk.translators.bedrock import BaseBedrockTranslator

from PyMCTranslate.py3.translation_manager import Version


class BedrockNumericalTranslator(BaseBedrockTranslator):
    @staticmethod
    def is_valid(key):
        if key[0] != "leveldb":
            return False
        if not key[1] < (1, 2, 13):
            return False
        return True

    def _unpack_palette(self, version: Version, palette: numpy.ndarray):
        """
        Unpacks an int array of block ids and block data values [[1, 0], [2, 0]] into a numpy array of Block objects.
        :param version:
        :param palette:
        :return:
        """
        palette = numpy.array([version.ints_to_block(*entry) for entry in palette])
        return palette

    def _pack_palette(self, version: Version, palette: numpy.ndarray) -> numpy.ndarray:
        """
        Packs a numpy array of Block objects into an int array of block ids and block data values [[1, 0], [2, 0]].
        :param version:
        :param palette:
        :return:
        """
        palette = [version.block_to_ints(entry) for entry in palette]
        for index, value in enumerate(palette):
            if value is None:
                palette[index] = (
                    0,
                    0,
                )  # TODO: find some way for the user to specify this
        return numpy.array(palette)


TRANSLATOR_CLASS = BedrockNumericalTranslator
