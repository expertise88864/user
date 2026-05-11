# -*- coding: utf-8 -*-
"""Fix broken bilingual elements in hairloss-myths.html and melasma-myths.html.

The earlier strip-pass regex terminated at the first `"` of a nested
`<strong data-zh="...">`, leaving the rest of the original outer data-zh
value as visible junk text inside the element body.

This pass rebuilds the TLDR + disclaimer blocks cleanly using a regex
that anchors on the OUTER element start (<p class="...tldr"...> or
<div class="disclaimer"...>) and consumes through the closing tag.
"""
from pathlib import Path
import re


HAIRLOSS_TLDR = (
    '<p class="mt-6 text-[15.5px] text-ink-700 leading-[1.9] tldr">'
    '<span data-zh="落髮是男女都會煩惱的問題。每個月新冒出來的「生髮水」、「養髮液」、「髮根活力素」一堆，但" '
    'data-en="Hair loss is a worry shared by both men and women. New &quot;hair tonics&quot;, &quot;follicle serums&quot; appear every month — but ">'
    '落髮是男女都會煩惱的問題。每個月新冒出來的「生髮水」、「養髮液」、「髮根活力素」一堆，但</span>'
    '<strong data-zh="真正有實證的就那幾個" data-en="only a handful are evidence-based">真正有實證的就那幾個</strong>'
    '<span data-zh="。本文整理 7 個民眾最常有的迷思，並附 Hamilton-Norwood 雄性禿分級、3 線治療階梯、植髮注意事項。" '
    'data-en=". This article walks through the 7 most common patient myths, plus the Hamilton-Norwood AGA scale, a 3-tier treatment ladder, and key points about hair transplants.">'
    '。本文整理 7 個民眾最常有的迷思，並附 Hamilton-Norwood 雄性禿分級、3 線治療階梯、植髮注意事項。</span></p>'
)

HAIRLOSS_DISC = (
    '<div class="disclaimer">'
    '<strong data-zh="提醒 ·" data-en="Reminder ·">提醒 ·</strong> '
    '<span data-zh="各種落髮成因不同（雄性禿、圓禿、休止期、貧血、甲狀腺、紅斑性狼瘡⋯⋯），" '
    'data-en="Hair loss has many possible causes (androgenetic, alopecia areata, telogen effluvium, anemia, thyroid disease, lupus, …), ">'
    '各種落髮成因不同（雄性禿、圓禿、休止期、貧血、甲狀腺、紅斑性狼瘡⋯⋯），</span>'
    '<strong data-zh="診斷後再治療最有效" data-en="diagnosis-first, then treatment is most effective">診斷後再治療最有效</strong>'
    '<span data-zh="。本文僅供衛教，個別評估請至皮膚科。" '
    'data-en=". This article is for general education only — please see a dermatologist for individual assessment.">'
    '。本文僅供衛教，個別評估請至皮膚科。</span></div>'
)

MELASMA_DISC = (
    '<div class="disclaimer">'
    '<strong data-zh="提醒 ·" data-en="Reminder ·">提醒 ·</strong> '
    '<span data-zh="肝斑容易混淆其他色素疾病（顴骨母斑 ADM、太田母斑、雀斑、發炎後色素沉澱）。本文僅供衛教，正式診斷與治療請至皮膚科。" '
    'data-en="Melasma is easily confused with other pigmentary disorders (Hori&#39;s macules / ADM, nevus of Ota, freckles, post-inflammatory hyperpigmentation). This article is general education only — see a dermatologist for diagnosis and treatment.">'
    '肝斑容易混淆其他色素疾病（顴骨母斑 ADM、太田母斑、雀斑、發炎後色素沉澱）。本文僅供衛教，正式診斷與治療請至皮膚科。</span></div>'
)


def fix_tldr(src):
    """Replace any <p ...tldr...">...</p> block whose body contains a stray
    `data-en="` literal (the corruption signature) with the clean rebuild."""
    pat = re.compile(
        r'<p[^>]*\btldr\b[^>]*>(?:(?!</p>).)*?\sdata-en="[^"]*">(?:(?!</p>).)*?</p>',
        re.DOTALL,
    )
    return pat.sub(HAIRLOSS_TLDR, src, count=1)


def fix_disclaimer(src, replacement):
    """Replace any <div class="disclaimer">...</div> block (corruption agnostic)."""
    pat = re.compile(
        r'<div class="disclaimer">(?:(?!</div>).)*?</div>',
        re.DOTALL,
    )
    return pat.sub(replacement, src, count=1)


def process(fp, tldr_fix, disc_replacement):
    p = Path(fp)
    if not p.exists():
        print(f'{fp}: not found, skipping')
        return
    src = p.read_text(encoding='utf-8')
    orig = src
    if tldr_fix:
        src = fix_tldr(src)
    src = fix_disclaimer(src, disc_replacement)
    if src != orig:
        p.write_text(src, encoding='utf-8')
        print(f'{fp}: bilingual blocks rebuilt')
    else:
        print(f'{fp}: no changes')


# Badge div has same nested-attribute corruption — outer data-zh contains a
# `<span class='...' data-zh="...">` with inner double-quoted attrs, which
# truncated to the first inner `"`. Strip the outer data-zh/data-en and wrap
# the leading plain-text in its own bilingual span.
BADGE_BROKEN = (
    ' data-zh="衛教 · 迷思澄清 <span class=\'ml-3 inline-block px-2 py-0.5 rounded-full bg-mint-100 text-teal-700 text-[10.5px] font-semibold normal-case tracking-normal\' data-zh="更新日期 · 2026-05-03" data-en="Updated · 2026-05-03">更新日期 · 2026-05-03</span>" data-en="Patient Education · Myth-busting <span class=\'ml-3 inline-block px-2 py-0.5 rounded-full bg-mint-100 text-teal-700 text-[10.5px] font-semibold normal-case tracking-normal\'>Updated 2026-05-03</span>"'
)
BADGE_FIXED = ''  # just strip — inner span keeps its bilingual data


def fix_badge(src):
    return src.replace(BADGE_BROKEN, BADGE_FIXED)


def main():
    for fp, with_tldr, disc in [
        ('blog/hairloss-myths.html',     True,  HAIRLOSS_DISC),
        ('en/blog/hairloss-myths.html',  True,  HAIRLOSS_DISC),
        ('blog/melasma-myths.html',      False, MELASMA_DISC),
        ('en/blog/melasma-myths.html',   False, MELASMA_DISC),
    ]:
        p = Path(fp)
        if not p.exists():
            print(f'{fp}: not found')
            continue
        src = p.read_text(encoding='utf-8')
        orig = src
        if with_tldr:
            src = fix_tldr(src)
        src = fix_disclaimer(src, disc)
        src = fix_badge(src)
        if src != orig:
            p.write_text(src, encoding='utf-8')
            print(f'{fp}: rebuilt')
        else:
            print(f'{fp}: no change')


if __name__ == '__main__':
    main()
