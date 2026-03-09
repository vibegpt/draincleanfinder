# Fix Brief: DrainCleanFinder URL Structure + Site Cleanup

## Operating rules — read before doing anything

- Run fully autonomously. Do not stop to ask for confirmation, clarification, or permission at any point.
- Do not pause between steps.
- Do not say "shall I proceed?", "would you like me to...", or "let me know if...".
- If you hit an ambiguous situation, make a reasonable decision, log it, and keep going.
- The only time you stop is when all 5 tasks are complete and you have written the report.
- Complete all tasks in order. Do not skip any.

---

## Context

You are auditing and fixing the HTML files for draincleanfinder.com, a static lead gen
referral site hosted on Vercel. The site is plain HTML with no framework.

---

## TASK 1 — URL Structure Migration

All city HTML files currently use flat slugs like `/drain-cleaning/phoenix-az/`

Migrate to hub structure: `/drain-cleaning/[state-full-name]/[city-slug]/`

Examples:
- `/drain-cleaning/phoenix-az/` → `/drain-cleaning/arizona/phoenix/`
- `/drain-cleaning/mesa-az/` → `/drain-cleaning/arizona/mesa/`
- `/drain-cleaning/denver-co/` → `/drain-cleaning/colorado/denver/`

File rename mapping:
- `phoenix-az.html` → `drain-cleaning/arizona/phoenix/index.html`
- `mesa-az.html` → `drain-cleaning/arizona/mesa/index.html`
- `scottsdale-az.html` → `drain-cleaning/arizona/scottsdale/index.html`
- `tempe-az.html` → `drain-cleaning/arizona/tempe/index.html`
- `gilbert-az.html` → `drain-cleaning/arizona/gilbert/index.html`
- `tucson-az.html` → `drain-cleaning/arizona/tucson/index.html`
- `denver-co.html` → `drain-cleaning/colorado/denver/index.html`
- `aurora-co.html` → `drain-cleaning/colorado/aurora/index.html`
- `boulder-co.html` → `drain-cleaning/colorado/boulder/index.html`
- `broomfield-co.html` → `drain-cleaning/colorado/broomfield/index.html`
- `arvada-co.html` → `drain-cleaning/colorado/arvada/index.html`
- `castle-rock-co.html` → `drain-cleaning/colorado/castle-rock/index.html`
- `englewood-co.html` → `drain-cleaning/colorado/englewood/index.html`
- `fort-collins-co.html` → `drain-cleaning/colorado/fort-collins/index.html`
- `greeley-co.html` → `drain-cleaning/colorado/greeley/index.html`
- `highlands-ranch-co.html` → `drain-cleaning/colorado/highlands-ranch/index.html`
- `lakewood-co.html` → `drain-cleaning/colorado/lakewood/index.html`
- `littleton-co.html` → `drain-cleaning/colorado/littleton/index.html`
- `longmont-co.html` → `drain-cleaning/colorado/longmont/index.html`
- `westminster-co.html` → `drain-cleaning/colorado/westminster/index.html`

For each file:
1. Create the new directory and move the file to `index.html` inside it
2. Update ALL internal `href` links to reflect new paths
3. Update `<link rel="canonical">` in `<head>` to new URL
4. Update `og:url` meta tag in `<head>` to new URL

---

## TASK 2 — Remove Dead Nav Links

Remove these href links from ALL page nav elements (they point to pages that don't exist):
- `/drain-cleaning-guide/`
- `/drain-cleaning-services/`
- `/drain-cleaning-services/hydro-jetting/`
- `/drain-cleaning-services/commercial-drain-cleaning/`
- `/drain-cleaning-services/sewer-drain-cleaning/`

Replace nav with only these 3 links plus a CTA:

```html
<nav>
  <!-- logo linking to / -->
  <a href="/">Home</a>
  <a href="/drain-cleaning/">Drain Cleaning</a>
  <a href="/emergency-drain-cleaning/">Emergency</a>
  <a href="#get-quote" class="cta-button">Get Free Quote</a>
</nav>
```

Apply this to: `index.html`, `drain-cleaning-pillar.html`, and every city page.

---

## TASK 3 — Consistent Nav + Footer Across All Files

Nav and footer markup, fonts, and color tokens must be identical across every HTML file.

Footer must include on every page:
```html
<footer>
  <p>&copy; 2026 DrainCleanFinder. All rights reserved.</p>
  <a href="/privacy-policy/">Privacy Policy</a>
  <a href="/terms/">Terms</a>
</footer>
```

Fonts must be Sora + DM Sans on every page. Do not change.

---

## TASK 4 — Update vercel.json

Update `vercel.json` with:

**301 redirects** from all old flat URLs to new hub URLs. Example:
```json
{ "source": "/drain-cleaning/phoenix-az/", "destination": "/drain-cleaning/arizona/phoenix/", "permanent": true }
```

**Rewrites** so new hub URL paths serve the correct HTML files. Example:
```json
{ "source": "/drain-cleaning/arizona/phoenix/", "destination": "/drain-cleaning/arizona/phoenix/index.html" }
```

Add a redirect and rewrite for every city page.

---

## TASK 5 — Regenerate sitemap.xml

Regenerate `sitemap.xml` with all new canonical URLs.

- Use today's date as `lastmod`
- Priority `1.0` for homepage
- Priority `0.9` for hub pages (`/drain-cleaning/`, state pages)
- Priority `0.8` for all city pages

---

## Constraints — must be respected on every file

- No phone numbers anywhere. All CTAs use `href="#get-quote"` only.
- No "response within 1 hour" copy. Use "Free quotes" instead.
- Do not change any copy, headings, or form content. Layout, nav, and footer only.
- Fonts: Sora + DM Sans. Do not change.
- GA4 tag `G-XF5Z9Z0E0Q` must be present in `<head>` of every file.
- Formspree endpoint `xeelybgd` must be present in all contact forms.

---

## Commit when done

```bash
git add -A
git commit -m "feat: migrate to hub URL structure, fix nav, update vercel.json + sitemap"
```

---

## Report when complete

Write a summary covering:
- How many files were moved and renamed
- Any dead links found and removed beyond the ones listed
- Any constraint violations found and fixed
- The final sitemap URL count
- Anything that couldn't be completed and why
