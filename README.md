# AI Blog Imager 

Automatically generate professional, branded cover images for every post on your WordPress blog — no design skills needed.

> **Origin story:** I built this tool to help a physiotherapy clinic in Bangkok automatically create on-brand cover images for every article on their website. It worked so well that I generalized it so anyone can use it for their own blog.

## What Does This Do?

If you run a WordPress blog and need a unique, branded cover image for each post, this tool does the heavy lifting for you:

1. **Reads your blog posts** — Point it at your WordPress export file (XML) and it pulls out every post title and content.
2. **Writes a smart image prompt** — It figures out what the article is about and builds a detailed description of the perfect photo to match, using your branding.
3. **Generates the image with AI** — Uses Google's Gemini AI to create a photorealistic image that matches your brand style (based on reference images you provide).
4. **Quality-checks with a second AI** — An Anthropic Claude AI reviews each image to make sure it looks right: correct framing, visible branding, and it actually matches the blog topic.
5. **Fixes problems automatically** — If an image doesn't pass quality checks after a few tries, a more powerful AI rewrites the prompt and tries again.

The end result: an `output/` folder full of ready-to-upload blog cover images.

---

## How It Works (The Simple Version)

```
WordPress XML ──▶ Read Posts ──▶ Build Prompt ──▶ Generate Image ──▶ QA Check ──▶ Save
                                                       ▲                 │
                                                       │    fail         │
                                                       └─── retry ◀─────┘
```

- **Gemini AI** (Google) creates the images.
- **Claude Sonnet** (Anthropic) checks if each image is good enough.
- **Claude Opus** (Anthropic) rewrites the prompt when something keeps going wrong.

---

## Setup Guide

### Prerequisites

- **Python 3.10+** installed on your machine
- A **Google AI API key** (free) — [Get one here](https://aistudio.google.com/apikey)
- An **Anthropic API key** — [Get one here](https://console.anthropic.com) *(only needed for automatic quality checking; you can skip this and approve images manually)*

### 1. Clone the repository

```bash
git clone https://github.com/your-username/ai-blog-imager.git
cd ai-blog-imager
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your API keys

Copy the example environment file and fill in your keys:

```bash
cp .env.example .env
```

Then open `.env` in any text editor and paste your keys:

```
GOOGLE_AI_API_KEY=your-google-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
```

### 5. Add your WordPress export & reference images

- Export your blog content from WordPress by going to **Tools → Export → All content** in your WordPress admin dashboard, then place the downloaded XML file in the project root folder. The script auto-detects any `.xml` file with "wordpress" in the name.
- Add **reference images** (photos showing the branding / style you want your images to match) into the `reference_images/` folder. These guide the AI to keep a consistent visual style across all generated images.

### 6. Customize the prompts

Open `prompt_builder.py` and edit the style description, body-part keywords, and scene templates to match **your** brand and niche. The defaults are set up for a medical/physiotherapy clinic, but you can adapt them to any industry.

### 7. Run the script

```bash
# Preview what will be generated (no images created)
python main.py --dry-run

# Generate an image for a single post (e.g. post #16)
python main.py --single 16

# Generate images for all posts starting from #16
python main.py --start-from 16

# Generate all images (starting from the newest post)
python main.py

# Skip AI quality checks — approve each image manually instead
python main.py --no-qa
```

Generated images are saved in the `output/` folder.

---

## All Options

| Flag | What it does |
|---|---|
| `--dry-run` | Show posts & prompts without generating anything |
| `--list` | List all blog posts with their numbers |
| `--single N` | Generate image for post #N only |
| `--start-from N` | Start from post #N onward |
| `--end-at N` | Stop after post #N |
| `--no-qa` | Disable AI quality checks (manual approval) |
| `--xml PATH` | Specify the WordPress XML file manually |
| `--output DIR` | Change output folder (default: `output/`) |
| `--delay SECS` | Wait time between images (default: 3s) |
| `--include-drafts` | Include draft posts, not just published ones |
| `--english-only` | Only process English-language posts |

---

## Project Structure

```
ai-blog-imager/
├── main.py              # Entry point — ties everything together
├── scraper.py           # Reads and parses the WordPress XML export
├── prompt_builder.py    # Builds image generation prompts from blog content
├── image_generator.py   # Calls Google Gemini to create images
├── qa_agent.py          # Claude Sonnet checks image quality
├── debugger_agent.py    # Claude Opus rewrites failing prompts
├── reference_images/    # Your branding photos (logo, uniform style, etc.)
├── output/              # Where generated images are saved
├── requirements.txt     # Python dependencies
└── .env.example         # Template for API keys
```

---

## Adapting to Your Brand

This tool was originally built for a medical clinic, but you can adapt it to **any niche**:

1. **`prompt_builder.py`** — Edit `BRAND_STYLE` to describe your brand, update the `BODY_PART_KEYWORDS` and `TREATMENT_SCENES` dictionaries to match your industry's topics and visual themes.
2. **`reference_images/`** — Replace with photos that represent your own brand style (logos, uniforms, settings).
3. **`qa_agent.py`** — Tweak the QA evaluation criteria to check for things that matter to your brand.

---

## License

MIT
