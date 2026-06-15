#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject a TL;DR "一句話結論" direct-answer block under each article H1.

GEO/AEO lever: AI answer engines (AI Overviews, Perplexity, ChatGPT-search)
reward a short, extractable, plain-language answer near the top of the page,
and — unlike classic SERPs — do NOT gate on domain authority. The site's
speakable JSON-LD already lists `.dn-tldr` / `[data-speakable]` selectors, so
this block is picked up automatically once present.

Placement: immediately AFTER the first </h1>, BEFORE the disclaimer block.
Bilingual: <span data-en="..."> so the EN mirror swaps it at runtime.
Idempotent: replaces an existing .dn-tldr block, else inserts it.

⚠️ Medical content — the blurbs below are DRAFTS for physician review.
Usage:  python _inject_tldr.py            # dry-run (report only)
        python _inject_tldr.py --apply     # write changes (after review)
"""
import os, io, sys, re, html as _html

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.abspath(__file__))
APPLY = "--apply" in sys.argv

# slug -> {zh: 40-80 字 direct answer, en: concise English}
TLDR = {
    "acne-myths": {
        "zh": "痘痘的根因是毛孔角化、皮脂與痤瘡桿菌發炎,不是「沒洗乾淨」。擠痘、狂洗臉、戒巧克力都無法根治;真正有效的是外用 A 酸/酸類、必要時口服藥,並規律使用數週才見效。",
        "en": "Acne is driven by clogged pores, oil and C. acnes inflammation — not poor hygiene. Squeezing, over-washing or cutting chocolate won't cure it; topical retinoids/acids (plus oral meds when needed), used consistently for weeks, do.",
    },
    "isotretinoin-patient": {
        "zh": "口服 A 酸是目前對中重度痘痘最有效的治療,多數人完成療程後可長期緩解,部分仍可能復發。常見副作用是嘴唇與皮膚乾燥、可處理;重點是孕婦絕對禁用、需嚴格避孕並依醫囑定期追蹤。",
        "en": "Oral isotretinoin is the most effective treatment for moderate-to-severe acne, with lasting remission for most though some relapse. Dryness is the common, manageable side effect; it is absolutely contraindicated in pregnancy and needs strict contraception and monitoring.",
    },
    "topical-acids-patient": {
        "zh": "A 酸、A 醇、杜鵑花酸、果酸、水楊酸各有適應症與刺激性。新手從低濃度、隔天晚上開始,白天務必防曬;不必「越濃越好」,重點是建立耐受、持續使用。",
        "en": "Retinoids, retinol, azelaic, AHA and salicylic acid each have their use and irritancy. Start low-strength every other night and always use daytime sunscreen — 'stronger' isn't better; consistency is.",
    },
    "atopic-dermatitis-overview": {
        "zh": "異位性皮膚炎是慢性、會反覆的皮膚屏障與免疫問題,不會傳染,也不是「沒擦乳液」那麼簡單。治療核心是每天保濕+發作時外用類固醇/TCI;中重度可用生物製劑或 JAK,多能良好控制。",
        "en": "Atopic dermatitis is a chronic, relapsing skin-barrier + immune condition — not contagious and not just 'dry skin'. Daily moisturising plus topical steroids/TCI for flares controls most cases; biologics or JAK help moderate-to-severe disease.",
    },
    "sunscreen-myths": {
        "zh": "室內、陰天、冬天紫外線仍在,該防曬。SPF 不是越高越好,足量與補擦更重要;物理性與化學性防曬都有效,選一支你願意天天擦的才是好防曬。",
        "en": "UV reaches you indoors, on cloudy days and in winter, so wear sunscreen. Higher SPF isn't automatically better — applying enough and reapplying matters more. Both mineral and chemical filters work; the best is the one you'll use daily.",
    },
    "melasma-myths": {
        "zh": "肝斑是受荷爾蒙與紫外線影響的慢性色素問題,容易復發,無法「雷射一次根治」。治療靠嚴格防曬+外用美白藥(如三合一、傳明酸);雷射使用不當反而會反黑。",
        "en": "Melasma is a hormone- and UV-driven chronic pigment problem that recurs and can't be 'lasered away' in one go. Strict sun protection plus topical lighteners (triple-combination, tranexamic acid) are the mainstay; wrong laser settings can darken it.",
    },
    "hairloss-myths": {
        "zh": "戴帽子、洗頭、壓力通常不是雄性禿主因;雄性禿是基因加雄性荷爾蒙造成、會持續進展。有實證的是 minoxidil 與 finasteride,需持續使用,停藥會逐漸退回。",
        "en": "Hats, washing and stress aren't the main cause of male-pattern hair loss — it's genetic + hormonal and progressive. Minoxidil and finasteride are the evidence-based treatments and must be used continuously; stopping reverses gains.",
    },
    "psoriasis-myths": {
        "zh": "乾癬不是「癬」、不會傳染,是免疫造成的慢性發炎,可能合併關節炎與代謝疾病。雖不能根治,但外用藥、照光、口服與生物製劑能讓多數人皮膚接近清零。",
        "en": "Psoriasis is not 'ringworm' and not contagious — it's chronic immune-driven inflammation that can involve the joints and metabolic disease. It can't be cured, but topicals, phototherapy, oral and biologic drugs can clear most people's skin.",
    },
    "rosacea-myths": {
        "zh": "酒糟不是單純「過敏」或洗不乾淨,是以血管與發炎為主的慢性問題,會臉紅、長丘疹膿皰。治療要避開誘因(辣、酒、高溫)加上外用/口服藥;亂擦類固醇會惡化。",
        "en": "Rosacea isn't simple 'allergy' or poor washing — it's a chronic vascular + inflammatory condition causing flushing and bumps. Avoid triggers (spice, alcohol, heat) plus topical/oral therapy; misusing steroids makes it worse.",
    },
    "tinea-myths": {
        "zh": "香港腳、灰指甲是黴菌感染,不痛不癢也要治、且會傳染家人。擦藥常需數週至數月;灰指甲多需口服藥才會好,療程不足是最常見的復發原因。",
        "en": "Athlete's foot and nail fungus are fungal infections that need treatment even when painless, and they spread to family. Creams often take weeks-to-months; nail fungus usually needs oral medication, and under-treatment is the top cause of relapse.",
    },
    "alopecia-areata": {
        "zh": "圓禿是自體免疫攻擊毛囊造成的塊狀掉髮,不是壓力「嚇掉」的,多數會自行或在治療後重新長回。範圍大或反覆者,JAK 抑制劑是新的有效選擇。",
        "en": "Alopecia areata is autoimmune patchy hair loss — not 'scared off' by stress — and often regrows by itself or with treatment. For extensive or recurrent cases, JAK inhibitors are an effective new option.",
    },
    "vitiligo": {
        "zh": "白斑是自體免疫造成的色素脫失,不會傳染,可能合併甲狀腺等自體免疫疾病。早期治療(外用藥、照光、新藥 ruxolitinib)有機會復色,臉部與近期病灶效果較好。",
        "en": "Vitiligo is autoimmune loss of skin pigment, not contagious, and can accompany thyroid and other autoimmune disease. Early treatment (topicals, phototherapy, newer ruxolitinib) can repigment, working best on the face and recent lesions.",
    },
}

def box(zh: str, en: str) -> str:
    # Match the existing doctor-written TL;DR design (atopic-dermatitis-overview)
    # for visual consistency. The `.dn-tldr` class is already in the speakable
    # JSON-LD selector, so no data-speakable needed. data-zh/data-en feed the
    # bilingual runtime swap (inner text = zh source).
    style = ("background:#fefce8;border-left:4px solid #ca8a04;border-radius:0 10px 10px 0;"
             "padding:14px 18px;margin:18px 0;font-size:14px;line-height:1.85")
    # Escape so any future <, >, &, or quote in the text can't corrupt markup.
    zh_e = _html.escape(zh, quote=True)
    en_e = _html.escape(en, quote=True)
    return (f'<div class="dn-tldr" style="{style}">'
            f'<strong data-zh="一句話結論" data-en="TL;DR">一句話結論</strong>:'
            f'<span data-zh="{zh_e}" data-en="{en_e}">{zh_e}</span></div>')


def main():
    inserted, skipped, missing = [], [], []
    for slug, t in TLDR.items():
        path = os.path.join(ROOT, "blog", f"{slug}.html")
        if not os.path.exists(path):
            missing.append(slug)
            continue
        src = open(path, encoding="utf-8").read()
        # NEVER overwrite an existing TL;DR (may be a richer doctor-written one).
        if 'class="dn-tldr"' in src:
            skipped.append(slug)
            continue
        m = re.search(r'</h1>', src)
        if not m:
            missing.append(slug + " (no </h1>)")
            continue
        new = src[:m.end()] + box(t["zh"], t["en"]) + src[m.end():]
        inserted.append(slug)
        if APPLY:
            open(path, "w", encoding="utf-8").write(new)

    print(("APPLIED" if APPLY else "DRY-RUN") + f" — TL;DR injection")
    print(f"  inserted: {len(inserted)}")
    for slug in inserted:
        print(f"     + blog/{slug}.html")
    if skipped:
        print(f"  skipped (already has TL;DR): {skipped}")
    if missing:
        print(f"  MISSING: {missing}")


if __name__ == "__main__":
    main()
