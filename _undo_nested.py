"""Undo data-zh/data-en added to inline tags (strong/em/span) where the
outer element already had data-zh containing the same content. This avoids
nested data-zh attrs that fail static a11y.
"""
import re
import pathlib

FILES = [
    'blog/severe-scabies-treatment.html',
    'blog/dermatologic-oral-examination.html',
]

# Strings I added in _rest_bilingual.py that overlap with content already
# inside an outer element's data-zh attribute. These are inline strong/em
# labels that are part of a longer parent paragraph/list item.
INLINE_LABELS = {
    "提醒：", "結論：高劑量沒有比較好。", "劑量", "時程", "怎麼吃",
    "禁忌與注意", "塗抹範圍", "停留時間", "用量", "結痂型加強",
    "關鍵原則：", "需要一起治療的人", "同治療策略", "通報", "個案診斷",
    "同步治療", "隔離結痂型", "環境清潔", "監測 6 週",
    "5% permethrin 乳膏", "口服 ivermectin",
    "請以衛福部食藥署藥品許可證資料庫與健保署藥品給付規定為準",
    "benzyl benzoate 10-25% 乳劑", "1% lindane 乳膏", "合併治療",
    "輕度（grade 1）", "中度（grade 2）", "重度（grade 3）",
    "台灣特殊族群提醒", "延伸閱讀：", "關鍵訊息：",
    "需要盡快就醫的紅旗：",
    "皮膚刮片顯微鏡（gold standard）", "皮膚鏡（dermoscopy）",
    "臨床診斷（IACS 2020 國際共識準則）",
    "口底（floor of mouth）", "軟顎後段",
    "腮腺管開口（Stensen's papilla, 上頷第二大臼齒對側）",
    "覆蓋牙根的牙齦", "第一塊樣本", "第二塊樣本",
    "器官移植 / 免疫抑制者", "抗凝血藥 / 抗血小板藥",
    "放射治療後", "孕婦", "陳翊嘉 醫師",
    "外用類固醇完整指南", "皮膚切片完整衛教",
    "皮膚科 25 個最常見問題",
    "皮膚切片與腫瘤切除手術完整衛教",
    "日光性角化症 AK + 鱗狀細胞癌 SCC",
    "口周皮膚炎完整衛教",
}


def patch(html: str) -> tuple[str, int]:
    count = 0
    for tag in ['strong', 'em', 'span', 'h3', 'a']:
        # Match: <tag ATTRS data-zh="X" data-en="Y" ATTRS2>X</tag>
        # where X is one of the inline labels.
        for label in INLINE_LABELS:
            zh_esc = re.escape(label.replace('"', '&quot;'))
            pat = re.compile(
                r'<' + tag + r'\b([^>]*?)\s*data-zh="' + zh_esc + r'"\s+data-en="[^"]+"([^>]*)>(' + re.escape(label) + r')</' + tag + r'>'
            )

            def repl(m: re.Match) -> str:
                nonlocal count
                count += 1
                a1, a2, body = m.group(1), m.group(2), m.group(3)
                return f'<{tag}{a1}{a2}>{body}</{tag}>'

            html = pat.sub(repl, html)
    return html, count


def main() -> None:
    root = pathlib.Path(__file__).parent
    for rel in FILES:
        p = root / rel
        before = p.read_text(encoding='utf-8')
        after, n = patch(before)
        if n:
            p.write_text(after, encoding='utf-8')
            print(f'{rel}: reverted {n} nested data-zh on inline labels')
        else:
            print(f'{rel}: no changes')


if __name__ == '__main__':
    main()
