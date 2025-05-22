from PIL import Image
from io import BytesIO

def invert_image(input_path):
    img = Image.open(input_path).convert("RGBA")
    inverted_img = Image.new("RGBA", img.size)

    for x in range(img.width):
        for y in range(img.height):
            r, g, b, a = img.getpixel((x, y))
            if (r, g, b) == (0, 0, 0):
                inverted_img.putpixel((x, y), (255, 255, 255, a))
            elif (r, g, b) == (255, 255, 255):
                inverted_img.putpixel((x, y), (0, 0, 0, a))
            else:
                inverted_img.putpixel((x, y), (r, g, b, a))

    img_byte_arr = BytesIO()
    inverted_img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr