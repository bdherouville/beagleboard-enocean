"""COMMON_COMMAND builders and response parsers."""

from vdsensor.esp3 import common_command as cc
from vdsensor.esp3.framing import FrameDecoder
from vdsensor.esp3.packets import CommonCommand, PacketType, ReturnCode
from vdsensor.esp3.response import parse_response


def test_cmd_co_wr_reset_matches_spec() -> None:
    # ESP3 §3.2.3 — exact bytes from the worked example.
    assert cc.cmd_co_wr_reset() == bytes.fromhex("550001000570020E")


def test_cmd_co_rd_idbase_matches_spec() -> None:
    # ESP3 §3.2.4 — exact bytes from the worked example.
    assert cc.cmd_co_rd_idbase() == bytes.fromhex("5500010005700838")


def test_cmd_co_rd_version_decodes_correctly() -> None:
    raw = cc.cmd_co_rd_version()
    frame = next(iter(FrameDecoder().feed(raw)))
    assert frame.packet_type == PacketType.COMMON_COMMAND
    assert frame.data == bytes((CommonCommand.CO_RD_VERSION,))


def test_cmd_co_wr_learnmode_layout() -> None:
    raw = cc.cmd_co_wr_learnmode(enable=True, timeout_ms=60_000, channel=0xFF)
    frame = next(iter(FrameDecoder().feed(raw)))
    assert frame.packet_type == PacketType.COMMON_COMMAND
    # data: cmd(0x17) | enable(0x01) | timeout BE(60000=0xEA60)
    assert frame.data == bytes((CommonCommand.CO_WR_LEARNMODE, 0x01, 0x00, 0x00, 0xEA, 0x60))
    assert frame.opt == bytes((0xFF,))


def test_parse_idbase_response_from_spec_example() -> None:
    # §3.2.4 response: 5 data bytes (00 FF800000), no opt → remaining_writes default 0xFF
    raw = bytes.fromhex("5500050002CE00FF800000DA")
    frame = next(iter(FrameDecoder().feed(raw)))
    resp = parse_response(frame)
    info = cc.parse_idbase_response(resp)
    assert resp.return_code == ReturnCode.RET_OK
    assert info.base_id == 0xFF800000
    assert info.remaining_writes == 0xFF


def test_parse_idbase_response_with_remaining_writes_in_opt() -> None:
    # Same response but with the (newer) opt byte = 0x05 remaining writes.
    from vdsensor.esp3.framing import encode_frame

    raw = encode_frame(
        PacketType.RESPONSE,
        bytes.fromhex("00FF800000"),
        opt=bytes((0x05,)),
    )
    frame = next(iter(FrameDecoder().feed(raw)))
    info = cc.parse_idbase_response(parse_response(frame))
    assert info.remaining_writes == 0x05


def test_parse_version_response_round_trip() -> None:
    from vdsensor.esp3.framing import encode_frame

    payload = (
        bytes((ReturnCode.RET_OK,))
        + bytes((2, 6, 0, 5))                    # app version 2.6.0.5
        + bytes((1, 22, 0, 0))                   # api version 1.22.0.0
        + (0x01234567).to_bytes(4, "big")        # EURID
        + (0x00000001).to_bytes(4, "big")        # device version
        + b"GATEWAYCTRLR\x00\x00\x00\x00"        # 16-byte ASCII description
    )
    raw = encode_frame(PacketType.RESPONSE, payload)
    frame = next(iter(FrameDecoder().feed(raw)))
    info = cc.parse_version_response(parse_response(frame))
    assert info.app_version == (2, 6, 0, 5)
    assert info.api_version == (1, 22, 0, 0)
    assert info.chip_id == 0x01234567
    assert info.chip_version == 0x00000001
    assert info.description == "GATEWAYCTRLR"
