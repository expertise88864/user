# REVIEW_PLAYBOOKS.md — 八大領域review 手冊(弱模型可執行版)

> 每一節 = 目的 → 命令 → 通過判準 → **基線**(本次完整 review 的實測值,附日期)→ 失敗處置 → 升級判準。
> 原則:**先跑 repo 自帶驗證器**(它們就是本站的規格書),不要憑印象評分。
> 基線過期怎麼辦:重跑命令取新值,更新本檔(隨做隨寫)。

## 0. 上線前總 gate(任何改動都適用)
```
python _run_quality.py check      # 必須 exit 0
git diff → Codex GPT-5.5 review   # APPROVE 才 push(全域規則)
```

## 1. SEO(技術面)
- 命令:`_check_seo_signals.py`、`_check_sitemap.py`、`_check_robots.py`、`_check_meta.py`
- 通過:全部 [OK];sitemap URL 數 = 可索引頁數;canonical 全站自指、無尾斜線混用(`/en` 不是 `/en/`)。
- 基線(2026-06-15):全綠;sitemap 125 URLs;hreflang 54 對互惠;`/en/` 尾斜線 bug 已修。
- 失敗處置:訊息會指出檔案 — 改**源頭**(見 PIPELINE.md)再 regen,不改產物。
- 判斷力提醒:**排名/流量問題 ≠ 技術 SEO 問題**。gate 全綠時流量低是站外權重問題(新網域),
  不要再磨站內。收錄真相只看 GSC(WebSearch 是美國節點、不支援 site:,不可作準)。

## 2. schema.org(結構化資料)
- 命令:`_audit_jsonld.py`(+ CI 的 schema-validator.yml)
- 通過:Errors: 0。型別分布基線(2026-06):417 blocks — MedicalWebPage 113、BreadcrumbList 122、
  ItemList 104、FAQPage 37、MedicalScholarlyArticle 14、HowTo 10、Physician 4。
- 不變量(改前先讀 DECISIONS.md):
  - 作者 Physician 節點:**有** hasCredential(醫師執照、無號碼),**絕不加** worksFor/affiliation。
  - `mainEntity → #article` 引用是**刻意契約**(auditor 強制),外部工具說它 dangling 也不改。
  - 病患衛教文用 MedicalWebPage(非 Article),research 文才用 MedicalScholarlyArticle — 刻意降級,防 Google 誤判。
- 失敗處置:JSON-LD 一律由 `_normalize_schema.py` 家族生成 — 改生成器,跑 `all`,兩次冪等。
- 升級:要「新增 schema 型別」或動作者權威表述 → 先問使用者。

## 3. Core Web Vitals(效能)
- 命令:`_check_performance_budget.py`(bundle 紀律)、`_check_pwa.py`。
  ⚠️ 誠實條款:**repo 檢查器不量真 CWV**(無 Lighthouse)。真值來源:GSC「核心網頁指標」報告,
  或 PageSpeed Insights 網頁版(貼 URL 手查)。harness 內無可靠 Lighthouse — 不要假裝量得到。
- 基線(2026-06):budget 綠;blog-shared.min.js 72KB(上限 75KB,接近頂);
  已知未修:Google Fonts 第三方 CSS render-blocking(_self_host_fonts.py 寫好未套用)、
  tw-mini.css/dn-below-fold.css render-blocking、首頁 HTML ~190KB。皆屬低優先(見 TECH_DEBT)。
- 判斷力提醒:CWV 是排名的小 tie-breaker,對新站流量影響≈0。除非 GSC 亮紅,不值得投入。

## 4. Metadata(title/description/OG)
- 命令:`_check_meta.py`(title 30-65 字元、desc 長度)、`_check_meta_descriptions.py`
  (寬度單位 120-220,CJK=2)、`_check_metadata_uniqueness.py`。
- 已知怪癖:兩支 checker 的 description 窗口**不一致**(字元 vs 寬度),少量 WARN 是常態、
  非 blocking — **以 `_check_meta_descriptions.py`(寬度版)為準**,warnings ≤ 20 可接受。
- 慣例(DECISIONS):zh 文章 title 後綴統一 `| 陳翊嘉醫師`;og/twitter title 跟隨;
  desc 是 SEO 源頭(blog-hub 卡片文字由它生成 → 改 desc 後跑 `_normalize_articles_desc.py` + `_minify.py`)。
- 基線(2026-06-15):125 頁 desc 全綠 0 problems;title 唯一性通過。

## 5. Internal Linking(內鏈)
- 命令:`_check_internal_link_density.py`(--orphans 只看孤兒)、`_check_internal_links.py`、
  `_check_en_internal_links.py`
- 通過判準:**孤兒(prose inbound=0)= 0 篇**;弱連結(1-2)只減不增。
- 基線(2026-06-06):孤兒 0(修復前 4)、弱連結 26、健康 28。
- 加內鏈 SOP:優先塞進「延伸閱讀」框(`data-en="Further reading:"` 的 `<p>` 內,
  append `；另見 <a href="/blog/SLUG" data-en="EN TITLE">中文錨點</a>`);雙語屬性齊全;
  改完跑 `_check_html_balance.py` + density 重驗。錨點文字用目標查詢語,不用「點這裡」。
- 結構目標(路線圖已定):pillar↔cluster 雙向 — 每篇支撐文往上鏈 pillar、pillar 往下鏈全部成員。

## 6. RAG-ready 架構(給檢索/引用系統的表面)
- 資產清單(全部已存在,是生成物):`llms.txt`(手維護清單)、`llms-full.txt`(全文語料,
  單篇 6000 字截斷)、`ai/summary.json`、`ai/faq.json`、`ai/service.json`、`.well-known/ai.txt`、
  每篇 JSON-LD(含 citations @graph、speakable、medical codes ICD-10/SNOMED/MeSH)。
- 驗證:`_normalize_llms_counts.py`(計數同步)、`_audit_jsonld.py`;
  llms-full 重生:`python _gen_llms_full.py`(來源=zh 文章 #proseZh,EN 鏡像刻意不入語料)。
- 通過判準:llms.txt 內文章數 = DN.ARTICLES 已發布數;llms-full.txt < 1MB;三份 ai/*.json 可 parse。
- 已知取捨(刻意,勿「修」):6000 字截斷(控檔案大小,尾部有 canonical URL 指路);
  EN 不入語料(zh 為權威源,llms.txt 有標註 EN 是 courtesy translation)。

## 7. AI Search / GEO(被 AI 引用的最佳化)
- 政策:引用型爬蟲全允許、訓練型封鎖(細節與名單:PIPELINE.md「三檔同步鐵則」+ DECISIONS D-06)。
  驗證:`_check_robots.py`(含 REQUIRED_BLOCKED 防護,防止訓練型被誤放行)。
- TL;DR 直答區塊(GEO 第一槓桿):`.dn-tldr`,H1 下、disclaimer 上,zh 40-80 字 + EN 對照,
  由 `_inject_tldr.py` 注入(冪等、**絕不覆寫**既有)。基線:12/57 篇(2026-06-15)。
  **剩餘 45 篇是現成任務**:每篇從既有 FAQ/內文濃縮草稿 → 醫師逐句審 → apply → gate → codex → push。
  措辭紅線(codex 實際退過件):不得寫「根治/cure」這類過強療效words — 用「最有效的治療…部分仍可能復發」。
- 量測:GSC 成效報告看曝光趨勢(領先指標);可選:自架 danishashko/geo-aeo-tracker 每週查
  ChatGPT/Perplexity/Gemini 是否引用本站(30 條目標查詢)。
- 判斷力提醒:GEO 是新站唯一不被網域權重卡死的通道 — 這一節的優先級**高於** CWV/站內 SEO 細節。

## 8. 可維護性 / 技術債
- 命令:`python _run_quality.py check` 兩次(第二次 diff 必須為空 = 全管線冪等);
  `git ls-files | grep -c "^_"`(根目錄腳本數,基線 ~128);TECH_DEBT.md 逐項狀態。
- 通過判準:gate 綠 + 冪等 + TECH_DEBT.md 無新增 P0/P1。
- 心智模型:這個 repo 的「測試」= 對**產物**的驗證器(31 支),生成器本身無單元測試 —
  所以改生成器的安全法是:跑 all → 看 git diff 是否**只有**你預期的變化 → 兩次冪等 → gate。
  diff 出現非預期檔案 = 立刻停下來讀懂再繼續,不要「看起來沒關係就 commit」。
- 升級判準:要重構管線結構(合併/拆分腳本、改執行順序)→ 屬架構決策,先問使用者。
