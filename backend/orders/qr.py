import base64

import qrcode
import qrcode.image.svg


def qr_svg_data_uri(payload: str) -> str:
    image = qrcode.make(payload, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    svg = image.to_string()
    return "data:image/svg+xml;base64," + base64.b64encode(svg).decode()
