"""
Image Generator: Uses Google Gemini API (Nano Banana) to generate images.
"""

import os
import time
import base64
from pathlib import Path
from PIL import Image
from google import genai
from google.genai import types


def get_client() -> genai.Client:
    """Create and return a Gemini API client."""
    api_key = os.environ.get('GOOGLE_AI_API_KEY')
    if not api_key:
        raise ValueError(
            "GOOGLE_AI_API_KEY not found in environment variables.\n"
            "Set it in your .env file or export it:\n"
            "  export GOOGLE_AI_API_KEY='your-key-here'"
        )
    return genai.Client(api_key=api_key)


def load_reference_images(ref_dir: str = 'reference_images') -> list[types.Part]:
    """Load BPC reference images to guide style consistency."""
    ref_path = Path(ref_dir)
    parts = []
    
    if not ref_path.exists():
        return parts
    
    for img_file in sorted(ref_path.iterdir()):
        if img_file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
            with open(img_file, 'rb') as f:
                img_data = f.read()
            
            mime_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg', 
                '.png': 'image/png',
                '.webp': 'image/webp',
            }.get(img_file.suffix.lower(), 'image/jpeg')
            
            parts.append(types.Part.from_bytes(data=img_data, mime_type=mime_type))
    
    return parts


def generate_image(
    prompt: str,
    output_path: str,
    reference_images: list[types.Part] | None = None,
    model: str = "gemini-2.5-flash-image",
    max_retries: int = 3,
    retry_delay: float = 35.0,
) -> bool:
    """
    Generate an image using the Gemini API and save it to disk.
    
    Args:
        prompt: The image generation prompt
        output_path: Where to save the generated image
        reference_images: Optional list of reference image Parts for style guidance
        model: Gemini model to use
        max_retries: Maximum number of retry attempts
        retry_delay: Seconds to wait between retries
        
    Returns:
        True if image was generated successfully, False otherwise
    """
    client = get_client()
    
    # Build the content parts
    contents = []
    
    # Add reference images if provided
    if reference_images:
        contents.append("Here are reference images showing the BPC branding style. "
                       "The generated image MUST use the EXACT same BPC logo as shown "
                       "on the therapist's shirt in these reference images. Match the "
                       "dark navy scrubs and overall visual style:")
        contents.extend(reference_images)
    
    contents.append(prompt)
    
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=['image', 'text'],
                ),
            )
            
            # Extract image from response
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith('image/'):
                        # Save the image
                        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(part.inline_data.data)
                        # Resize to exactly 1600x921 without stretching:
                        # 1. Shrink if larger than target
                        # 2. Paste centered onto a 1600x921 canvas
                        target_w, target_h = 1600, 921
                        img = Image.open(output_path)
                        img.thumbnail((target_w, target_h), Image.LANCZOS)

                        # Sample background color from image edges
                        edge_pixels = []
                        w, h = img.size
                        for x in range(w):
                            edge_pixels.append(img.getpixel((x, 0)))
                            edge_pixels.append(img.getpixel((x, h - 1)))
                        for y in range(h):
                            edge_pixels.append(img.getpixel((0, y)))
                            edge_pixels.append(img.getpixel((w - 1, y)))
                        # Average the edge colors for a seamless background
                        n = len(edge_pixels)
                        channels = len(edge_pixels[0]) if isinstance(edge_pixels[0], tuple) else 1
                        if channels >= 3:
                            avg_color = tuple(
                                sum(p[c] for p in edge_pixels) // n
                                for c in range(min(channels, 3))
                            )
                        else:
                            avg_color = (128, 128, 128)

                        canvas = Image.new('RGB', (target_w, target_h), avg_color)
                        paste_x = (target_w - img.width) // 2
                        paste_y = (target_h - img.height) // 2
                        canvas.paste(img, (paste_x, paste_y))
                        canvas.save(output_path)
                        return True
            
            print(f"  ⚠ No image in response (attempt {attempt}/{max_retries})")
            
        except Exception as e:
            print(f"  ⚠ Error (attempt {attempt}/{max_retries}): {e}")
        
        if attempt < max_retries:
            print(f"  Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
    
    return False


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    
    print("Testing Gemini image generation...")
    
    test_prompt = """A physiotherapist treating a patient's knee in a clean, bright clinic.
The therapist wears dark navy scrubs with a BPC logo on the chest.
Professional, photorealistic, warm lighting."""
    
    success = generate_image(test_prompt, 'output/test_image.png')
    
    if success:
        print("✅ Test image saved to output/test_image.png")
    else:
        print("❌ Failed to generate test image")
