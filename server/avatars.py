"""Аватары аккаунтов: PNG 150×150 пикселей, проверяется по заголовку без внешних библиотек."""

import base64
import binascii
import struct

AVATAR_SIZE = 150
MAX_AVATAR_BYTES = 128 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ALLOWED_COLOR_TYPES = (2, 6)  # RGB и RGBA


def validate_avatar_png(data):
    if len(data) > MAX_AVATAR_BYTES:
        raise ValueError("Аватар слишком большой: не больше 128 КБ")
    if len(data) < 26 or not data.startswith(_PNG_SIGNATURE) or data[12:16] != b"IHDR":
        raise ValueError("Аватар должен быть PNG-файлом")
    width, height = struct.unpack(">II", data[16:24])
    bit_depth, color_type = data[24], data[25]
    if width != AVATAR_SIZE or height != AVATAR_SIZE:
        raise ValueError(f"Аватар должен быть {AVATAR_SIZE}×{AVATAR_SIZE} пикселей")
    if bit_depth != 8 or color_type not in _ALLOWED_COLOR_TYPES:
        raise ValueError("Аватар должен быть PNG с 8 битами на канал (RGB или RGBA)")
    return data


def decode_avatar(encoded):
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("Не переданы данные аватара")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Данные аватара повреждены") from error
    return validate_avatar_png(data)


def encode_avatar(png):
    return base64.b64encode(png).decode("ascii")
