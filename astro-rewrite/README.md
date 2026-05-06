# Astro rewrite (parallel scaffold — NOT a destructive migration)

This folder is a **starter** for migrating ChenDermatologist to Astro 5 if/when
you want SSG with islands and zero-JS-by-default rendering. The current static
site (`/index.html`, `/blog/*.html`, `blog-shared.js`) is **not touched**.

## Why migrate?

- Component reuse: header / nav / cards become single-file `.astro`
- Markdown content + frontmatter (instead of HTML + JSON-LD scripts)
- Built-in image optimization
- Islands architecture: load JS only where interactive
- TypeScript out of the box
- View Transitions API native support

## Why NOT migrate yet?

- Current site is **fast** (286 KB minified JS, ~7 KB CSS, Lighthouse 95+)
- You'd rewrite ~12,000 lines of JS + 32 articles + custom components
- Astro adds Node-build dependency — currently zero build step
- 4–5 days of work would balloon to 2–3 weeks

## When to migrate

Migrate when ANY of these become true:
- You hire collaborators (component-based becomes essential)
- Article count exceeds ~80 (HTML editing tedious)
- You add many interactive widgets (islands shine)
- You want type-safe schemas (TypeScript + Zod)

## Setup commands (when you decide to start)

```bash
cd astro-rewrite
npm create astro@latest -- --template blog --typescript strict --skip-houston
npm install
npm run dev
```

## Migration plan (incremental, ~2 weeks part-time)

1. **Day 1–2** — Set up Astro layout matching current header/footer/nav. Copy `tw-mini.css` to `src/styles/`.
2. **Day 3–4** — Migrate `blog-shared.js` into individual Astro components:
   - `<ReadingProgress />` (island, hydrates on idle)
   - `<Bookmark />` (island)
   - `<Search />` (island, hydrates on user interaction)
   - `<MedDiagram name="acne-pathogenesis" />` (no JS, server-rendered SVG)
3. **Day 5–6** — Migrate one article (`acne-myths.html`) to `src/content/blog/acne-myths.md` with frontmatter schema.
4. **Day 7–8** — Migrate the other 31 articles using a Python script.
5. **Day 9–10** — Wire up Decap CMS (already configured in `/admin/`).
6. **Day 11–12** — Diff-test: render every Astro page, compare HTML output to legacy `.html` to ensure no regressions.
7. **Day 13–14** — Switch DNS / Vercel project to `astro-rewrite/` build output.

## Schema for content collection (preview)

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';
const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    title_en: z.string().optional(),
    tag: z.enum(['痘痘', '防曬', '異膚', /* ... 30 tags */]),
    tag_en: z.string(),
    cat: z.enum(['myth', 'rx', 'product']),
    date: z.coerce.date(),
    description: z.string().max(180),
    pmids: z.array(z.string()).optional(),
    related: z.array(z.string()).optional(),  // slugs
  }),
});
export const collections = { blog };
```

## Files in this scaffold

- `astro.config.mjs` — Astro config with site URL + integrations
- `src/layouts/BaseLayout.astro` — header / footer / nav placeholder
- `src/components/MagCover.astro` — port of `DN.MAG_COVERS` SVG library
- `src/content/config.ts` — Zod schema (see above)

You'll fill these in when you migrate. The current site keeps running unchanged.
