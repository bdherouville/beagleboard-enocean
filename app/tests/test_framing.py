"""ESP3 framing — encode against §3.2 examples, then exercise the decoder."""

from vdsensor.esp3.framing import FrameDecoder, encode_frame
from vdsensor.esp3.packets import PacketType

# Worked examples from ESP3 v1.58 §3.2 (full frames, sync byte first)
CO_WR_RESET_FRAME = bytes.fromhex("55 00 01 00 05 70 02 0E".replace(" ", ""))
CO_RD_IDBASE_FRAME = bytes.fromhex("55 00 01 00 05 70 08 38".replace(" ", ""))
IDBASE_RESPONSE_FRAME = bytes.fromhex("55 00 05 00 02 CE 00 FF 80 00 00 DA".replace(" ", ""))
ERP1_VLD_FRAME = bytes.fromhex(
    "55 00 0F 07 01 2B"
    " D2 DD DD DD DD DD DD DD DD DD 00 80 35 C4 00"
    " 03 FF FF FF FF 4D 00"
    " 36".replace(" ", "")
)


def test_encode_co_wr_reset_matches_spec() -> None:
    out = encode_frame(PacketType.COMMON_COMMAND, b"\x02")
    assert out == CO_WR_RESET_FRAME


def test_encode_co_rd_idbase_matches_spec() -> None:
    out = encode_frame(PacketType.COMMON_COMMAND, b"\x08")
    assert out == CO_RD_IDBASE_FRAME


def test_encode_response_matches_spec() -> None:
    # Reproduce the §3.2.4 response: 5 data bytes, no opt.
    out = encode_frame(PacketType.RESPONSE, bytes.fromhex("00FF800000"))
    assert out == IDBASE_RESPONSE_FRAME


def test_decoder_decodes_each_spec_frame() -> None:
    dec = FrameDecoder()
    blob = CO_WR_RESET_FRAME + CO_RD_IDBASE_FRAME + IDBASE_RESPONSE_FRAME + ERP1_VLD_FRAME
    frames = list(dec.feed(blob))
    assert [f.packet_type for f in frames] == [
        PacketType.COMMON_COMMAND,
        PacketType.COMMON_COMMAND,
        PacketType.RESPONSE,
        PacketType.RADIO_ERP1,
    ]
    assert frames[3].opt.hex() == "03ffffffff4d00"


def test_decoder_handles_split_chunks() -> None:
    dec = FrameDecoder()
    out = []
    # feed one byte at a time to make sure the streaming path agrees with bulk
    for b in CO_RD_IDBASE_FRAME:
        out.extend(dec.feed(bytes((b,))))
    assert len(out) == 1
    assert out[0].packet_type == PacketType.COMMON_COMMAND
    assert out[0].data == b"\x08"


def test_decoder_resyncs_past_garbage() -> None:
    dec = FrameDecoder()
    junk = b"\xff\x00\x55\x55\xaa"               # second 0x55 is the real sync below
    frames = list(dec.feed(junk + CO_WR_RESET_FRAME))
    assert len(frames) == 1
    assert frames[0].data == b"\x02"


def test_decoder_resyncs_past_bad_header_crc() -> None:
    # Corrupt CRC8H — decoder should drop the bogus sync and find the next frame.
    bad = bytearray(CO_WR_RESET_FRAME)
    bad[5] ^= 0xFF                               # wreck CRC8H
    dec = FrameDecoder()
    frames = list(dec.feed(bytes(bad) + CO_RD_IDBASE_FRAME))
    assert len(frames) == 1
    assert frames[0].data == b"\x08"


def test_decoder_resyncs_past_bad_data_crc() -> None:
    bad = bytearray(CO_RD_IDBASE_FRAME)
    bad[-1] ^= 0xFF                              # wreck CRC8D
    dec = FrameDecoder()
    frames = list(dec.feed(bytes(bad) + CO_WR_RESET_FRAME))
    assert len(frames) == 1
    assert frames[0].data == b"\x02"


def test_encode_rejects_oversize_data() -> None:
    import pytest

    with pytest.raises(ValueError):
        encode_frame(PacketType.RADIO_ERP1, b"\x00" * (1 << 16))
