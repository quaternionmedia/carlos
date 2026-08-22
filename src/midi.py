"""MIDI in, and where it lands.

Carlos does not make sound, so a MIDI message here is not a note to play — it is
evidence that something in the rig did something, and the question this module
answers is *which device on screen was it*.

The seam is MIDI itself. It is a standard protocol with more independent
implementations than anyone can count, which is exactly what the QM seams record
asks of anything reaching a third party: a from-scratch implementation of the
protocol alone is enough to drive this, and nothing about Carlos needs to be
known on the other side.

Three pieces, all pure:

- `parse` turns bytes into a message. Real MIDI arrives as status + data bytes,
  and a build that only accepts a friendly JSON shape has not anticipated a MIDI
  signal, it has anticipated a description of one.
- `MidiBinding` says which messages belong to which device.
- `route` matches a message against the bindings and reports what lit up.

Nothing here opens a port. The browser's Web MIDI adapter and the HTTP endpoint
both call `route`, so the mapping behaves identically whichever side the message
came in on, and the tests need no hardware.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

# Channel voice messages, by the high nibble of the status byte.
NOTE_OFF = 0x80
NOTE_ON = 0x90
POLY_AFTERTOUCH = 0xA0
CONTROL_CHANGE = 0xB0
PROGRAM_CHANGE = 0xC0
CHANNEL_AFTERTOUCH = 0xD0
PITCH_BEND = 0xE0

# System real-time, whole-byte statuses. RAD drives playback from these, so the
# same three bytes mean the same thing in both projects.
CLOCK = 0xF8
START = 0xFA
CONTINUE = 0xFB
STOP = 0xFC

# RAD claims CC 20-23 for its speed axes (bpm, aps, div, quantize). A binding
# here may still *watch* them, but Carlos must not give them a second meaning:
# the seams record permits extending a shared vocabulary and forbids
# repurposing it.
RAD_RESERVED_CC = (20, 21, 22, 23)

MessageType = Literal[
    "note_on", "note_off", "aftertouch", "cc",
    "program", "pitchbend", "clock", "start", "stop", "continue",
]

SourceType = Literal["channel", "note", "cc", "program", "pitchbend", "transport"]


class MidiError(ValueError):
    """Bytes that are not a message, or a binding that cannot be read."""


class MidiMessage(BaseModel):
    """One parsed message."""

    model_config = ConfigDict(extra="forbid")

    type: MessageType
    channel: int | None = Field(default=None, ge=1, le=16)
    note: int | None = Field(default=None, ge=0, le=127)
    controller: int | None = Field(default=None, ge=0, le=127)
    # Velocity for notes, value for CC, 0..16383 for pitch bend.
    value: int | None = Field(default=None, ge=0, le=16383)

    @property
    def intensity(self) -> float:
        """0..1, for something on screen to be brighter or dimmer.

        A note-off is zero however it was spelled, which matters because the
        two spellings below are both real and a display that honoured only one
        would leave a device lit forever.
        """
        if self.type in ("note_off", "stop"):
            return 0.0
        if self.type == "pitchbend":
            return (self.value or 0) / 16383
        if self.value is None:
            return 1.0
        return self.value / 127


def parse(data: "bytes | list[int]") -> MidiMessage:
    """Turn raw MIDI bytes into a message, or say why they are not one."""
    payload = list(data)
    if not payload:
        raise MidiError("no bytes")

    status = payload[0]
    if status < 0x80:
        raise MidiError(f"0x{status:02X} is a data byte, not a status byte")

    if status >= 0xF8:
        transport = {CLOCK: "clock", START: "start", STOP: "stop", CONTINUE: "continue"}
        if status not in transport:
            raise MidiError(f"unsupported system message 0x{status:02X}")
        return MidiMessage(type=transport[status])

    if status >= 0xF0:
        raise MidiError(f"system common 0x{status:02X} is not mapped")

    kind = status & 0xF0
    channel = (status & 0x0F) + 1  # wire is 0-based; humans count from 1
    data1 = payload[1] if len(payload) > 1 else None
    data2 = payload[2] if len(payload) > 2 else None

    def need(*values):
        if any(v is None for v in values):
            raise MidiError(f"0x{status:02X} is missing its data bytes")

    if kind == NOTE_ON:
        need(data1, data2)
        # A note-on with velocity 0 is a note-off. Devices really send this,
        # and treating it as a note-on leaves the display stuck lit.
        return MidiMessage(
            type="note_on" if data2 else "note_off",
            channel=channel, note=data1, value=data2,
        )

    if kind == NOTE_OFF:
        need(data1, data2)
        return MidiMessage(type="note_off", channel=channel, note=data1, value=data2)

    if kind == POLY_AFTERTOUCH:
        need(data1, data2)
        return MidiMessage(type="aftertouch", channel=channel, note=data1, value=data2)

    if kind == CONTROL_CHANGE:
        need(data1, data2)
        return MidiMessage(type="cc", channel=channel, controller=data1, value=data2)

    if kind == PROGRAM_CHANGE:
        need(data1)
        return MidiMessage(type="program", channel=channel, value=data1)

    if kind == CHANNEL_AFTERTOUCH:
        need(data1)
        return MidiMessage(type="aftertouch", channel=channel, value=data1)

    if kind == PITCH_BEND:
        need(data1, data2)
        # 14-bit, LSB first.
        return MidiMessage(type="pitchbend", channel=channel, value=(data2 << 7) | data1)

    raise MidiError(f"unhandled status 0x{status:02X}")


def encode(message: "MidiMessage | dict") -> list[int]:
    """Turn a message into the bytes a device will receive, or refuse it.

    The inverse of `parse`, and the only way anything leaves this application.
    Every send goes through here, so a malformed message is refused with the
    reason rather than handed to a device that will report it as garbage - which
    is the failure this exists for: a device saying "malformed" tells you
    something was wrong and never which byte.

    The refusal is deliberately stricter than the wire. MIDI itself cannot
    express a note of 200 - the eighth bit marks a status byte - so a value out
    of range does not produce a bad note, it produces a byte the device reads as
    a new message and then starves for data. That is why a single bad value can
    desynchronise a stream rather than sound wrong.

    `parse(encode(m)) == m` for every message this can build, which is the
    property the tests assert rather than a table of expected bytes.
    """
    if not isinstance(message, MidiMessage):
        try:
            message = MidiMessage.model_validate(message)
        except ValidationError as error:
            # The same shaping `load_binding` does below: pydantic's own string
            # carries the model name, an echo of the input and a versioned docs
            # URL, none of which help somebody holding a message that will not
            # send.
            problems = "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: "
                f"{item['msg'].removeprefix('Value error, ')}"
                for item in error.errors()
            )
            raise MidiError(problems) from None

    kind = message.type

    transport = {"clock": CLOCK, "start": START, "stop": STOP, "continue": CONTINUE}
    if kind in transport:
        return [transport[kind]]

    if message.channel is None:
        raise MidiError(f"a {kind} message needs a channel")
    status_channel = message.channel - 1

    def seven(name: str, value: "int | None", default: "int | None" = None) -> int:
        if value is None:
            if default is None:
                raise MidiError(f"a {kind} message needs {name}")
            value = default
        if not 0 <= value <= 127:
            raise MidiError(
                f"{name} is {value}; MIDI carries 0-127 in a data byte, and "
                f"anything above it sets the bit that marks a status byte"
            )
        return value

    if kind == "note_on":
        return [NOTE_ON | status_channel,
                seven("a note", message.note),
                seven("a velocity", message.value, 64)]

    if kind == "note_off":
        # Sent as a real note-off rather than note-on-with-zero. Both are legal
        # and devices differ on which they prefer; the explicit one is never
        # mistaken for a note that failed to sound.
        return [NOTE_OFF | status_channel,
                seven("a note", message.note),
                seven("a velocity", message.value, 0)]

    if kind == "cc":
        return [CONTROL_CHANGE | status_channel,
                seven("a controller", message.controller),
                seven("a value", message.value, 0)]

    if kind == "program":
        return [PROGRAM_CHANGE | status_channel, seven("a program", message.value)]

    if kind == "aftertouch":
        # Polyphonic when it names a note, channel-wide when it does not.
        if message.note is not None:
            return [POLY_AFTERTOUCH | status_channel,
                    seven("a note", message.note),
                    seven("a pressure", message.value, 0)]
        return [CHANNEL_AFTERTOUCH | status_channel, seven("a pressure", message.value)]

    if kind == "pitchbend":
        value = message.value if message.value is not None else 8192
        if not 0 <= value <= 16383:
            raise MidiError(
                f"a pitch bend is {value}; it is 14 bits, so 0-16383, "
                f"sent as two 7-bit bytes"
            )
        return [PITCH_BEND | status_channel, value & 0x7F, (value >> 7) & 0x7F]

    raise MidiError(f"nothing knows how to send a {kind} message")


class MidiSource(BaseModel):
    """Which messages a binding is interested in.

    A field left out is a wildcard, so `{type: channel, channel: 10}` is "any
    message on channel 10" and `{type: note, note: 36}` is "kick, on any
    channel". Omitting the channel is deliberate rather than lazy: a rig where
    one machine is moved to another channel should not need its bindings
    rewritten.
    """

    model_config = ConfigDict(extra="forbid")

    type: SourceType
    channel: int | None = Field(default=None, ge=1, le=16)
    note: int | None = Field(default=None, ge=0, le=127)
    controller: int | None = Field(default=None, ge=0, le=127)

    @model_validator(mode="after")
    def _selector_matches_type(self) -> "MidiSource":
        if self.type == "note" and self.controller is not None:
            raise ValueError("a note source cannot select a controller")
        if self.type == "cc" and self.note is not None:
            raise ValueError("a cc source cannot select a note")
        return self


class MidiBinding(BaseModel):
    """One rule: messages like *this* belong to *that* device.

    `parameter` and `jack` are both optional and are about what the device does
    when it is hit — turn a knob, light a socket. A binding with neither still
    lights the device, which is the common case and the reason neither is
    required.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source: MidiSource
    module: str = Field(min_length=1)
    parameter: str | None = None
    jack: str | None = None
    label: str = ""


class Activity(BaseModel):
    """What one message did to the picture."""

    model_config = ConfigDict(extra="forbid")

    binding: str
    module: str
    parameter: str | None = None
    jack: str | None = None
    intensity: float
    message: MidiMessage


def matches(source: MidiSource, message: MidiMessage) -> bool:
    """Whether a message is one this source asked for."""
    if source.channel is not None and message.channel != source.channel:
        return False

    if source.type == "channel":
        return message.channel is not None

    if source.type == "note":
        if message.type not in ("note_on", "note_off", "aftertouch"):
            return False
        return source.note is None or message.note == source.note

    if source.type == "cc":
        if message.type != "cc":
            return False
        return source.controller is None or message.controller == source.controller

    if source.type == "program":
        return message.type == "program"

    if source.type == "pitchbend":
        return message.type == "pitchbend"

    if source.type == "transport":
        return message.type in ("clock", "start", "stop", "continue")

    return False


def route(bindings: "list[MidiBinding]", message: MidiMessage) -> "list[Activity]":
    """Every device this message lights, in binding order.

    All matching bindings fire, rather than the most specific one winning. One
    message genuinely can concern two devices — a clock lights everything
    following it — and picking a single winner would hide that. A rig where two
    bindings fight over one parameter is a mapping to fix, not a tie for this
    function to break silently.
    """
    return [
        Activity(
            binding=binding.id,
            module=binding.module,
            parameter=binding.parameter,
            jack=binding.jack,
            intensity=message.intensity,
            message=message,
        )
        for binding in bindings
        if matches(binding.source, message)
    ]


def load_binding(document: object) -> MidiBinding:
    if not isinstance(document, dict):
        raise MidiError(f"a binding is an object, not {type(document).__name__}")
    try:
        return MidiBinding.model_validate(document)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in d['loc'])}: "
            f"{d['msg'].removeprefix('Value error, ')}"
            for d in exc.errors()
        )
        raise MidiError(problems) from exc
