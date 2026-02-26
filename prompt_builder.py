"""
Prompt Builder: Converts blog post content into AI image generation prompts.
Matches the BPC branding style from the reference images.
"""

import random

from scraper import BlogPost


# Diverse therapist appearances to ensure each image has a unique person
THERAPIST_APPEARANCES = [
    "a young Southeast Asian female therapist with long black hair tied in a ponytail",
    "a middle-aged Caucasian male therapist with short brown hair and a trimmed beard",
    "a young Caucasian female therapist with shoulder-length curly hair",
    "an older East Asian male therapist with short gray hair and glasses",
    "a young Southeast Asian female therapist with dark hair in a bun",
    "a middle-aged Southeast Asian male therapist with short dark hair and a mustache",
    "a young Caucasian female therapist with short blonde hair",
    "an older Caucasian male therapist with a shaved head and reading glasses",
    "a young Southeast Asian male therapist with medium-length black hair",
    "a middle-aged Southeast Asian female therapist with auburn hair pulled back",
    "a young Southeast Asian female therapist with long brown hair in a braid",
]


# BPC branding style description based on reference images
BPC_STYLE = """Professional photorealistic image in a clean, bright physiotherapy clinic.
The medical professional is wearing dark navy blue scrubs with the BPC logo on the 
upper chest of the shirt — use the EXACT logo design shown in the reference images. 
The logo should appear only once, on the therapist's shirt. The clinic has white 
walls, modern minimalist furniture, and warm natural lighting. The image should look 
like a high-quality medical stock photo with a warm, inviting atmosphere.

Full people should be shown naturally, including faces.
IMPORTANT: The therapist's face and appearance MUST match the appearance description 
provided in the prompt. Do NOT copy the face from the reference images — only use 
the reference images for the BPC logo design and scrub style.
Do not include any text overlays or watermarks in the image."""


# Keywords that map to specific body parts/treatments
BODY_PART_KEYWORDS = {
    'knee': 'knee',
    'acl': 'knee',
    'ankle': 'ankle',
    'foot': 'foot',
    'plantar': 'foot',
    'hip': 'hip',
    'shoulder': 'shoulder',
    'rotator cuff': 'shoulder',
    'neck': 'neck',
    'cervical': 'neck',
    'back': 'lower back',
    'spine': 'back',
    'spinal': 'back',
    'lumbar': 'lower back',
    'lower back': 'lower back',
    'wrist': 'wrist',
    'carpal tunnel': 'wrist',
    'hand': 'hand',
    'finger': 'hand',
    'trigger finger': 'hand',
    'arthritis': 'hand',
    'rheumatoid': 'hand',
    'elbow': 'elbow',
    'tennis elbow': 'elbow',
    'golfer': 'elbow',
    'scoliosis': 'back',
    'sciatica': 'lower back',
    'headache': 'head',
    'migraine': 'head',
    'jaw': 'jaw',
    'tmj': 'jaw',
    'chest': 'chest',
    'rib': 'chest',
    'hamstring': 'leg',
    'quadriceps': 'leg',
    'calf': 'leg',
    'shin': 'leg',
    'thigh': 'leg',
    'arm': 'arm',
    'bicep': 'arm',
    'tricep': 'arm',
    'posture': 'full body posture',
    'ergonomic': 'full body posture',
    'office syndrome': 'neck and shoulders',
    'sports': 'athletic injury',
    'running': 'leg',
    'golf': 'elbow',
    'swim': 'shoulder',
    'breastfeed': 'chest and upper back',
    'pregnancy': 'full body',
    'pediatric': 'child treatment',
    'elderly': 'elderly patient',
    'stroke': 'neurological rehabilitation',
    'concussion': 'head',
    'vertigo': 'head',
    'balance': 'full body balance',
    'fall': 'full body',
}


# Treatment-specific scene descriptions
TREATMENT_SCENES = {
    'knee': 'A physiotherapist treating a patient\'s knee. The patient is lying on a white treatment table while the therapist gently manipulates their knee joint.',
    'ankle': 'A physiotherapist examining and treating a patient\'s ankle. The patient is seated on a white treatment table while the therapist carefully works on the ankle area.',
    'foot': 'A physiotherapist treating a patient\'s foot. The patient is seated while the therapist examines and applies treatment to the foot area.',
    'hip': 'A physiotherapist treating a patient\'s hip. The patient is lying on a white treatment table while the therapist works on the hip joint area.',
    'shoulder': 'A physiotherapist treating a patient\'s shoulder. The patient is seated while the therapist carefully works on the shoulder joint and surrounding muscles.',
    'neck': 'A physiotherapist gently treating a patient\'s neck. The patient is lying face-up on a white treatment table while the therapist supports and mobilizes the cervical spine area. A subtle red glow highlights the neck area indicating the point of pain.',
    'lower back': 'A physiotherapist treating a patient\'s lower back. The patient is lying face-down on a white treatment table while the therapist applies manual therapy to the lumbar region.',
    'back': 'A physiotherapist treating a patient\'s back. The patient is lying on a white treatment table while the therapist performs manual therapy on the spine area.',
    'wrist': 'A close-up shot of a medical professional examining a patient\'s wrist. The background shows a modern medical office.',
    'hand': 'A close-up shot of a physiotherapist\'s hands examining and treating a patient\'s hand and fingers. The focus is tightly on the hands — no faces are visible. The therapist is gently manipulating the affected joints in a modern clinic.',
    'elbow': 'A close-up shot of a physiotherapist\'s hands treating a patient\'s elbow and forearm area. The focus is on the hands and elbow joint — no faces are visible. The therapist is applying manual therapy to the elbow in a modern clinic.',
    'head': 'A physiotherapist performing a gentle head and temple treatment. The patient is lying on a white treatment table while the therapist applies careful manual therapy.',
    'jaw': 'A physiotherapist treating a patient\'s jaw area (TMJ). The patient is lying face-up while the therapist applies gentle pressure around the jaw joint.',
    'chest': 'A physiotherapist treating a patient\'s chest and ribcage area. The patient is seated while the therapist works on the thoracic region.',
    'leg': 'A physiotherapist treating a patient\'s leg muscles. The patient is lying on a white treatment table while the therapist stretches and works on the leg.',
    'arm': 'A physiotherapist treating a patient\'s arm. The patient is seated while the therapist works on the arm muscles and joints.',
    'full body posture': 'A physiotherapist assessing a patient\'s posture. The patient is standing while the therapist evaluates their alignment from the side.',
    'neck and shoulders': 'A physiotherapist treating a patient\'s neck and shoulder area. The patient is seated at a desk-like setup while the therapist works on the upper trapezius and neck.',
    'athletic injury': 'A physiotherapist treating a sports athlete. The patient in athletic wear is on a treatment table while the therapist applies treatment.',
    'chest and upper back': 'A physiotherapist treating a patient\'s upper back and chest area. The patient is seated while the therapist works on the thoracic region.',
    'full body': 'A physiotherapist performing a full body assessment. The patient is standing while the therapist evaluates their overall condition.',
    'child treatment': 'A physiotherapist gently treating a young patient. The child is on a treatment table while the therapist applies gentle therapeutic techniques.',
    'elderly patient': 'A physiotherapist helping an elderly patient. The older patient is seated while the therapist provides gentle treatment and support.',
    'neurological rehabilitation': 'A physiotherapist assisting a patient with neurological rehabilitation exercises. The patient is performing guided movements under the therapist\'s supervision.',
    'full body balance': 'A physiotherapist helping a patient with balance exercises. The patient is standing on one leg while the therapist provides support and guidance.',
}

DEFAULT_SCENE = 'A physiotherapist treating a patient in a bright clinic setting. The patient is on a white treatment table while the therapist provides professional care.'


def identify_body_part(title: str, content: str) -> str:
    """Identify the primary body part/condition from post title and content."""
    combined = (title + ' ' + content[:500]).lower()
    
    # Check for multi-word keywords first (more specific)
    for keyword, body_part in sorted(BODY_PART_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in combined:
            return body_part
    
    return 'full body'


def build_prompt(post: BlogPost) -> str:
    """
    Generate an image generation prompt based on blog post content.
    
    Args:
        post: A BlogPost object with title and content
        
    Returns:
        A detailed prompt string for image generation
    """
    body_part = identify_body_part(post.title, post.content)
    scene = TREATMENT_SCENES.get(body_part, DEFAULT_SCENE)
    
    # Pick a random therapist appearance for this image
    appearance = random.choice(THERAPIST_APPEARANCES)
    
    # Replace the generic "A physiotherapist" with the specific appearance
    personalized_scene = scene.replace(
        'A physiotherapist', f'{appearance.capitalize()},', 1
    ).replace(
        'a physiotherapist', appearance, 1
    )
    
    prompt = f"""{personalized_scene}

{BPC_STYLE}

The therapist in this image should be {appearance}.
The image specifically relates to: {post.title}. 
The focus should be on the {body_part} area being treated.
Do not include any text overlays or watermarks in the image."""

    return prompt


def build_prompt_summary(post: BlogPost) -> dict:
    """
    Return a summary of what the prompt will generate (for dry-run mode).
    
    Returns:
        Dict with body_part, scene_description, and full prompt
    """
    body_part = identify_body_part(post.title, post.content)
    scene = TREATMENT_SCENES.get(body_part, DEFAULT_SCENE)
    
    return {
        'body_part': body_part,
        'scene': scene[:100] + '...' if len(scene) > 100 else scene,
        'prompt': build_prompt(post),
    }


if __name__ == '__main__':
    # Test with a sample post
    sample = BlogPost(
        number=1,
        post_id=1,
        title="ACL Rehab: A Complete Physical Therapy Guide",
        slug="acl-rehab-guide",
        content="An injury to your Anterior Cruciate Ligament (ACL) can be a painful experience...",
        content_html="",
        date="2025-10-30",
        status="publish",
        category="Blog",
        url="https://bpcphysio.com/blog/acl-rehab-guide/",
    )
    
    result = build_prompt_summary(sample)
    print(f"Body part: {result['body_part']}")
    print(f"Scene: {result['scene']}")
    print(f"\nFull prompt:\n{result['prompt']}")
