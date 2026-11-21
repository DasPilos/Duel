"""Минимальный WebSocket по RFC 6455 на стандартной библиотеке: рукопожатие, текстовые кадры, ping/pong, закрытие.

Ограничения: только текстовые кадры без фрагментации (то, что нужно игре), максимальный размер кадра ограничен.
"""

import base64
import hashlib
import struct

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_PAYLOAD = 1024 * 1024
OP_TEXT = 0x1
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA


class WebSocketError(Exception):
    pass


def accept_key(client_key):
    """Заголовок Sec-WebSocket-Accept для ключа клиента."""
    digest = hashlib.sha1((client_key.strip() + GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def encode_frame(opcode, payload):
    """Кадр от сервера: без маски (серверные кадры не маскируются)."""
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header += struct.pack("!H", length)
    else:
        header.append(127)
        header += struct.pack("!Q", length)
    return bytes(header) + payload


def _read_exact(stream, count):
    data = b""
    while len(data) < count:
        chunk = stream.read(count - len(data))
        if not chunk:
            raise WebSocketError("соединение закрыто")
        data += chunk
    return data


def read_frame(stream):
    """Читает один кадр: возвращает (opcode, payload). Кадры клиента маскируются."""
    head = _read_exact(stream, 2)
    if not head[0] & 0x80:
        raise WebSocketError("фрагментированные кадры не поддерживаются")
    opcode = head[0] & 0x0F
    masked = head[1] & 0x80
    length = head[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", _read_exact(stream, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _read_exact(stream, 8))[0]
    if length > MAX_PAYLOAD:
        raise WebSocketError("слишком большой кадр")
    mask = _read_exact(stream, 4) if masked else b""
    data = _read_exact(stream, length)
    if masked:
        data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
    return opcode, data
