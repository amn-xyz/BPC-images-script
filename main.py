#!/usr/bin/env python3
"""
BPC Blog Image Generator
========================
Parses WordPress XML export, generates AI images for each blog post
using Google Gemini (Nano Banana), and saves them as numbered files.

Usage:
    python main.py --dry-run          # Preview all posts and prompts
    python main.py --single 16        # Generate image for post #16 only
    python main.py --start-from 16    # Generate images for posts 16+
    python main.py                    # Generate all images (starts from 1)
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from scraper import parse_xml_export
from prompt_builder import build_prompt, build_prompt_summary
from image_generator import generate_image, load_reference_images


def find_xml_file(directory: str = '.') -> str | None:
    """Find the WordPress XML export file in the given directory."""
    for f in sorted(Path(directory).iterdir()):
        if f.suffix == '.xml' and 'wordpress' in f.name.lower():
            return str(f)
    # Fallback: any XML file
    for f in sorted(Path(directory).iterdir()):
        if f.suffix == '.xml':
            return str(f)
    return None


def run_dry_run(posts, start_from: int):
    """Print all posts and their generated prompts without creating images."""
    print(f"\n{'='*80}")
    print(f"DRY RUN — Showing posts from #{start_from} onward")
    print(f"{'='*80}\n")
    
    count = 0
    for post in posts:
        if post.number < start_from:
            continue
        
        summary = build_prompt_summary(post)
        
        print(f"📄 Post #{post.number}: {post.title}")
        print(f"   Slug: {post.slug}")
        print(f"   Date: {post.date}")
        print(f"   Category: {post.category}")
        print(f"   Body Part: {summary['body_part']}")
        print(f"   Scene: {summary['scene']}")
        print(f"   Content preview: {post.content[:150]}...")
        print(f"   Output file: output/{post.number}_{post.slug}.png")
        print()
        count += 1
    
    print(f"{'='*80}")
    print(f"Total posts to generate: {count}")
    print(f"{'='*80}")


def run_generation(posts, start_from: int, single: int | None, output_dir: str, delay: float):
    """Generate images for the specified posts."""
    # Load reference images for style consistency
    print("Loading BPC reference images...")
    ref_images = load_reference_images('reference_images')
    if ref_images:
        print(f"  Loaded {len(ref_images)} reference image(s)")
    else:
        print("  ⚠ No reference images found in reference_images/ directory")
        print("    Images will be generated without style reference")
    
    # Filter posts
    if single is not None:
        target_posts = [p for p in posts if p.number == single]
        if not target_posts:
            print(f"\n❌ Post #{single} not found! Total posts: {len(posts)}")
            sys.exit(1)
    else:
        target_posts = [p for p in posts if p.number >= start_from]
    
    if not target_posts:
        print(f"\n✅ No posts to process (start_from={start_from}, total={len(posts)})")
        return
    
    os.makedirs(output_dir, exist_ok=True)
    
    total = len(target_posts)
    success_count = 0
    fail_count = 0
    
    print(f"\n🎨 Generating {total} image(s)...\n")
    
    for i, post in enumerate(target_posts, 1):
        output_file = os.path.join(output_dir, f"{post.number}_{post.slug}.png")
        
        # Skip if already exists
        if os.path.exists(output_file):
            print(f"[{i}/{total}] ⏭ #{post.number} already exists, skipping: {post.title}")
            success_count += 1
            continue
        
        prompt = build_prompt(post)
        
        # Interactive generation loop
        while True:
            print(f"\n[{i}/{total}] 🖼 #{post.number}: {post.title}")
            
            success = generate_image(
                prompt=prompt,
                output_path=output_file,
                reference_images=ref_images if ref_images else None,
            )
            
            if success:
                print(f"  ✅ Saved: {output_file}")
                
                # Ask user for approval
                print(f"\n  📋 Review the generated image: {output_file}")
                print(f"     1. ✅ Continue (accept & move to next)")
                print(f"     2. 🔄 Regenerate image")
                print(f"     3. 🛑 Quit script")
                
                while True:
                    choice = input("\n  Enter choice (1/2/3): ").strip()
                    if choice in ('1', '2', '3'):
                        break
                    print("  ⚠ Invalid choice. Please enter 1, 2, or 3.")
                
                if choice == '1':
                    success_count += 1
                    break  # Move to next post
                elif choice == '2':
                    # Delete the generated image and regenerate
                    if os.path.exists(output_file):
                        os.remove(output_file)
                    print(f"  🔄 Regenerating image for #{post.number}...")
                    continue  # Re-run the while loop
                elif choice == '3':
                    print(f"\n  🛑 Quitting script.")
                    success_count += 1  # Count the last image as success since it was saved
                    return  # Exit run_generation entirely
            else:
                print(f"  ❌ Failed to generate image")
                fail_count += 1
                break  # Move to next post
        
        # Rate limiting delay between images
        if i < total:
            print(f"  ⏳ Waiting {delay}s before next image...")
            time.sleep(delay)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 Generation Complete")
    print(f"   ✅ Success: {success_count}")
    print(f"   ❌ Failed:  {fail_count}")
    print(f"   📁 Output:  {output_dir}/")
    print(f"{'='*80}")


def main():
    parser = argparse.ArgumentParser(
        description='BPC Blog Image Generator - Generate AI images for WordPress blog posts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --dry-run          Preview all posts and prompts
  python main.py --single 16        Generate image for post #16 only
  python main.py --start-from 16    Generate images for posts 16+
  python main.py --list              List all posts with numbers
        """
    )
    
    parser.add_argument('--xml', type=str, default=None,
                        help='Path to WordPress XML export file (auto-detected if not specified)')
    parser.add_argument('--start-from', type=int, default=1,
                        help='Start generating from this post number (default: 1)')
    parser.add_argument('--single', type=int, default=None,
                        help='Generate image for a single post number only')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show prompts without generating images')
    parser.add_argument('--list', action='store_true',
                        help='List all posts with their numbers')
    parser.add_argument('--output', type=str, default='output',
                        help='Output directory for generated images (default: output)')
    parser.add_argument('--delay', type=float, default=3.0,
                        help='Delay in seconds between image generations (default: 3.0)')
    parser.add_argument('--include-drafts', action='store_true',
                        help='Include draft posts (default: published only)')
    parser.add_argument('--english-only', action='store_true',
                        help='Only include English posts (default: all languages)')
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Find XML file
    xml_path = args.xml or find_xml_file()
    if not xml_path or not os.path.exists(xml_path):
        print("❌ No WordPress XML export file found!")
        print("   Place the XML file in this directory or specify with --xml")
        sys.exit(1)
    
    print(f"📂 Parsing: {xml_path}")
    
    # Parse posts
    posts = parse_xml_export(
        xml_path,
        english_only=args.english_only,
        published_only=not args.include_drafts,
    )
    
    print(f"📝 Found {len(posts)} English posts")
    
    if not posts:
        print("❌ No posts found in XML file!")
        sys.exit(1)
    
    # List mode
    if args.list:
        print(f"\n{'#':<4} {'Date':<22} {'Category':<20} {'Title'}")
        print("-" * 100)
        for post in posts:
            title_display = post.title[:55] + '...' if len(post.title) > 58 else post.title
            print(f"{post.number:<4} {post.date:<22} {post.category:<20} {title_display}")
        return
    
    # Dry run mode
    if args.dry_run:
        start = args.single if args.single else args.start_from
        run_dry_run(posts, start)
        return
    
    # Check for API key before generation
    if not os.environ.get('GOOGLE_AI_API_KEY'):
        print("\n❌ GOOGLE_AI_API_KEY not set!")
        print("   1. Get a key at: https://aistudio.google.com/apikey")
        print("   2. Create a .env file with: GOOGLE_AI_API_KEY=your-key-here")
        sys.exit(1)
    
    # Generation mode
    run_generation(posts, args.start_from, args.single, args.output, args.delay)


if __name__ == '__main__':
    main()
