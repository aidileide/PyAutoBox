from __future__ import annotations

import struct
from pathlib import Path

from pyautobox.core.conversion.music import MusicConverter
from pyautobox.core.conversion.proprietary_audio import decrypt_audio


def test_kwm_is_decrypted_without_external_key(tmp_path: Path) -> None:
    plain = b"OggS" + b"test-audio" * 8
    key_text = str(12345678).encode()
    expanded = bytes(key_text[index % len(key_text)] for index in range(32))
    predefined = b"MoOtOiTvINGwd2E6n0E1i7L5t2IoOoNk"
    mask = bytes(left ^ right for left, right in zip(predefined, expanded, strict=True))
    encrypted = bytes(value ^ mask[index & 0x1F] for index, value in enumerate(plain))
    header = bytearray(0x400)
    header[:16] = b"yeelion-kuwo-tme"
    struct.pack_into("<Q", header, 0x18, 12345678)
    source = tmp_path / "sample.kwm"
    source.write_bytes(header + encrypted)

    decoded, audio_format = decrypt_audio(source)

    assert audio_format == "ogg"
    assert decoded == plain


def test_music_converter_keeps_native_mp3_after_decryption(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.kgg"
    source.write_bytes(b"encrypted")
    output = tmp_path / "sample.mp3"
    payload = b"ID3" + b"audio"
    monkeypatch.setattr(
        "pyautobox.core.conversion.music.decrypt_audio",
        lambda *_args, **_kwargs: (payload, "mp3"),
    )

    result = MusicConverter().convert(source, output)

    assert result == output
    assert output.read_bytes() == payload
