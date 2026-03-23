from PIL import Image
import io

def optimize_image(image_bytes: bytes, max_size=(800, 800)) -> bytes:
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80)
            return buffer.getvalue()
    except Exception:
        return image_bytes