import os
from PIL import Image

def generate_pwa_icons(input_image_path):
    # Ensure the static folder exists
    if not os.path.exists('static'):
        os.makedirs('static')

    try:
        # Open the base image you downloaded
        with Image.open(input_image_path) as img:
            # Convert to RGB in case it's RGBA and needs saving properly
            img = img.convert("RGBA")
            
            # Generate 512x512 icon
            icon_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
            icon_512.save('static/icon-512.png', format="PNG")
            print("✅ Successfully generated static/icon-512.png")
            
            # Generate 192x192 icon
            icon_192 = img.resize((192, 192), Image.Resampling.LANCZOS)
            icon_192.save('static/icon-192.png', format="PNG")
            print("✅ Successfully generated static/icon-192.png")
            
    except FileNotFoundError:
        print(f"Error: Could not find '{input_image_path}'. Make sure you saved the downloaded image with this name.")

# Run the function
generate_pwa_icons('base_icon.png')