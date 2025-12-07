"""
Image utility functions.
"""
from PIL import Image, ImageOps

def crop_image(image_path):
    """
    Crop whitespace from the borders of an image.

    Args:
        image_path (str): The path to the image file.
    """
    try:
        image = Image.open(image_path).convert('L')  # Convert to grayscale
        inverted_image = ImageOps.invert(image)
        bbox = inverted_image.getbbox()
        if bbox:
            # Crop with a small margin
            cropped = image.crop((bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2))
            cropped.save(image_path)
    except Exception:
        # If cropping fails, do nothing
        pass


def create_collage(image_paths, output_path):
    """
    Create a collage from a list of images.

    Args:
        image_paths (list): A list of paths to the images.
        output_path (str): The path to save the collage to.
    """
    images = [Image.open(p) for p in image_paths]
    
    # Get the maximum width and total height of the collage
    widths, heights = zip(*(i.size for i in images))
    total_height = sum(heights)
    max_width = max(widths)
    
    # Create a new image with the calculated dimensions
    collage = Image.new('RGB', (max_width, total_height))
    
    # Paste the images into the collage
    y_offset = 0
    for image in images:
        collage.paste(image, (0, y_offset))
        y_offset += image.size[1]
        
    # Save the collage
    collage.save(output_path)
