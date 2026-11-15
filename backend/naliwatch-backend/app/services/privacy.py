import io

import cv2
import numpy as np
from PIL import Image


def normalize_photo(data: bytes, max_side: int = 1600) -> bytes:
    """Re-encode as JPEG: strips EXIF (incl. GPS) and shrinks big photos."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue()


def blur_faces(data: bytes) -> tuple[bytes, int]:
    """Returns (image, faces found). If detection is unavailable it returns (data, 0); the caller then drops
    the photo whenever the classifier said a face is visible."""
    try:
        return _blur(data)
    except Exception:
        return data, 0


def _blur(data: bytes) -> tuple[bytes, int]:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return data, 0
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(30, 30))
    for (x, y, w, h) in faces:
        img[y:y + h, x:x + w] = cv2.GaussianBlur(img[y:y + h, x:x + w], (0, 0), max(w, h) / 4)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return (buf.tobytes() if ok else data), len(faces)
