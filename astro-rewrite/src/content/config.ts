import { defineCollection, z } from 'astro:content';

const TAGS = [
  '痘痘', '痘疤', '防曬', '異膚', '兒童異膚', '肝斑', '美白',
  '酒糟肌', '玫瑰斑', '落髮', '圓禿', '足癬', '病毒疣', '皮蛇',
  '蕁麻疹', '結節性癢疹', '乾癬', '化膿性汗腺炎', '猴痘', '酸類',
  '口服 A 酸', '外用類固醇', '生物製劑', '白斑', '標靶藥物',
  '常見問題', '粉瘤', '健保規範', '雷射 / 光電', '皮膚淋巴瘤',
] as const;

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    title_en: z.string().optional(),
    tag: z.enum(TAGS),
    tag_en: z.string(),
    cat: z.enum(['myth', 'rx', 'product']),
    date: z.coerce.date(),
    description: z.string().max(180),
    pmids: z.array(z.string()).optional(),
    related: z.array(z.string()).optional(),
    cover_palette: z.enum(['cream', 'mint', 'beige', 'rose']).optional(),
  }),
});

const glossary = defineCollection({
  type: 'data',
  schema: z.object({
    terms: z.array(z.object({
      zh: z.string(),
      en: z.string(),
      def: z.string(),
      cat: z.string().optional(),
    })),
  }),
});

export const collections = { blog, glossary };
