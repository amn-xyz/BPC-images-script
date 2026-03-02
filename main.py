#!/usr/bin/env python3
"""
AI Blog Imager
========================
Parses WordPress XML export, generates AI images for each blog post
using Google Gemini (Nano Banana), with an Anthropic Claude QA loop.

Usage:
    python main.py --dry-run          # Preview all posts and prompts
    python main.py --single 16        # Generate image for post #16 only
    python main.py --start-from 16    # Generate images for posts 16+
    python main.py --no-qa            # Skip AI QA, use manual approval
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
from qa_agent import evaluate_image
from debugger_agent import rewrite_prompt


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


def _run_qa_loop(
    post,
    prompt: str,
    output_file: str,
    ref_images,
) -> bool:
    """
    Run QA-gated generation in two phases:

    Phase 1 — Original prompt, up to 3 attempts (Sonnet QA each time):
      Decision 1 → accept.
      Decision 2 → regenerate (attempt 1 or 2 only).
      Decision 3 → escalate: Opus rewrites the prompt, enter Phase 2.

    Phase 2 — Opus-rewritten prompt, up to 3 more attempts (Sonnet QA continues):
      Decision 1 → accept.
      Decision 2 → regenerate.
      Decision 3 → accept best-effort (avoid infinite Opus calls).

    Returns True if an image was ultimately accepted, False if generation itself
    failed exhaustively.
    """
    MAX_ATTEMPTS_PER_PHASE = 3
    past_images_log: list[str] = []
    current_prompt = prompt
    escalated = False
    phase_attempt = 1  # resets to 1 after escalation
    total_attempt = 0

    while True:
        total_attempt += 1
        phase_label = "post-Opus" if escalated else "original"
        print(f"\n  🎨 Generation attempt {phase_attempt}/{MAX_ATTEMPTS_PER_PHASE} ({phase_label} prompt)")

        success = generate_image(
            prompt=current_prompt,
            output_path=output_file,
            reference_images=ref_images if ref_images else None,
        )

        if not success:
            print(f"  ❌ Image generation failed")
            if phase_attempt >= MAX_ATTEMPTS_PER_PHASE:
                return False
            print(f"  🔄 Retrying generation...")
            phase_attempt += 1
            continue

        print(f"  ✅ Image saved: {output_file}")
        print(f"  🤖 QA Agent (Claude Sonnet) evaluating image...")

        try:
            qa_result = evaluate_image(
                blog_title=post.title,
                image_path=output_file,
                attempt_number=phase_attempt,
                past_images_log=past_images_log,
            )
        except Exception as e:
            print(f"  ⚠ QA Agent error: {e} — accepting image as-is")
            return True

        print(f"  📋 QA Reasoning: {qa_result.reasoning}")
        print(f"  📊 QA Decision:  {qa_result.decision}  ", end="")

        if qa_result.decision == 1:
            print("✅ (Continue)")
            return True

        elif qa_result.decision == 2:
            print("🔄 (Regenerate)")
            past_images_log.append(
                f"Attempt {total_attempt}: {qa_result.reasoning[:120]}"
            )
            if os.path.exists(output_file):
                os.remove(output_file)
            if phase_attempt >= MAX_ATTEMPTS_PER_PHASE:
                # Shouldn't normally reach here (Sonnet should return 3 on attempt 3)
                # but handle defensively — trigger the escalation path
                qa_result = type(qa_result)(decision=3, reasoning=qa_result.reasoning, failure_reason=qa_result.failure_reason)
                # Fall through to Decision 3 handling below via re-check
            else:
                phase_attempt += 1
                continue

        # Decision 3 (or phase-limit exceeded above)
        if qa_result.decision == 3:
            if not escalated:
                print("🛑 (Escalate to Opus)")
                print(f"  🧠 Escalating to Claude Opus debugger...")
                print(f"     Failure: {qa_result.failure_reason[:200]}")
                try:
                    revised_prompt = rewrite_prompt(
                        blog_title=post.title,
                        failure_reason=qa_result.failure_reason,
                        current_prompt=current_prompt,
                    )
                    current_prompt = revised_prompt
                    escalated = True
                    phase_attempt = 1  # reset attempt counter for the new phase
                    if os.path.exists(output_file):
                        os.remove(output_file)
                    print(f"  ✍ Opus rewrote the prompt — continuing QA loop with new prompt")
                    continue  # back to top of while loop with new prompt
                except Exception as e:
                    print(f"  ⚠ Opus debugger error: {e} — accepting last image")
                    return os.path.exists(output_file)
            else:
                # Already escalated and still failing — accept best effort
                print("⚠ (Already escalated — accepting best-effort image)")
                return os.path.exists(output_file)

        # Safety: exhausted phase attempts after escalation without decision 1
        if escalated and phase_attempt >= MAX_ATTEMPTS_PER_PHASE:
            print(f"  ⚠ Exhausted post-Opus attempts — accepting last image")
            return os.path.exists(output_file)


def _run_manual_loop(
    post,
    prompt: str,
    output_file: str,
    ref_images,
) -> tuple[bool, bool]:
    """
    Original interactive approval loop (used when --no-qa is set).
    Returns (success, should_quit).
    """
    while True:
        success = generate_image(
            prompt=prompt,
            output_path=output_file,
            reference_images=ref_images if ref_images else None,
        )

        if success:
            print(f"  ✅ Saved: {output_file}")
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
                return True, False
            elif choice == '2':
                if os.path.exists(output_file):
                    os.remove(output_file)
                print(f"  🔄 Regenerating image for #{post.number}...")
                continue
            elif choice == '3':
                return True, True
        else:
            print(f"  ❌ Failed to generate image")
            return False, False


def run_generation(
    posts,
    start_from: int,
    single: int | None,
    output_dir: str,
    delay: float,
    use_qa: bool = True,
    end_at: int | None = None,
):
    """Generate images for the specified posts."""
    # Load reference images for style consistency
    print("Loading reference images...")
    ref_images = load_reference_images('reference_images')
    if ref_images:
        print(f"  Loaded {len(ref_images)} reference image(s)")
    else:
        print("  ⚠ No reference images found in reference_images/ directory")
        print("    Images will be generated without style reference")

    if use_qa:
        print("  🤖 AI QA mode: Claude Sonnet 4.5 + Opus 4.5 orchestration enabled")
    else:
        print("  👤 Manual approval mode (--no-qa)")

    # Filter posts
    if single is not None:
        target_posts = [p for p in posts if p.number == single]
        if not target_posts:
            print(f"\n❌ Post #{single} not found! Total posts: {len(posts)}")
            sys.exit(1)
    else:
        target_posts = [p for p in posts if p.number >= start_from]
        if end_at is not None:
            target_posts = [p for p in target_posts if p.number <= end_at]

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

        print(f"\n[{i}/{total}] 🖼  #{post.number}: {post.title}")
        prompt = build_prompt(post)

        if use_qa:
            accepted = _run_qa_loop(post, prompt, output_file, ref_images)
            if accepted:
                success_count += 1
            else:
                fail_count += 1
        else:
            success, should_quit = _run_manual_loop(post, prompt, output_file, ref_images)
            if success:
                success_count += 1
            else:
                fail_count += 1
            if should_quit:
                print(f"\n  🛑 Quitting script.")
                break

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
        description='AI Blog Imager - Generate AI images for WordPress blog posts',
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
    parser.add_argument('--end-at', type=int, default=None,
                        help='Stop after this post number (inclusive). Default: process all.')
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
    parser.add_argument('--no-qa', action='store_true',
                        help='Disable AI QA loop and use manual approval instead')
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
    
    use_qa = not args.no_qa

    # Check for required API keys before generation
    if not os.environ.get('GOOGLE_AI_API_KEY'):
        print("\n❌ GOOGLE_AI_API_KEY not set!")
        print("   1. Get a key at: https://aistudio.google.com/apikey")
        print("   2. Create a .env file with: GOOGLE_AI_API_KEY=your-key-here")
        sys.exit(1)

    if use_qa and not os.environ.get('ANTHROPIC_API_KEY'):
        print("\n❌ ANTHROPIC_API_KEY not set!")
        print("   1. Get a key at: https://console.anthropic.com")
        print("   2. Add to your .env file: ANTHROPIC_API_KEY=your-key-here")
        print("   3. Or run with --no-qa to use manual approval instead")
        sys.exit(1)

    # Generation mode
    run_generation(posts, args.start_from, args.single, args.output, args.delay, use_qa, args.end_at)


if __name__ == '__main__':
    main()
