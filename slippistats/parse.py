from __future__ import annotations

import io
import mmap
import os
from pathlib import Path
from typing import Any, BinaryIO, Callable

import ubjson

from .event import End, EventType, Frame, Start
from .log import log
from .metadata import Metadata
from .util import (
    Enum,
    expect_bytes,
    unpack_int32,
    unpack_uint8,
    unpack_uint16,
)

# TODO parse maybe to pass around metadata/start event to allow for "smarter" parsing
# otherwise, frame event does contain character so that can be used

# It would also carry slippi file version


class ParseEvent(Enum):
    """Parser events, used as keys for event handlers.
    Docstrings indicate the type of object that will be passed to each handler."""

    METADATA = 0
    METADATA_RAW = 1
    START = 2
    FRAME = 3
    END = 4
    FRAME_START = 5
    ITEM = 6
    FRAME_END = 7


class ParseError(IOError):
    def __init__(self, message, filename=None, pos=None):
        super().__init__(message)
        self.filename = filename
        self.pos = pos

    def __str__(self):
        return f'Parse error ({self.filename or "?"} {self.pos if self.pos else "?"}): {super().__str__()}'


def _parse_event_payloads(stream):
    (code,) = unpack_uint8(stream.read(1))
    (this_size,) = unpack_uint8(stream.read(1))

    event_type = EventType(code)
    if event_type is not EventType.EVENT_PAYLOADS:
        raise ValueError(f"expected event payloads, but got {event_type}")

    this_size -= 1  # includes size byte for some reason
    command_count = this_size // 3
    if command_count * 3 != this_size:
        raise ValueError(f"payload size not divisible by 3: {this_size}")

    sizes = {}
    for i in range(command_count):
        (code,) = unpack_uint8(stream.read(1))
        (size,) = unpack_uint16(stream.read(2))
        sizes[code] = size
        try:
            EventType(code)
        except ValueError:
            log.info("ignoring unknown event type: 0x%02x" % code)

    # log.debug(f'event payload sizes: {sizes}')
    return (2 + this_size, sizes)


# This essentially acts as a jump table in _parse_event,
# saves a lot of processing (~15% over py-slippi) on a very hot match statement and enum call
# If python was compiled, this would probably be unnecessary.
EVENT_PARSE_DISPATCH = {
    EventType.GAME_START: lambda stream: Start._parse(stream),
    EventType.FRAME_START: lambda stream: Frame.Event(Frame.Event.Id(stream), Frame.Event.Type.START, stream),
    EventType.FRAME_PRE: lambda stream: Frame.Event(Frame.Event.PortId(stream), Frame.Event.Type.PRE, stream),
    EventType.FRAME_POST: lambda stream: Frame.Event(Frame.Event.PortId(stream), Frame.Event.Type.POST, stream),
    EventType.ITEM: lambda stream: Frame.Event(Frame.Event.Id(stream), Frame.Event.Type.ITEM, stream),
    EventType.FRAME_END: lambda stream: Frame.Event(Frame.Event.Id(stream), Frame.Event.Type.END, stream),
    EventType.GAME_END: lambda stream: End._parse(stream),
}


def _parse_event(event_stream: io.BytesIO, payload_sizes: dict):
    (code,) = unpack_uint8(event_stream.read(1))
    # log.debug(f'Event: 0x{code:x}')

    # It's not great, but ripping this out saves something like 15-30% of processing time. tell() is INCREDIBLY slow
    # remember starting pos for better error reporting
    # try: base_pos = event_stream.tell() if event_stream.seekable() else None
    # except AttributeError: base_pos = None

    try:
        size = payload_sizes[code]
    except KeyError:
        log.warn("unexpected event type: 0x%02x" % code)

    stream = io.BytesIO(event_stream.read(size))

    try:
        event = EVENT_PARSE_DISPATCH.get(code, None)
        if callable(event):
            event = event(stream)

        return (1 + size, event, code)

    except Exception as exc:
        # Calculate the stream position of the exception as best we can.
        # This won't be perfect: for an invalid enum, the calculated position
        # will be *after* the value at minimum, and may be farther than that
        # due to `unpack`ing multiple values at once. But it's better than
        # leaving it up to the `catch` clause in `parse`, because that will
        # always report a position that's at the end of an event (due to
        # `event_stream.read` above).
        raise ParseError(str(exc), pos=stream.tell())  # pos = base_pos + stream.tell() if base_pos else None)


# exceptional ugliness to implement a jump table instead of a bunch of conditionals or a match statement.
# It's gross but it increases parse speed by ~15%
def _pre_frame(
    current_frame: Frame,
    event: Frame.Event,
    handlers: dict,
    *_,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    port = current_frame.ports[event.id.port]
    if not port:
        port = Frame.Port()
        current_frame.ports[event.id.port] = port
    if not event.id.is_follower:
        data = port.leader
    else:
        if port.follower is None:
            port.follower = Frame.Port.Data()
        data = port.follower
    data._pre = event.data
    return current_frame


def _post_frame(
    current_frame: Frame,
    event: Frame.Event,
    handlers,
    *_,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    port = current_frame.ports[event.id.port]
    if not port:
        port = Frame.Port()
        current_frame.ports[event.id.port] = port
    if not event.id.is_follower:
        data = port.leader
    else:
        if port.follower is None:
            port.follower = Frame.Port.Data()
        data = port.follower
    data._post = event.data
    return current_frame


def _item_frame(
    current_frame,
    event,
    handlers,
    *_,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    current_frame.items.append(Frame.Item._parse(event.data))
    return current_frame


def _start_frame(
    current_frame,
    event,
    handlers,
    *_,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    current_frame.start = Frame.Start._parse(event.data)
    return current_frame


def _end_frame(
    current_frame,
    event,
    handlers,
    *_,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    current_frame.end = Frame.End._parse(event.data)
    return current_frame


def _game_start(
    current_frame,
    event,
    handlers,
    skip_frames,
    total_size,
    bytes_read,
    payload_sizes,
    stream,
):
    handlers[Start](event)
    if skip_frames and total_size != 0:
        skip = total_size - bytes_read - payload_sizes[EventType.GAME_END.value] - 1
        stream.seek(skip, os.SEEK_CUR)
        bytes_read += skip
    return current_frame


def _game_end(
    current_frame,
    event,
    handlers,
    *_,
):
    handlers[End](event)
    return current_frame


# _parse_events jump table
BUILD_GAME_DISPATCH = {
    EventType.GAME_START: _game_start,
    EventType.FRAME_START: _start_frame,
    EventType.FRAME_PRE: _pre_frame,
    EventType.FRAME_POST: _post_frame,
    EventType.ITEM: _item_frame,
    EventType.FRAME_END: _end_frame,
    EventType.GAME_END: _game_end,
}


def _parse_events(stream, payload_sizes, total_size, handlers, skip_frames):
    current_frame = None
    bytes_read = 0
    event = None

    # `total_size` will be zero for in-progress replays
    while (total_size == 0 or bytes_read < total_size) and not isinstance(event, End):
        (b, event, event_code) = _parse_event(stream, payload_sizes)
        bytes_read += b
        #                                                        lmao
        current_frame = BUILD_GAME_DISPATCH.get(event_code, lambda *_: None)(
            current_frame,
            event,
            handlers,
            skip_frames,
            total_size,
            bytes_read,
            payload_sizes,
            stream,
        )

    if current_frame:
        current_frame._finalize()
        handlers[Frame](current_frame)


def _parse(stream, handlers, skip_frames):
    # For efficiency, don't send the whole file through ubjson.
    # Instead, assume `raw` is the first element. This is brittle and
    # ugly, but it's what the official parser does so it should be OK.
    expect_bytes(b"{U\x03raw[$U#l", stream)
    (length,) = unpack_int32(stream.read(4))

    (bytes_read, payload_sizes) = _parse_event_payloads(stream)
    if length != 0:
        length -= bytes_read

    _parse_events(stream, payload_sizes, length, handlers, skip_frames)

    expect_bytes(b"U\x08metadata", stream)

    json = ubjson.load(stream)
    handlers[dict](json)

    metadata = Metadata._parse(json)
    handlers[Metadata](metadata)

    expect_bytes(b"}", stream)


def _parse_try(source: BinaryIO, handlers, skip_frames, path=None):
    """Wrap parsing exceptions with additional information."""

    try:
        _parse(source, handlers, skip_frames)
    except Exception as exception:
        exception = exception if isinstance(exception, ParseError) else ParseError(str(exception))

        try:
            exception.filename = path  # type: ignore
        except AttributeError:
            pass

        try:
            # prefer provided position info, as it will be more accurate
            if not exception.pos and source.seekable():  # type: ignore
                exception.pos = source.tell()  # type: ignore
        # not all stream-like objects support `seekable` (e.g. HTTP requests)
        except AttributeError:
            pass

        raise exception


def _parse_open(source: os.PathLike, handlers, skip_frames) -> None:
    with mmap.mmap(os.open(source, os.O_RDONLY), 0, access=mmap.ACCESS_READ) as f:
        _parse_try(f, handlers, skip_frames, source)


def parse(
    source: BinaryIO | str | os.PathLike,
    handlers: dict[Any, Callable[..., None]],
    skip_frames: bool = False,
) -> None:
    """Parse a Slippi replay.
    :param input: replay file object or path
    :param handlers: dict of parse event keys to handler functions. Each event will be passed to the corresponding handler as it occurs.
    :param skip_frames: when true, skip past all frame data. Requires input to be seekable.
    """

    if isinstance(source, str):
        _parse_open(Path(source), handlers, skip_frames)
    elif isinstance(source, os.PathLike):
        _parse_open(source, handlers, skip_frames)
    else:
        _parse_try(source, handlers, skip_frames)
