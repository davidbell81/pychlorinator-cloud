"""Timer models, parsers, and write builders for Halo cloud timer payloads.

Wire format confirmed from decompiled app source (TimeConfigCharacteristic3):

  cmd 0x0193 body (13 bytes, Pack=1):
    [0]    TimerType   0=Pump, 1=Lighting
    [1]    TimerIndex  slot 0-3
    [2]    TimerMode   0=Winter, 1=Summer
    [3]    TimerEnabled 0/1
    [4-5]  Enables     uint16 LE equipment bitmask (EnablesValues)
    [6]    StartMode   0=Normal
    [7]    StartHour
    [8]    StartMin
    [9]    StopMode    0=Normal
    [10]   StopHour
    [11]   StopMin
    [12]   Parameter   speed: 0=Low 1=Medium 2=High 3=AI

  Write command: 0x03 + LE16(0x0193) + struct_bytes, padded to 20 bytes total.
"""

from __future__ import annotations

import struct
from dataclasses import asdict, dataclass
from typing import Any

TIMER_SETUP_SEASONS = {
    0: "Winter",
    1: "Summer",
}

TIMER_STATE_SEASONS = {
    1: "Winter",
    2: "Summer",
}

# EnablesValues flags (uint16 bitmask in TimeConfigCharacteristic3.Enables)
ENABLES_POOL_SPA = 0x0001
ENABLES_FILTER_PUMP = 0x0002
ENABLES_HEATER = 0x0004
ENABLES_OUTLET1 = 0x0008
ENABLES_OUTLET2 = 0x0010
ENABLES_OUTLET3 = 0x0020
ENABLES_OUTLET4 = 0x0040
ENABLES_VALVE1 = 0x0080
ENABLES_VALVE2 = 0x0100
ENABLES_VALVE3 = 0x0200
ENABLES_VALVE4 = 0x0400
ENABLES_RELAY1 = 0x0800
ENABLES_RELAY2 = 0x1000

ENABLES_LABELS: dict[int, str] = {
    ENABLES_POOL_SPA: "PoolSpa",
    ENABLES_FILTER_PUMP: "FilterPump",
    ENABLES_HEATER: "Heater",
    ENABLES_OUTLET1: "Outlet1",
    ENABLES_OUTLET2: "Outlet2",
    ENABLES_OUTLET3: "Outlet3",
    ENABLES_OUTLET4: "Outlet4",
    ENABLES_VALVE1: "Valve1",
    ENABLES_VALVE2: "Valve2",
    ENABLES_VALVE3: "Valve3",
    ENABLES_VALVE4: "Valve4",
    ENABLES_RELAY1: "Relay1",
    ENABLES_RELAY2: "Relay2",
}

TIMER_TYPE_PUMP = 0
TIMER_TYPE_LIGHTING = 1

TIMER_MODE_WINTER = 0
TIMER_MODE_SUMMER = 1

TIMER_START_MODE_NORMAL = 0
TIMER_STOP_MODE_NORMAL = 0

TIMER_SPEED_LEVELS = {
    0: "Low",
    1: "Medium",
    2: "High",
    3: "AI",
}

_TIMER_CONFIG_STRUCT = struct.Struct("<BBBBHBBBBBBB")


@dataclass(slots=True, frozen=True)
class TimerCapabilities:
    """Decoded timer capability counts."""

    equipment_timer_slots: int
    lighting_timer_slots: int
    winter_summer_available: bool = False
    dusk_dawn_available: bool = False
    flags: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = "timer_capabilities"
        data["flags"] = list(self.flags)
        return data


@dataclass(slots=True, frozen=True)
class TimerSetup:
    """Decoded timer setup/profile selection state (cmd 0x0191)."""

    season_byte: int
    season: str
    raw_bytes: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = "timer_setup"
        data["raw_bytes"] = list(self.raw_bytes)
        return data


@dataclass(slots=True, frozen=True)
class TimerState:
    """Decoded timer state/profile pointer (cmd 0x0192)."""

    profile_index: int
    season: str | None = None
    raw_bytes: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = "timer_state"
        data["raw_bytes"] = list(self.raw_bytes)
        return data


@dataclass(slots=True, frozen=True)
class TimerConfig:
    """Decoded per-slot timer record (cmd 0x0193)."""

    timer_type: int
    slot_index: int
    timer_mode: int
    active: bool
    enables: int
    start_mode: int = 0
    start_hour: int = 0
    start_minute: int = 0
    stop_mode: int = 0
    stop_hour: int = 0
    stop_minute: int = 0
    speed_code: int = 0
    season: str | None = None
    start_time: str | None = None
    stop_time: str | None = None
    duration_minutes: int | None = None
    overnight: bool = False
    speed: str | None = None
    equipment_enabled: tuple[str, ...] = ()
    raw_bytes: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = "timer_config"
        data["equipment_enabled"] = list(self.equipment_enabled)
        data["raw_bytes"] = list(self.raw_bytes)
        return data


def _format_time(hour: int, minute: int) -> str | None:
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def _duration_minutes(
    start_hour: int,
    start_minute: int,
    stop_hour: int,
    stop_minute: int,
) -> tuple[int | None, bool]:
    start_time = _format_time(start_hour, start_minute)
    stop_time = _format_time(stop_hour, stop_minute)
    if start_time is None or stop_time is None:
        return None, False
    start_total = start_hour * 60 + start_minute
    stop_total = stop_hour * 60 + stop_minute
    overnight = stop_total < start_total
    if overnight:
        stop_total += 24 * 60
    return stop_total - start_total, overnight


def parse_timer_capabilities(data: bytes) -> dict[str, Any]:
    """Parse cmd 0x0190 timer capabilities (TimerCapabilitiesCharacteristic)."""
    if len(data) < 2:
        return {"type": "timer_capabilities", "raw": data.hex(), "error": "too short"}

    winter_summer = bool(data[2]) if len(data) > 2 else False
    dusk_dawn = bool(data[3]) if len(data) > 3 else False
    return TimerCapabilities(
        equipment_timer_slots=data[0],
        lighting_timer_slots=data[1],
        winter_summer_available=winter_summer,
        dusk_dawn_available=dusk_dawn,
        flags=tuple(data[4:]),
    ).to_dict()


def parse_timer_setup(data: bytes) -> dict[str, Any]:
    """Parse cmd 0x0191 timer setup/profile state."""
    if len(data) < 3:
        return {"type": "timer_setup", "raw": data.hex(), "error": "too short"}

    season_byte = data[2]
    return TimerSetup(
        season_byte=season_byte,
        season=TIMER_SETUP_SEASONS.get(season_byte, f"Unknown({season_byte})"),
        raw_bytes=tuple(data),
    ).to_dict()


def parse_timer_state(data: bytes) -> dict[str, Any]:
    """Parse cmd 0x0192 timer profile pointer/state."""
    if len(data) < 1:
        return {"type": "timer_state", "raw": data.hex(), "error": "too short"}

    profile_index = data[0]
    return TimerState(
        profile_index=profile_index,
        season=TIMER_STATE_SEASONS.get(profile_index),
        raw_bytes=tuple(data),
    ).to_dict()


def parse_timer_config(data: bytes) -> dict[str, Any]:
    """Parse cmd 0x0193 per-slot timer config (TimeConfigCharacteristic3)."""
    if len(data) < _TIMER_CONFIG_STRUCT.size:
        return {"type": "timer_config", "raw": data.hex(), "error": "too short"}

    (
        timer_type,
        slot_index,
        timer_mode,
        timer_enabled,
        enables,
        start_mode,
        start_hour,
        start_min,
        stop_mode,
        stop_hour,
        stop_min,
        speed_code,
    ) = _TIMER_CONFIG_STRUCT.unpack_from(data)

    equipment_enabled = tuple(
        label for bit, label in ENABLES_LABELS.items() if enables & bit
    )
    duration, overnight = _duration_minutes(start_hour, start_min, stop_hour, stop_min)

    return TimerConfig(
        timer_type=timer_type,
        slot_index=slot_index,
        timer_mode=timer_mode,
        active=bool(timer_enabled),
        enables=enables,
        start_mode=start_mode,
        start_hour=start_hour,
        start_minute=start_min,
        stop_mode=stop_mode,
        stop_hour=stop_hour,
        stop_minute=stop_min,
        speed_code=speed_code,
        season=TIMER_SETUP_SEASONS.get(timer_mode),
        start_time=_format_time(start_hour, start_min),
        stop_time=_format_time(stop_hour, stop_min),
        duration_minutes=duration,
        overnight=overnight,
        speed=TIMER_SPEED_LEVELS.get(speed_code, f"Unknown({speed_code})"),
        equipment_enabled=equipment_enabled,
        raw_bytes=tuple(data),
    ).to_dict()


def build_timer_config_payload(
    slot_index: int,
    *,
    enabled: bool,
    enables: int,
    start_hour: int,
    start_minute: int,
    stop_hour: int,
    stop_minute: int,
    speed_code: int,
    timer_mode: int = TIMER_MODE_WINTER,
    start_mode: int = TIMER_START_MODE_NORMAL,
    stop_mode: int = TIMER_STOP_MODE_NORMAL,
    timer_type: int = TIMER_TYPE_PUMP,
) -> bytes:
    """Build the 13-byte TimeConfigCharacteristic3 payload for a cmd 0x0193 write."""
    return _TIMER_CONFIG_STRUCT.pack(
        timer_type,
        slot_index,
        timer_mode,
        int(enabled),
        enables,
        start_mode,
        start_hour,
        start_minute,
        stop_mode,
        stop_hour,
        stop_minute,
        speed_code,
    )
