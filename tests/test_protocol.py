"""Tests for framed binary parser behavior."""

from __future__ import annotations

import numpy as np

from flexitac.protocol import FrameParser
from flexitac.types import SensorGeometry


def test_parser_reads_complete_frame() -> None:
    geometry = SensorGeometry(rows=2, cols=3)
    parser = FrameParser(geometry=geometry)

    payload = bytes([1, 2, 3, 4, 5, 6])
    frames = parser.feed(b"\xaa\x55" + payload)

    assert len(frames) == 1
    assert frames[0].dtype == np.uint8
    np.testing.assert_array_equal(frames[0], np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8))


def test_parser_handles_garbage_and_split_marker() -> None:
    geometry = SensorGeometry(rows=2, cols=2)
    parser = FrameParser(geometry=geometry)

    part_a = b"junk\xaa"
    part_b = b"\x55\x01\x02\x03\x04"

    first = parser.feed(part_a)
    second = parser.feed(part_b)

    assert first == []
    assert len(second) == 1
    np.testing.assert_array_equal(second[0], np.array([[1, 2], [3, 4]], dtype=np.uint8))


def test_parser_reads_multiple_frames_from_one_chunk() -> None:
    geometry = SensorGeometry(rows=1, cols=2)
    parser = FrameParser(geometry=geometry)

    chunk = b"\xaa\x55\x01\x02\xaa\x55\x03\x04"
    frames = parser.feed(chunk)

    assert len(frames) == 2
    np.testing.assert_array_equal(frames[0], np.array([[1, 2]], dtype=np.uint8))
    np.testing.assert_array_equal(frames[1], np.array([[3, 4]], dtype=np.uint8))
