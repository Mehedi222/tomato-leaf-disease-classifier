from io import BytesIO

from PIL import Image


def make_thumbnail(image: Image.Image, size: tuple = (64, 64)) -> bytes:
    thumb = image.copy()
    thumb.thumbnail(size)
    buffer = BytesIO()
    thumb.convert("RGB").save(buffer, format="JPEG")
    return buffer.getvalue()
