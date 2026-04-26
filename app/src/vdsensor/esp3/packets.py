"""ESP3 enums — packet types, return codes, event codes, command codes.

References are to ESP3 v1.58 (file EnOceanSerialProtocol3-1.pdf at the repo root).
"""

from __future__ import annotations

from enum import IntEnum

SYNC_BYTE = 0x55                                # §3.4.1
HEADER_LENGTH = 4                               # u16DataLength + u8OptLen + u8Type


class PacketType(IntEnum):
    """ESP3 packet type field (§1.8 / per-section structures)."""

    RADIO_ERP1 = 0x01                           # §2.1
    RESPONSE = 0x02                             # §2.2
    RADIO_SUB_TEL = 0x03                        # §2.3
    EVENT = 0x04                                # §2.4
    COMMON_COMMAND = 0x05                       # §2.5
    SMART_ACK_COMMAND = 0x06                    # §2.6
    REMOTE_MAN_COMMAND = 0x07                   # §2.7
    RADIO_MESSAGE = 0x09                        # §2.8
    RADIO_ERP2 = 0x0A                           # §2.9
    COMMAND_ACCEPTED = 0x0C                     # §2.10
    RADIO_802_15_4 = 0x10                       # §2.11
    CONFIG_2_4_GHZ = 0x11                       # §2.12


class ReturnCode(IntEnum):
    """RESPONSE return codes (§2.2.2)."""

    RET_OK = 0x00
    RET_ERROR = 0x01
    RET_NOT_SUPPORTED = 0x02
    RET_WRONG_PARAM = 0x03
    RET_OPERATION_DENIED = 0x04
    RET_LOCK_SET = 0x05
    RET_BUFFER_TO_SMALL = 0x06
    RET_NO_FREE_BUFFER = 0x07


class EventCode(IntEnum):
    """EVENT (0x04) event codes (§2.4.2)."""

    SA_RECLAIM_NOT_SUCCESSFUL = 0x01            # §2.4.3
    SA_CONFIRM_LEARN = 0x02                     # §2.4.4
    SA_LEARN_ACK = 0x03                         # §2.4.5
    CO_READY = 0x04                             # §2.4.6
    CO_EVENT_SECUREDEVICES = 0x05               # §2.4.7
    CO_DUTYCYCLE_LIMIT = 0x06                   # §2.4.8
    CO_TRANSMIT_FAILED = 0x07                   # §2.4.9
    CO_TX_DONE = 0x08                           # §2.4.10
    CO_LRN_MODE_DISABLED = 0x09                 # §2.4.11


class CommonCommand(IntEnum):
    """COMMON_COMMAND (0x05) command codes (§2.5.2)."""

    CO_WR_SLEEP = 0x01                          # §2.5.3
    CO_WR_RESET = 0x02                          # §2.5.4
    CO_RD_VERSION = 0x03                        # §2.5.5
    CO_RD_SYS_LOG = 0x04                        # §2.5.6
    CO_WR_IDBASE = 0x07                         # §2.5.9
    CO_RD_IDBASE = 0x08                         # §2.5.10
    CO_WR_LEARNMODE = 0x17                      # §2.5.25
    CO_RD_LEARNMODE = 0x18                      # §2.5.26


# RORG bytes (radio choice byte) — only the ones we decode in v1
class Rorg(IntEnum):
    RPS = 0xF6                                  # §2.1 / EEP F6
    ONE_BS = 0xD5                               # §2.1 / EEP D5
    FOUR_BS = 0xA5                              # §2.1 / EEP A5
    VLD = 0xD2                                  # §2.1 / EEP D2
    UTE = 0xD4                                  # §2.1 / EEP D4
    ADT = 0xA6                                  # §2.1 (addressed destination wrapper)
    SIGNAL = 0xD0                               # §2.1
    MSC = 0xD1                                  # §2.1
