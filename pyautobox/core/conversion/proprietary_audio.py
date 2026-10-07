"""Local decoders for encrypted music containers.

Algorithm details are adapted from the MIT-licensed KGG-Decryptor project.
Only keys already present on the user's computer are used; no online key lookup
or account session extraction is performed.
"""

from __future__ import annotations

import base64
import hashlib
import math
import os
import sqlite3
import struct
import tempfile
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from pyautobox.exceptions import ConversionFailedError, InvalidFileError

KGM_MAGIC = bytes.fromhex("7CD532EB86027F4BA8AFA68E0FFF9914")
VPR_MAGIC = bytes.fromhex("0528BC96E9E45A4391AABDD07AF53631")
KWM_MAGIC = (b"yeelion-kuwo-tme", b"yeelion-kuwo\0\0\0\0")
KWM_KEY = b"MoOtOiTvINGwd2E6n0E1i7L5t2IoOoNk"
NCM_MAGIC = b"CTENFDAM"
NCM_CORE_KEY = b"hzHRAmso5kInbaxW"
PAGE_SIZE = 0x400
SQLITE_HEADER = b"SQLite format 3\0"
MASTER_KEY = bytes.fromhex("1D613145B247BF7F3D189672144FE4BF")
TEA_DELTA = 0x9E3779B9
U32_MASK = 0xFFFFFFFF

ENCRYPTED_AUDIO_FORMATS = frozenset(
    {
        "kgg",
        "kgm",
        "kgma",
        "vpr",
        "ncm",
        "kwm",
        "qmc0",
        "qmc2",
        "qmc3",
        "qmc4",
        "qmc6",
        "qmc8",
        "qmcflac",
        "qmcogg",
        "tkm",
        "mflac",
        "mflac0",
        "mflac1",
        "mgg",
        "mgg0",
        "mgg1",
        "mggl",
    }
)


def detect_kugou_database(explicit: str | Path | None = None) -> Path | None:
    """Find the local KuGou key database without scanning unrelated folders."""
    candidates: list[Path] = []
    configured = explicit or os.getenv("PYAUTOBOX_KUGOU_DB")
    if configured:
        candidates.append(Path(configured).expanduser())
    for variable in ("APPDATA", "LOCALAPPDATA"):
        if base := os.getenv(variable):
            candidates.extend(
                [Path(base) / "KuGou8" / "KGMusicV3.db", Path(base) / "KuGou" / "KGMusicV3.db"]
            )
    home = Path.home()
    candidates.extend(
        [
            home / "AppData" / "Roaming" / "KuGou8" / "KGMusicV3.db",
            home / "AppData" / "Roaming" / "KuGou" / "KGMusicV3.db",
            home / "AppData" / "Local" / "KuGou8" / "KGMusicV3.db",
            home / "AppData" / "Local" / "KuGou" / "KGMusicV3.db",
        ]
    )
    candidates.extend([Path.cwd() / "KGMusicV3.db", Path.cwd() / "tools" / "KGMusicV3.db"])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def decrypt_audio(path: Path, *, database: str | Path | None = None) -> tuple[bytes, str]:
    """Decrypt one supported container and return raw audio plus its real format."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise InvalidFileError(f"无法读取音频文件：{path}") from exc
    suffix = path.suffix.lower().lstrip(".")
    try:
        if suffix in {"kgg", "kgm", "kgma", "vpr"}:
            return _decrypt_kugou(data, suffix, database)
        if suffix == "ncm":
            return _decrypt_ncm(data)
        if suffix == "kwm":
            return _decrypt_kwm(data)
        if suffix in ENCRYPTED_AUDIO_FORMATS:
            return _decrypt_qmc(data)
    except ConversionFailedError:
        raise
    except (IndexError, ValueError, struct.error) as exc:
        raise ConversionFailedError(f"{path.name} 的加密容器已损坏或版本不受支持。") from exc
    raise InvalidFileError(f"暂不支持 .{suffix} 加密音频。")


def _decrypt_kugou(data: bytes, suffix: str, database: str | Path | None) -> tuple[bytes, str]:
    if len(data) < 0x48 or data[:16] not in {KGM_MAGIC, VPR_MAGIC}:
        raise ConversionFailedError(f"{suffix.upper()} 文件头无效。")
    audio_offset = _u32le(data, 0x10)
    version = _u32le(data, 0x14)
    if not 0 < audio_offset <= len(data):
        raise ConversionFailedError("酷狗音频偏移超出文件范围。")
    audio = bytearray(data[audio_offset:])
    if version == 3:
        if _u32le(data, 0x18) != 1:
            raise ConversionFailedError("暂不支持该 KGM v3 加密槽位。")
        _decrypt_kgm_v3(data, audio)
    elif version == 5:
        hash_len = _u32le(data, 0x44)
        hash_end = 0x48 + hash_len
        if not hash_len or hash_end > len(data):
            raise ConversionFailedError("酷狗 audio hash 无效。")
        audio_hash = data[0x48:hash_end].rstrip(b"\0").decode("utf-8", errors="strict")
        db_path = detect_kugou_database(database)
        if db_path is None:
            raise ConversionFailedError(
                "未找到 KGMusicV3.db。请先在酷狗客户端播放一次目标歌曲，或设置 PYAUTOBOX_KUGOU_DB。"
            )
        keys = _load_kugou_keys(db_path)
        ekey = keys.get(audio_hash)
        if not ekey:
            raise ConversionFailedError(
                "酷狗数据库中没有这首歌的本机密钥，请先在客户端播放后重试。"
            )
        _QmcCipher(_derive_ekey(ekey)).decrypt(audio)
    else:
        raise ConversionFailedError(f"暂不支持 KGM/KGG 加密版本 {version}。")
    return bytes(audio), _sniff_audio(audio)


def _decrypt_kgm_v3(header: bytes, audio: bytearray) -> None:
    slot = _kugou_md5(bytes((0x6C, 0x2C, 0x2F, 0x27)))
    file_key = _kugou_md5(header[0x2C:0x3C]) + b"k"
    for index, value in enumerate(audio):
        value ^= file_key[index % len(file_key)]
        value ^= (value << 4) & 0xFF
        value ^= slot[index % len(slot)]
        value ^= index ^ (index >> 8) ^ (index >> 16) ^ (index >> 24)
        audio[index] = value & 0xFF


def _kugou_md5(data: bytes) -> bytes:
    digest = hashlib.md5(data).digest()  # noqa: S324 - format compatibility, not security
    return b"".join(digest[index : index + 2] for index in range(14, -1, -2))


def _decrypt_database(data: bytes) -> bytes:
    if data.startswith(SQLITE_HEADER):
        return data
    if len(data) < PAGE_SIZE or len(data) % PAGE_SIZE:
        raise ConversionFailedError("KGMusicV3.db 大小无效。")
    output = bytearray(data)
    o10 = _u32le(output, 0x10)
    o14 = _u32le(output, 0x14)
    v6 = (((o10 & 0xFF) << 8) | ((o10 & 0xFF00) << 16)) & U32_MASK
    if not (o14 == 0x20204000 and v6 - 0x200 <= 0xFE00 and ((v6 - 1) & v6) == 0):
        raise ConversionFailedError("KGMusicV3.db 版本或页头不受支持。")
    output[0x10:0x18] = output[0x08:0x10]
    output[0x10:PAGE_SIZE] = _aes_cbc(bytes(output[0x10:PAGE_SIZE]), _page_key(1), _page_iv(1))
    output[:16] = SQLITE_HEADER
    for page in range(2, len(output) // PAGE_SIZE + 1):
        start = (page - 1) * PAGE_SIZE
        output[start : start + PAGE_SIZE] = _aes_cbc(
            bytes(output[start : start + PAGE_SIZE]), _page_key(page), _page_iv(page)
        )
    return bytes(output)


def _page_key(page: int) -> bytes:
    return hashlib.md5(MASTER_KEY + struct.pack("<I", page) + b"sAlT").digest()  # noqa: S324


def _page_iv(page: int) -> bytes:
    seed = page + 1
    raw = bytearray()
    for _ in range(4):
        left = (seed * 0x9EF4) & U32_MASK
        right = ((seed // 0xCE26) * 0x7FFFFF07) & U32_MASK
        seed = (left - right) & U32_MASK
        if seed & 0x80000000:
            seed = (seed + 0x7FFFFF07) & U32_MASK
        raw.extend(struct.pack("<I", seed))
    return hashlib.md5(raw).digest()  # noqa: S324


def _aes_cbc(data: bytes, key: bytes, iv: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return decryptor.update(data) + decryptor.finalize()


@lru_cache(maxsize=4)
def _cached_kugou_keys(path: str, size: int, modified_ns: int) -> dict[str, str]:
    del size, modified_ns
    plain = _decrypt_database(Path(path).read_bytes())
    descriptor, temporary = tempfile.mkstemp(prefix="pyautobox-kugou-", suffix=".db")
    os.close(descriptor)
    temp_path = Path(temporary)
    try:
        temp_path.write_bytes(plain)
        connection = sqlite3.connect(temp_path)
        try:
            rows = connection.execute(
                "SELECT EncryptionKeyId, EncryptionKey FROM ShareFileItems "
                "WHERE EncryptionKey IS NOT NULL AND EncryptionKey != ''"
            )
            return {str(key): str(value) for key, value in rows if key and value}
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ConversionFailedError("无法读取酷狗本机密钥数据库。") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _load_kugou_keys(path: Path) -> dict[str, str]:
    try:
        stat = path.stat()
        return _cached_kugou_keys(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    except OSError as exc:
        raise ConversionFailedError("无法读取 KGMusicV3.db。") from exc


def _derive_ekey(ekey: str) -> bytes:
    try:
        raw = base64.b64decode(ekey, validate=True)
        prefix = b"QQMusic EncV2,Key:"
        if raw.startswith(prefix):
            raw = _derive_key_v2(raw[len(prefix) :])
        return _derive_key_v1(raw)
    except (ValueError, TypeError) as exc:
        raise ConversionFailedError("歌曲密钥格式无效。") from exc


def _derive_key_v1(raw: bytes) -> bytes:
    if len(raw) < 16:
        raise ConversionFailedError("歌曲密钥长度不足。")
    simple = _simple_key(106, 8)
    tea_key = bytes(value for pair in zip(simple, raw[:8], strict=True) for value in pair)
    return raw[:8] + _tencent_tea_decrypt(raw[8:], tea_key)


def _derive_key_v2(raw: bytes) -> bytes:
    key1 = bytes.fromhex("3338365A4A592140232A24255E262928")
    key2 = bytes.fromhex("2A2A232128232425265E6131635A2C54")
    first = _tencent_tea_decrypt(raw, key1)
    second = _tencent_tea_decrypt(first, key2)
    try:
        return base64.b64decode(second, validate=True)
    except ValueError as exc:
        raise ConversionFailedError("二代歌曲密钥无效。") from exc


def _simple_key(salt: int, length: int) -> bytes:
    values = []
    for index in range(length):
        value = int(abs(math.tan(salt + index * 0.1)) * 100)
        values.append(min(255, value))
    return bytes(values)


def _tea_block(block: bytes, key: bytes) -> bytearray:
    v0, v1 = struct.unpack(">2I", block)
    words = struct.unpack(">4I", key)
    total = (TEA_DELTA * 16) & U32_MASK
    for _ in range(16):
        term = (((v0 << 4) & U32_MASK) + words[2]) & U32_MASK
        term ^= (v0 + total) & U32_MASK
        term ^= ((v0 >> 5) + words[3]) & U32_MASK
        v1 = (v1 - term) & U32_MASK
        term = (((v1 << 4) & U32_MASK) + words[0]) & U32_MASK
        term ^= (v1 + total) & U32_MASK
        term ^= ((v1 >> 5) + words[1]) & U32_MASK
        v0 = (v0 - term) & U32_MASK
        total = (total - TEA_DELTA) & U32_MASK
    return bytearray(struct.pack(">2I", v0, v1))


def _tencent_tea_decrypt(data: bytes, key: bytes) -> bytes:
    if len(data) < 16 or len(data) % 8:
        raise ConversionFailedError("TEA 密钥数据长度无效。")
    dest = _tea_block(data[:8], key)
    padding = dest[0] & 7
    output_length = len(data) - 1 - padding - 2 - 7
    if output_length < 0:
        raise ConversionFailedError("TEA 填充无效。")
    iv_previous = bytearray(8)
    iv_current = bytearray(data[:8])
    input_position = 8
    dest_index = 1 + padding

    def next_block() -> None:
        nonlocal dest, iv_previous, iv_current, input_position, dest_index
        if input_position + 8 > len(data):
            raise ConversionFailedError("TEA 数据被截断。")
        iv_previous, iv_current = iv_current, bytearray(data[input_position : input_position + 8])
        for index in range(8):
            dest[index] ^= iv_current[index]
        dest = _tea_block(dest, key)
        input_position += 8
        dest_index = 0

    skipped = 0
    while skipped < 2:
        if dest_index < 8:
            dest_index += 1
            skipped += 1
        else:
            next_block()
    output = bytearray()
    while len(output) < output_length:
        if dest_index < 8:
            output.append(dest[dest_index] ^ iv_previous[dest_index])
            dest_index += 1
        else:
            next_block()
    return bytes(output)


class _QmcCipher:
    def __init__(self, key: bytes | None = None, *, static: bool = False) -> None:
        if static:
            self.kind = "static"
            self.key = b""
        elif not key:
            raise ConversionFailedError("无法创建音频解密器。")
        else:
            self.kind = "rc4" if len(key) > 300 else "map"
            self.key = key
        if self.kind == "rc4":
            self._init_rc4()

    def decrypt(self, data: bytearray, offset: int = 0) -> None:
        if self.kind == "static":
            for index in range(len(data)):
                at = offset + index
                period = at % 0x7FFF if at > 0x7FFF else at
                data[index] ^= _QMC_STATIC_BOX[(period * period + 27) & 0xFF]
        elif self.kind == "map":
            for index in range(len(data)):
                data[index] ^= self._map_mask(offset + index)
        else:
            self._rc4_decrypt(data, offset)

    def _map_mask(self, offset: int) -> int:
        offset = offset % 0x7FFF if offset > 0x7FFF else offset
        index = (offset * offset + 71214) % len(self.key)
        value = self.key[index]
        rotate = ((index & 7) + 4) % 8
        return ((value << rotate) | (value >> rotate)) & 0xFF if rotate else value

    def _init_rc4(self) -> None:
        size = len(self.key)
        self.box = bytearray(index & 0xFF for index in range(size))
        cursor = 0
        for index in range(size):
            cursor = (cursor + self.box[index] + self.key[index % size]) % size
            self.box[index], self.box[cursor] = self.box[cursor], self.box[index]
        self.hash = 1
        for value in self.key:
            if not value:
                continue
            following = (self.hash * value) & U32_MASK
            if not following or following <= self.hash:
                break
            self.hash = following

    def _segment_skip(self, identifier: int) -> int:
        seed = self.key[identifier % len(self.key)]
        denominator = (identifier + 1) * seed
        if not denominator:
            return 0
        return int(self.hash / denominator * 100) % len(self.key)

    def _rc4_decrypt(self, data: bytearray, offset: int) -> None:
        position = 0
        remaining = len(data)
        if offset < 128:
            size = min(remaining, 128 - offset)
            for index in range(size):
                data[position + index] ^= self.key[self._segment_skip(offset + index)]
            offset += size
            position += size
            remaining -= size
        if remaining and offset % 5120:
            size = min(remaining, 5120 - offset % 5120)
            self._rc4_segment(data, position, size, offset)
            offset += size
            position += size
            remaining -= size
        while remaining > 5120:
            self._rc4_segment(data, position, 5120, offset)
            offset += 5120
            position += 5120
            remaining -= 5120
        if remaining:
            self._rc4_segment(data, position, remaining, offset)

    def _rc4_segment(self, data: bytearray, start: int, size: int, offset: int) -> None:
        box = self.box.copy()
        j = k = 0
        skip = offset % 5120 + self._segment_skip(offset // 5120)
        for index in range(-skip, size):
            j = (j + 1) % len(self.key)
            k = (box[j] + k) % len(self.key)
            box[j], box[k] = box[k], box[j]
            if index >= 0:
                data[start + index] ^= box[(box[j] + box[k]) % len(self.key)]


def _decrypt_kwm(data: bytes) -> tuple[bytes, str]:
    if len(data) < 0x400 or not data.startswith(KWM_MAGIC):
        raise ConversionFailedError("KWM 文件头无效。")
    key_text = str(struct.unpack_from("<Q", data, 0x18)[0]).encode()
    expanded = bytes(key_text[index % len(key_text)] for index in range(32))
    mask = bytes(left ^ right for left, right in zip(KWM_KEY, expanded, strict=True))
    audio = bytearray(data[0x400:])
    for index in range(len(audio)):
        audio[index] ^= mask[index & 0x1F]
    return bytes(audio), _sniff_audio(audio)


def _decrypt_ncm(data: bytes) -> tuple[bytes, str]:
    if len(data) < 14 or not data.startswith(NCM_MAGIC):
        raise ConversionFailedError("NCM 文件头无效。")
    offset = 10
    key_length = _u32le(data, offset)
    offset += 4
    key_blob = bytes(value ^ 0x64 for value in data[offset : offset + key_length])
    offset += key_length
    key_plain = _pkcs7_unpad(_aes_ecb(key_blob, NCM_CORE_KEY))
    if len(key_plain) <= 17:
        raise ConversionFailedError("NCM 音频密钥无效。")
    key_box = _ncm_key_box(key_plain[17:])
    metadata_length = _u32le(data, offset)
    offset += 4 + metadata_length + 5
    frame_length = _u32le(data, offset)
    audio_start = offset + 8 + frame_length
    if audio_start > len(data):
        raise ConversionFailedError("NCM 封面帧不完整。")
    audio = bytearray(data[audio_start:])
    for index in range(len(audio)):
        audio[index] ^= key_box[index & 0xFF]
    return bytes(audio), _sniff_audio(audio)


def _aes_ecb(data: bytes, key: bytes) -> bytes:
    if not data or len(data) % 16:
        raise ConversionFailedError("AES 数据长度无效。")
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return decryptor.update(data) + decryptor.finalize()


def _pkcs7_unpad(data: bytes) -> bytes:
    padding = data[-1] if data else 0
    if not 0 < padding <= 16 or data[-padding:] != bytes((padding,)) * padding:
        raise ConversionFailedError("加密音频填充无效。")
    return data[:-padding]


def _ncm_key_box(key: bytes) -> bytes:
    box = bytearray(range(256))
    cursor = 0
    for index in range(256):
        cursor = (cursor + box[index] + key[index % len(key)]) & 0xFF
        box[index], box[cursor] = box[cursor], box[index]
    output = bytearray(256)
    for index in range(256):
        first = box[(index + 1) & 0xFF]
        second = box[(index + 1 + first) & 0xFF]
        output[index] = box[(first + second) & 0xFF]
    return bytes(output)


def _decrypt_qmc(data: bytes) -> tuple[bytes, str]:
    if len(data) < 4:
        raise ConversionFailedError("QMC 文件太短。")
    if len(data) >= 16 and data.endswith(b"musicex\0"):
        raise ConversionFailedError("新版 MusicEx 文件需要在线会话密钥，当前本地模式不支持。")
    tail = data[-4:]
    if tail == b"STag":
        raise ConversionFailedError("STag 文件不包含可离线使用的密钥。")
    if tail == b"QTag":
        key_length = struct.unpack(">I", data[-8:-4])[0]
        audio_length = len(data) - 8 - key_length
        raw = data[audio_length:-8]
        if b"," not in raw:
            raise ConversionFailedError("QTag 密钥不完整。")
        cipher = _QmcCipher(_derive_ekey(raw.split(b",", 1)[0].decode("utf-8")))
    else:
        key_length = struct.unpack("<I", tail)[0]
        if 0 < key_length <= 0xFFFF and key_length + 4 <= len(data):
            audio_length = len(data) - 4 - key_length
            ekey = data[audio_length:-4].rstrip(b"\0").decode("utf-8")
            cipher = _QmcCipher(_derive_ekey(ekey))
        else:
            audio_length = len(data)
            cipher = _QmcCipher(static=True)
    audio = bytearray(data[:audio_length])
    cipher.decrypt(audio)
    return bytes(audio), _sniff_audio(audio)


def _sniff_audio(data: bytes | bytearray) -> str:
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        return "mp3"
    if data.startswith(b"fLaC"):
        return "flac"
    if data.startswith(b"OggS"):
        return "ogg"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE":
        return "wav"
    if data.startswith((b"ADIF", b"\xff\xf1", b"\xff\xf9")):
        return "aac"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "m4a"
    if data.startswith(bytes.fromhex("3026B275")):
        return "wma"
    if data.startswith(b"FRM8"):
        return "dff"
    raise ConversionFailedError("解密后无法识别真实音频格式。")


def _u32le(data: bytes | bytearray, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ConversionFailedError("加密音频文件头被截断。")
    return struct.unpack_from("<I", data, offset)[0]


_QMC_STATIC_BOX = bytes.fromhex(
    "77483273DEF2C0C895EC30B251C3E1A09EE69DCFFA7F14D1CEB8DCC34A6793D6"
    "28C29170CA8DA2A4F00861907E6FA2E0EBAE3EB667C792F491B5F66C5E8440F7"
    "F31B027FD5AB418928F425CC5211AD4368A6418B84B5FF2C924A26D8476A7C95"
    "61CCE6CBBB3F47588975C375A1D9AFCC087317DCAA9AA21641D8A206C68BFC66"
    "349FCF1823A00A74E72B277092E9AF37E68CA7BC62659CC208C988B3F343AC74"
    "2C0FD4AFA1C30164954E489FF43578957A39D66AA06D40E84FA8EF111DF31B3F"
    "3F07DD6F5B193019FBEF0E37F00ECD1649FE5347131ABDA4F14019600EED6809"
    "065F4DCF3D1AFE2077E4D9DAF9A42B761C71DB00BCFD0C6CA547F7F600794A11"
)
