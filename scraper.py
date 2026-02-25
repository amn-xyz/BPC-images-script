"""
Scraper module: Parses WordPress XML export to extract English blog posts.
"""

import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass, field
from html import unescape
from typing import Optional


@dataclass
class BlogPost:
    """Represents a single blog post extracted from the XML export."""
    number: int  # 1-indexed position in the ordered list
    post_id: int
    title: str
    slug: str
    content: str  # Plain text content (HTML stripped)
    content_html: str  # Original HTML content
    date: str
    status: str  # publish, draft, etc.
    category: str
    url: str
    meta_description: str = ""


# WordPress XML namespaces
NAMESPACES = {
    'wp': 'http://wordpress.org/export/1.2/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
}


def strip_html(html_content: str) -> str:
    """Remove HTML tags, WordPress comments, and clean up whitespace."""
    # Remove WordPress block comments like <!-- wp:paragraph -->
    text = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode HTML entities
    text = unescape(text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def is_english(text: str) -> bool:
    """Check if text is primarily English (not Thai)."""
    if not text:
        return True
    # Thai Unicode range: \u0E00-\u0E7F
    thai_chars = len(re.findall(r'[\u0E00-\u0E7F]', text))
    ascii_chars = len(re.findall(r'[a-zA-Z]', text))
    # If more Thai chars than ASCII, it's Thai
    return ascii_chars >= thai_chars


def parse_xml_export(xml_path: str, english_only: bool = True, published_only: bool = True) -> list[BlogPost]:
    """
    Parse a WordPress XML export file and return a list of BlogPost objects.
    
    Args:
        xml_path: Path to the WordPress XML export file
        english_only: If True, only return English-language posts
        published_only: If True, only return published posts (not drafts)
    
    Returns:
        List of BlogPost objects, ordered by date (oldest first)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    channel = root.find('channel')
    
    posts = []
    
    for item in channel.findall('item'):
        # Only process posts (not pages, attachments, etc.)
        post_type = item.find('wp:post_type', NAMESPACES)
        if post_type is None or post_type.text != 'post':
            continue
        
        # Get status
        status_el = item.find('wp:status', NAMESPACES)
        status = status_el.text if status_el is not None else 'unknown'
        
        if published_only and status != 'publish':
            continue
        
        # Get title
        title_el = item.find('title')
        title = title_el.text if title_el is not None and title_el.text else ''
        
        # Filter by language
        if english_only and not is_english(title):
            continue
        
        # Check URL for /th/ path (Thai translations)
        link_el = item.find('link')
        url = link_el.text if link_el is not None and link_el.text else ''
        if english_only and '/th/' in url:
            continue
        
        # Get content
        content_el = item.find('content:encoded', NAMESPACES)
        content_html = content_el.text if content_el is not None and content_el.text else ''
        content_text = strip_html(content_html)
        
        # Skip posts with no content
        if not content_text.strip():
            continue
        
        # Get slug
        slug_el = item.find('wp:post_name', NAMESPACES)
        slug = slug_el.text if slug_el is not None and slug_el.text else ''
        
        # Get post ID
        post_id_el = item.find('wp:post_id', NAMESPACES)
        post_id = int(post_id_el.text) if post_id_el is not None else 0
        
        # Get date
        date_el = item.find('wp:post_date', NAMESPACES)
        date = date_el.text if date_el is not None and date_el.text else ''
        
        # Get category
        categories = []
        for cat in item.findall('category'):
            domain = cat.get('domain', '')
            if domain == 'category' and cat.text:
                categories.append(cat.text)
        category = ', '.join(categories) if categories else 'Uncategorized'
        
        # Get meta description from Yoast
        meta_desc = ''
        for meta in item.findall('wp:postmeta', NAMESPACES):
            key_el = meta.find('wp:meta_key', NAMESPACES)
            val_el = meta.find('wp:meta_value', NAMESPACES)
            if key_el is not None and key_el.text == '_yoast_wpseo_metadesc':
                meta_desc = val_el.text if val_el is not None and val_el.text else ''
                break
        
        posts.append(BlogPost(
            number=0,  # Will be set after sorting
            post_id=post_id,
            title=title,
            slug=slug,
            content=content_text,
            content_html=content_html,
            date=date,
            status=status,
            category=category,
            url=url,
            meta_description=meta_desc,
        ))
    
    # Sort: English first, then Thai; within each group, newest first
    posts.sort(key=lambda p: (0 if is_english(p.title) else 1, p.date), reverse=False)
    # Reverse within groups: English newest-first, then Thai newest-first
    english = [p for p in posts if is_english(p.title)]
    thai = [p for p in posts if not is_english(p.title)]
    english.sort(key=lambda p: p.date, reverse=True)
    thai.sort(key=lambda p: p.date, reverse=True)
    posts = english + thai
    
    # Assign sequential numbers
    for i, post in enumerate(posts, start=1):
        post.number = i
    
    return posts


if __name__ == '__main__':
    import sys
    import os
    
    # Find the XML file
    xml_files = [f for f in os.listdir('.') if f.endswith('.xml')]
    if not xml_files:
        print("No XML file found in current directory!")
        sys.exit(1)
    
    xml_path = xml_files[0]
    print(f"Parsing: {xml_path}\n")
    
    posts = parse_xml_export(xml_path)
    
    print(f"Found {len(posts)} English published posts:\n")
    print(f"{'#':<4} {'Date':<22} {'Title':<60} {'Category'}")
    print("-" * 120)
    for post in posts:
        title_display = post.title[:57] + '...' if len(post.title) > 60 else post.title
        print(f"{post.number:<4} {post.date:<22} {title_display:<60} {post.category}")
