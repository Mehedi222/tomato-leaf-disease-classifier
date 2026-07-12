from io import BytesIO

from PIL import Image

from imaging import make_thumbnail


def test_make_thumbnail_returns_jpeg_bytes_within_bounds():
    image = Image.new("RGB", (224, 224), color=(255, 0, 0))
    thumb_bytes = make_thumbnail(image, size=(64, 64))

    assert isinstance(thumb_bytes, bytes)
    assert len(thumb_bytes) > 0

    result = Image.open(BytesIO(thumb_bytes))
    assert result.format == "JPEG"
    assert result.width <= 64
    assert result.height <= 64
