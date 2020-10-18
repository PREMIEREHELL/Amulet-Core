from __future__ import annotations

import os
import shutil
from typing import Union, Generator, Optional, Tuple, Callable, Any, Set, TYPE_CHECKING
from types import GeneratorType
import warnings
import traceback

from amulet import log
from amulet.api.block import Block
from amulet.api.block_entity import BlockEntity
from amulet.api.entity import Entity
from amulet.api.registry import BlockManager
from amulet.api.registry.biome_manager import BiomeManager
from amulet.api.errors import ChunkDoesNotExist, ChunkLoadError, LevelDoesNotExist
from amulet.api.chunk import Chunk
from amulet.api.selection import SelectionGroup, SelectionBox
from amulet.api.paths import get_temp_dir
from amulet.api.data_types import (
    OperationType,
    Dimension,
    VersionIdentifierType,
    ChunkCoordinates,
)
from amulet.utils.world_utils import block_coords_to_chunk_coords
from .chunk_manager import ChunkManager
from amulet.api.history.history_manager import MetaHistoryManager

if TYPE_CHECKING:
    from PyMCTranslate import TranslationManager
    from amulet.api.wrapper import FormatWrapper


class ChunkWorld:
    """
    ChunkWorld handles chunk editing of any world format via an separate and flexible data format.
    """

    def __init__(
        self, directory: str, format_wrapper: "FormatWrapper", temp_dir: str = None
    ):
        self._directory = directory
        if temp_dir is None:
            self._temp_directory = get_temp_dir(self._directory)
        else:
            self._temp_directory = temp_dir

        self._format_wrapper = format_wrapper
        self._format_wrapper.open()

        self._block_palette = BlockManager()
        self._block_palette.get_add_block(
            Block(namespace="universal_minecraft", base_name="air")
        )  # ensure that index 0 is always air

        self._biome_palette = BiomeManager()
        self._biome_palette.get_add_biome("universal_minecraft:plains")

        self._history_manager = MetaHistoryManager()

        self._chunks: ChunkManager = ChunkManager(
            os.path.join(self._temp_directory, "chunks"), self
        )

        self._history_manager.register(self._chunks, True)

    @property
    def sub_chunk_size(self) -> int:
        """The normal dimensions of the chunk"""
        return self._format_wrapper.sub_chunk_size

    @property
    def world_path(self) -> str:
        """The directory where the world is located"""
        return self._directory

    @property
    def changed(self) -> bool:
        """Has any data been modified but not saved to disk"""
        return self._history_manager.changed or self._format_wrapper.changed

    @property
    def history_manager(self) -> MetaHistoryManager:
        return self._history_manager

    @property
    def chunk_history_manager(self) -> ChunkManager:
        """A class storing previous versions of chunks to roll back to as required."""
        warnings.warn(
            "World.chunk_history_manager is depreciated and will be removed in the future. Please use World.chunks instead",
            DeprecationWarning,
        )
        return self._chunks

    def create_undo_point(self):
        """Create a restore point for all chunks that have changed."""
        self._history_manager.create_undo_point()

    @property
    def translation_manager(self) -> "TranslationManager":
        """An instance of the translation class for use with this world."""
        return self._format_wrapper.translation_manager

    @property
    def world_wrapper(self) -> "FormatWrapper":
        """A class to access data directly from the world."""
        return self._format_wrapper

    @property
    def palette(self) -> BlockManager:
        """The manager for the universal blocks in this world. New blocks must be registered here before adding to the world."""
        warnings.warn(
            "World.palette is depreciated and will be removed in the future. Please use World.block_palette instead",
            DeprecationWarning,
        )
        return self.block_palette

    @property
    def block_palette(self) -> BlockManager:
        """The manager for the universal blocks in this world. New blocks must be registered here before adding to the world."""
        return self._block_palette

    @property
    def biome_palette(self) -> BiomeManager:
        """The manager for the universal blocks in this world. New blocks must be registered here before adding to the world."""
        return self._biome_palette

    @property
    def selection_bounds(self) -> SelectionGroup:
        """The selection(s) that all chunk data must fit within. Usually +/-30M for worlds."""
        return self._format_wrapper.selection

    def all_chunk_coords(self, dimension: Dimension) -> Set[Tuple[int, int]]:
        """The coordinates of every chunk in this world.
        This is the combination of chunks saved to the world and chunks yet to be saved."""
        return self._chunks.all_chunk_coords(dimension)

    def has_chunk(self, cx: int, cz: int, dimension: Dimension) -> bool:
        """Does the chunk exist. This is a quick way to check if the chunk exists without loading it.

        :param cx: The x coordinate of the chunk.
        :param cz: The z coordinate of the chunk.
        :param dimension: The dimension to load the chunk from.
        :return: True if the chunk exists. Calling get_chunk on this chunk may still throw ChunkLoadError
        """
        return self._chunks.has_chunk(dimension, cx, cz)

    def get_chunk(self, cx: int, cz: int, dimension: Dimension) -> Chunk:
        """
        Gets the chunk data of the specified chunk coordinates.
        If the chunk does not exist ChunkDoesNotExist is raised.
        If some other error occurs then ChunkLoadError is raised (this error will also catch ChunkDoesNotExist)

        :param cx: The X coordinate of the desired chunk
        :param cz: The Z coordinate of the desired chunk
        :param dimension: The dimension to get the chunk from
        :return: A Chunk object containing the data for the chunk
        :raises: `amulet.api.errors.ChunkDoesNotExist` if the chunk does not exist or `amulet.api.errors.ChunkLoadError` if the chunk failed to load for some reason. (This also includes it not existing)
        """
        return self._chunks.get_chunk(dimension, cx, cz)

    def get_block(self, x: int, y: int, z: int, dimension: Dimension) -> Block:
        """
        Gets the universal Block object at the specified coordinates

        :param x: The X coordinate of the desired block
        :param y: The Y coordinate of the desired block
        :param z: The Z coordinate of the desired block
        :param dimension: The dimension of the desired block
        :return: The universal Block object representation of the block at that location
        :raise: Raises ChunkDoesNotExist or ChunkLoadError if the chunk was not loaded.
        """
        cx, cz = block_coords_to_chunk_coords(x, z, sub_chunk_size=self.sub_chunk_size)
        offset_x, offset_z = x - 16 * cx, z - 16 * cz

        return self.get_chunk(cx, cz, dimension).get_block(offset_x, y, offset_z)

    def _chunk_box(
        self, cx: int, cz: int, sub_chunk_size: Optional[int] = None,
    ):
        """Get a SelectionBox containing the whole of a given chunk"""
        if sub_chunk_size is None:
            sub_chunk_size = self.sub_chunk_size
        return SelectionBox.create_chunk_box(cx, cz, sub_chunk_size)

    def get_coord_box(
        self,
        dimension: Dimension,
        selection: Union[SelectionGroup, SelectionBox, None] = None,
        create_missing_chunks=False,
    ) -> Generator[Tuple[ChunkCoordinates, SelectionBox], None, None]:
        """Given a selection will yield chunk coordinates and `SelectionBox`es into that chunk
        If not given a selection will use the bounds of the object.

        :param selection: SelectionGroup or SelectionBox into the world
        :param dimension: The dimension to take effect in
        :param create_missing_chunks: If a chunk does not exist an empty one will be created (defaults to false). Use this with care.
        """
        if isinstance(selection, SelectionBox):
            selection = SelectionGroup(selection)
        elif selection is None:
            selection = self.selection_bounds
        elif not isinstance(selection, SelectionGroup):
            raise TypeError(f"Expected a SelectionGroup but got {type(selection)}")

        selection: SelectionGroup
        if create_missing_chunks or selection.footprint_area < 1_000_000:
            if create_missing_chunks:
                for coord, box in selection.chunk_boxes(self.sub_chunk_size):
                    yield coord, box
            else:
                for (cx, cz), box in selection.chunk_boxes(self.sub_chunk_size):
                    if self.has_chunk(cx, cz, dimension):
                        yield (cx, cz), box

        else:
            # if the selection gets very large iterating over the whole selection and accessing chunks can get slow
            # instead we are going to iterate over the chunks and get the intersection of the selection
            for cx, cz in self.all_chunk_coords(dimension):
                box = SelectionGroup(
                    SelectionBox.create_chunk_box(cx, cz, self.sub_chunk_size)
                )

                if selection.intersects(box):
                    chunk_selection = selection.intersection(box)
                    for sub_box in chunk_selection.selection_boxes:
                        yield (cx, cz), sub_box

    def get_chunk_boxes(
        self,
        dimension: Dimension,
        selection: Union[SelectionGroup, SelectionBox, None] = None,
        create_missing_chunks=False,
    ) -> Generator[Tuple[Chunk, SelectionBox], None, None]:
        """Given a selection will yield chunks and `SelectionBox`es into that chunk
        If not given a selection will use the bounds of the object.

        :param selection: SelectionGroup or SelectionBox into the world
        :param dimension: The dimension to take effect in
        :param create_missing_chunks: If a chunk does not exist an empty one will be created (defaults to false). Use this with care.
        """
        for (cx, cz), box in self.get_coord_box(dimension, selection, create_missing_chunks):
            try:
                chunk = self.get_chunk(cx, cz, dimension)
            except ChunkDoesNotExist:
                if create_missing_chunks:
                    chunk = Chunk(cx, cz)
                    self.put_chunk(chunk, dimension)
                else:
                    continue
            except ChunkLoadError:
                log.error(f"Error loading chunk\n{traceback.format_exc()}")
                continue
            yield chunk, box

    def get_chunk_slice_box(
        self,
        selection: Union[SelectionGroup, SelectionBox],
        dimension: Dimension,
        create_missing_chunks=False,
    ) -> Generator[Tuple[Chunk, Tuple[slice, slice, slice], SelectionBox], None, None]:
        """Given a selection will yield chunks, slices into that chunk and the corresponding box

        :param selection: SelectionGroup or SelectionBox into the world
        :param dimension: The dimension to take effect in
        :param create_missing_chunks: If a chunk does not exist an empty one will be created (defaults to false)
        Usage:
        for chunk, slice, box in world.get_chunk_slices(selection):
            chunk.blocks[slice] = ...
        """
        for chunk, box in self.get_chunk_boxes(
            dimension, selection, create_missing_chunks
        ):
            slices = box.chunk_slice(chunk.cx, chunk.cz, self.sub_chunk_size)
            yield chunk, slices, box

    def save(
        self,
        wrapper: "FormatWrapper" = None,
        progress_callback: Callable[[int, int], None] = None,
    ):
        """Save the world using the given wrapper.
        Leave as None to save back to the input wrapper.
        Optional progress callback to let the calling program know the progress. Input format chunk_index, chunk_count"""
        for chunk_index, chunk_count in self.save_iter(wrapper):
            if progress_callback is not None:
                progress_callback(chunk_index, chunk_count)

    def save_iter(
        self, wrapper: "FormatWrapper" = None
    ) -> Generator[Tuple[int, int], None, None]:
        """Save the world using the given wrapper.
        Leave as None to save back to the input wrapper."""
        chunk_index = 0

        changed_chunks = list(self._chunks.changed_chunks())
        chunk_count = len(changed_chunks)

        if wrapper is None:
            wrapper = self._format_wrapper

        output_dimension_map = wrapper.dimensions

        # perhaps make this check if the directory is the same rather than if the class is the same
        save_as = wrapper is not self._format_wrapper
        if save_as:
            # The input wrapper is not the same as the loading wrapper (save-as)
            # iterate through every chunk in the input world and save them to the wrapper
            log.info(
                f"Converting world {self._format_wrapper.path} to world {wrapper.path}"
            )
            wrapper.translation_manager = (
                self._format_wrapper.translation_manager
            )  # TODO: this might cause issues in the future
            for dimension in self._format_wrapper.dimensions:
                chunk_count += len(
                    list(self._format_wrapper.all_chunk_coords(dimension))
                )

            for dimension in self._format_wrapper.dimensions:
                try:
                    if dimension not in output_dimension_map:
                        continue
                    for cx, cz in self._format_wrapper.all_chunk_coords(dimension):
                        log.info(f"Converting chunk {dimension} {cx}, {cz}")
                        try:
                            chunk = self._format_wrapper.load_chunk(cx, cz, dimension)
                            wrapper.commit_chunk(chunk, dimension)
                        except ChunkLoadError:
                            log.info(f"Error loading chunk {cx} {cz}", exc_info=True)
                        chunk_index += 1
                        yield chunk_index, chunk_count
                        if not chunk_index % 10000:
                            wrapper.save()
                            self._format_wrapper.unload()
                            wrapper.unload()
                except LevelDoesNotExist:
                    continue

        for dimension, cx, cz in changed_chunks:
            if dimension not in output_dimension_map:
                continue
            try:
                chunk = self.get_chunk(cx, cz, dimension)
            except ChunkDoesNotExist:
                wrapper.delete_chunk(cx, cz, dimension)
            except ChunkLoadError:
                pass
            else:
                wrapper.commit_chunk(chunk, dimension)
                chunk.changed = False
            chunk_index += 1
            yield chunk_index, chunk_count
            if not chunk_index % 10000:
                wrapper.save()
                wrapper.unload()

        self._history_manager.mark_saved()
        log.info(f"Saving changes to world {wrapper.path}")
        wrapper.save()
        log.info(f"Finished saving changes to world {wrapper.path}")

    def close(self):
        """Close the attached world and remove temporary files
        Use changed method to check if there are any changes that should be saved before closing."""
        # TODO: add "unsaved changes" check before exit
        shutil.rmtree(self._temp_directory, ignore_errors=True)
        self._format_wrapper.close()

    def unload(self, safe_area: Optional[Tuple[Dimension, int, int, int, int]] = None):
        """Unload all chunks not in the safe area
        Safe area format: dimension, min chunk X|Z, max chunk X|Z"""
        self._chunks.unload(safe_area)
        self._format_wrapper.unload()

    def unload_unchanged(self):
        """Unload all data that has not been marked as changed."""
        self._chunks.unload_unchanged()

    def create_chunk(self, cx: int, cz: int, dimension: Dimension) -> Chunk:
        chunk = Chunk(cx, cz)
        self.put_chunk(chunk, dimension)
        return chunk

    def put_chunk(self, chunk: Chunk, dimension: Dimension):
        """Add a chunk to the universal world database"""
        self._chunks.put_chunk(chunk, dimension)

    def delete_chunk(self, cx: int, cz: int, dimension: Dimension):
        """Delete a chunk from the universal world database"""
        self._chunks.delete_chunk(dimension, cx, cz)

    def extract_structure(self, selection: SelectionGroup, dimension: Dimension) -> ImmutableStructure:
        """Extract the area in the SelectionGroup from the world as a new structure"""
        return ImmutableStructure.from_world(self, selection, dimension)

    def get_version_block(
        self,
        x: int,
        y: int,
        z: int,
        dimension: Dimension,
        version: VersionIdentifierType,
    ) -> Tuple[Union[Block, Entity], Optional[BlockEntity]]:
        """
        Get a block at the specified location and convert it to the format of the version specified
        Note the odd return format. In most cases this will return (Block, None) or (Block, BlockEntity)
        but in select cases like item frames may return (Entity, None)

        :param x: The X coordinate of the desired block
        :param y: The Y coordinate of the desired block
        :param z: The Z coordinate of the desired block
        :param dimension: The dimension of the desired block
        :param version: The version to get the block converted to.
        :return: The block at the given location converted to the `version` format. Note the odd return format.
        :raise: Raises ChunkDoesNotExist or ChunkLoadError if the chunk was not loaded.
        """
        cx, cz = block_coords_to_chunk_coords(x, z, sub_chunk_size=self.sub_chunk_size)
        chunk = self.get_chunk(cx, cz, dimension)
        offset_x, offset_z = x - 16 * cx, z - 16 * cz

        output, extra_output, _ = self.translation_manager.get_version(
            *version
        ).block.from_universal(
            chunk.get_block(offset_x, y, offset_z), chunk.block_entities.get((x, y, z))
        )
        return output, extra_output

    def set_version_block(
        self,
        x: int,
        y: int,
        z: int,
        dimension: Dimension,
        version: VersionIdentifierType,
        block: Block,
        block_entity: BlockEntity,
    ):
        """
        Convert the block and block_entity from the given version format to the universal format and set at the location

        :param x: The X coordinate of the desired block
        :param y: The Y coordinate of the desired block
        :param z: The Z coordinate of the desired block
        :param dimension: The dimension of the desired block
        :param version: The version to get the block converted to.
        :param block:
        :param block_entity:
        :return: The block at the given location converted to the `version` format. Note the odd return format.
        :raise: Raises ChunkLoadError if the chunk was not loaded correctly.
        """
        cx, cz = block_coords_to_chunk_coords(x, z, sub_chunk_size=self.sub_chunk_size)
        try:
            chunk = self.get_chunk(cx, cz, dimension)
        except ChunkDoesNotExist:
            chunk = self.create_chunk(cx, cz, dimension)
        offset_x, offset_z = x - 16 * cx, z - 16 * cz

        (
            universal_block,
            universal_block_entity,
            _,
        ) = self.translation_manager.get_version(*version).block.to_universal(
            block, block_entity
        )
        chunk.set_block(offset_x, y, offset_z, block),
        chunk.block_entities[(x, y, z)] = block_entity

    # def get_entities_in_box(
    #     self, box: "SelectionGroup"
    # ) -> Generator[Tuple[Coordinates, List[object]], None, None]:
    #     # TODO: some of this logic can probably be moved the chunk class and have this method call that
    #     # TODO: update this to use the newer entity API
    #     out_of_place_entities = []
    #     entity_map: Dict[Tuple[int, int], List[List[object]]] = {}
    #     for chunk, subbox in self.get_chunk_boxes(box):
    #         entities = chunk.entities
    #         in_box = list(filter(lambda e: e.location in subbox, entities))
    #         not_in_box = filter(lambda e: e.location not in subbox, entities)
    #
    #         in_box_copy = deepcopy(in_box)
    #
    #         entity_map[chunk.coordinates] = [
    #             not_in_box,
    #             in_box,
    #         ]  # First index is the list of entities not in the box, the second is for ones that are
    #
    #         yield chunk.coordinates, in_box_copy
    #
    #         if (
    #             in_box != in_box_copy
    #         ):  # If an entity has been changed, update the dictionary entry
    #             entity_map[chunk.coordinates][1] = in_box_copy
    #         else:  # Delete the entry otherwise
    #             del entity_map[chunk.coordinates]
    #
    #     for chunk_coords, entity_list_list in entity_map.items():
    #         chunk = self.get_chunk(*chunk_coords)
    #         in_place_entities = list(
    #             filter(
    #                 lambda e: chunk_coords
    #                 == entity_position_to_chunk_coordinates(e.location),
    #                 entity_list_list[1],
    #             )
    #         )
    #         out_of_place = filter(
    #             lambda e: chunk_coords
    #             != entity_position_to_chunk_coordinates(e.location),
    #             entity_list_list[1],
    #         )
    #
    #         chunk.entities = in_place_entities + list(entity_list_list[0])
    #
    #         if out_of_place:
    #             out_of_place_entities.extend(out_of_place)
    #
    #     if out_of_place_entities:
    #         self.add_entities(out_of_place_entities)
    #
    # def add_entities(self, entities):
    #     proper_entity_chunks = map(
    #         lambda e: (entity_position_to_chunk_coordinates(e.location), e,), entities,
    #     )
    #     accumulated_entities: Dict[Tuple[int, int], List[object]] = {}
    #
    #     for chunk_coord, ent in proper_entity_chunks:
    #         if chunk_coord in accumulated_entities:
    #             accumulated_entities[chunk_coord].append(ent)
    #         else:
    #             accumulated_entities[chunk_coord] = [ent]
    #
    #     for chunk_coord, ents in accumulated_entities.items():
    #         chunk = self.get_chunk(*chunk_coord)
    #
    #         chunk.entities += ents
    #
    # def delete_entities(self, entities):
    #     chunk_entity_pairs = map(
    #         lambda e: (entity_position_to_chunk_coordinates(e.location), e,), entities,
    #     )
    #
    #     for chunk_coord, ent in chunk_entity_pairs:
    #         chunk = self.get_chunk(*chunk_coord)
    #         entities = chunk.entities
    #         entities.remove(ent)
    #         chunk.entities = entities

    def run_operation(
        self, operation: OperationType, dimension: Dimension, *args, create_undo=True
    ) -> Any:
        try:
            out = operation(self, dimension, *args)
            if isinstance(out, GeneratorType):
                try:
                    while True:
                        next(out)
                except StopIteration as e:
                    out = e.value
        except Exception as e:
            self.restore_last_undo_point()
            raise e
        if create_undo:
            self.create_undo_point()
        return out

    def undo(self):
        """Undoes the last set of changes to the world"""
        self._history_manager.undo()

    def redo(self):
        """Redoes the last set of changes to the world"""
        self._history_manager.redo()

    def restore_last_undo_point(self):
        """Restore the world to the state it was when self.create_undo_point was called.
        If an operation errors there may be modifications made that did not get tracked.
        This will revert those changes."""
        self._history_manager.restore_last_undo_point()


# this needs to be down here to stop a circular import error
from ..immutable_structure import ImmutableStructure
