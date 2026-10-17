<section class="ex-note" id="laser-principles">
<h2>1. Laser Principles（雷射原理）</h2>
<h3>History（歷史）</h3>
<ul>
<li><strong class="ex-n">1900</strong> Max Planck：光以特定能量單位（quanta）釋放、傳遞與吸收。<span class="ex-ref">p.3820</span></li>
<li><strong class="ex-n">1917</strong> Einstein《The Quantum Theory of Radiation》：提出 <strong>stimulated emission</strong>（特定波長的 photon 撞擊 excited atom → 同時釋放 2 個同頻率 photons）。<span class="ex-ref">p.3820</span></li>
<li>LASER = <strong>L</strong>ight <strong>A</strong>mplification by the <strong>S</strong>timulated <strong>E</strong>mission of <strong>R</strong>adiation。<span class="ex-ref">p.3820</span></li>
<li><strong class="ex-n">1960</strong> Theodore Maiman 以 <strong>ruby crystal</strong> 做出第一台雷射。<span class="ex-ref">p.3820</span></li>
</ul>
<h3>Physics（物理基礎）</h3>
<ul>
<li>光速 c = <strong class="ex-n">2.998 × 10⁸ m/s</strong>；<strong>c = λ · ν</strong>（波長 × 頻率）。<span class="ex-ref">p.3820</span></li>
<li>Photon 能量與頻率成正比：<strong>頻率越高（波長越短）能量越高</strong>。<span class="ex-ref">p.3820</span></li>
<li>Visible light（可見光）：<strong class="ex-n">390 nm</strong>（violet）到 <strong class="ex-n">700 nm</strong>（red）；皮膚科多數雷射落在 visible 與 near infrared 範圍。<span class="ex-ref">p.3820</span></li>
<li>發射波長由激發態與基態的能量差決定：<strong>ΔE = hc/λL</strong>。<span class="ex-ref">p.3822</span></li>
</ul>
<h3>Laser device components（雷射構造）</h3>
<ul>
<li>所有雷射 = <strong>energy source</strong>（pumping：electrical current、flashlamp 或另一台雷射）+ <strong>optical resonator</strong>。<span class="ex-ref">p.3820</span></li>
<li>Resonator：管內的 medium + <strong>2 面平行鏡</strong>（一面完全不透光，一面部分可透光）。<span class="ex-ref">p.3820</span></li>
<li>Medium 可為 solid、liquid、liquid crystal 或 gas；<strong>medium 決定雷射波長與性質</strong>。<span class="ex-ref">p.3820</span></li>
<li>Stimulated emission 連鎖反應：1 → 2 → 4 photons，photon 數呈指數增加但每個 photon 能量不變；excited atoms 多於 ground state 稱為 <strong>(population) inversion</strong>；完全平行的 photons 由遠端部分透光鏡射出成為雷射光束。<span class="ex-ref">p.3822</span></li>
</ul>
<h3>Properties of laser light（雷射光特性）</h3>
<table class="ex-table">
<thead><tr><th scope="col">Property</th><th scope="col">意義</th><th scope="col">臨床重要性</th></tr></thead>
<tbody>
<tr><td><mark data-q="104-46">Monochromatic（單一波長）</mark></td><td>單一波長（temporal coherence）</td><td>可被特定 chromophore 選擇性吸收</td></tr>
<tr><td>Coherent（同調）</td><td>波在空間與時間上同相（crests、troughs 同步）</td><td>發散極小，遠距離不失強度</td></tr>
<tr><td>Collimated（準直）</td><td>所有 photons 彼此平行</td><td>遠距離不變形，能量可密集集中於小體積</td></tr>
</tbody>
</table>
<p class="ex-cite">p.3822–3823。</p>
<ul>
<li>相對地，natural light 與燈泡的 spontaneous emission 為 <strong>incoherent、divergent、spectrally broadband</strong>。<span class="ex-ref">p.3820</span></li>
<li>At-a-glance：<mark data-q="104-46">Laser = monochromatic、coherent、collimated；IPL = polychromatic、broadband、divergent</mark>。<span class="ex-ref">p.3820</span></li>
</ul>
<aside class="ex-trap"><strong>易錯</strong>Fig. 208-4 圖說把 flashlight 光寫成「divergent, coherent, and polychromatic」，但同一圖的標示寫「divergent incoherent white light」；內文寫 natural light 為 incoherent（p.3820），IPL 為 noncoherent（p.3824）、polychromatic（At-a-glance，p.3820）。<span class="ex-ref">p.3824</span></aside>
</section>

<section class="ex-note" id="emission-modes">
<h2>2. Emission Modes &amp; Q-switching（發射模式與 Q 開關）</h2>
<table class="ex-table">
<thead><tr><th scope="col">Mode</th><th scope="col">原理</th><th scope="col">Pulse／exposure</th></tr></thead>
<tbody>
<tr><td>Continuous wave（cw）</td><td>持續供能，輸出功率幾乎不變；以 shutter 開關光束</td><td>Shutter 開數 ms 到數秒；exposure 為一秒的分數到數秒</td></tr>
<tr><td>Pulsed</td><td>以 gas discharge 或 flashlamp 在限定時間供能；脈衝內能量先升、達峰、再下降</td><td><strong class="ex-n">µs 到 ms</strong>；peak power 可比 cw 最大輸出高達 <strong class="ex-n">100 倍</strong></td></tr>
<tr><td><mark data-q="101-29,108-45">Q-switched（circuit quality switch）</mark></td><td>Resonator 加 optical polarizer 與 nonlinear crystal：先加電壓阻斷振盪讓 excited atoms 累積到最大，再於 ns 內關掉電壓 → 極強脈衝</td><td><mark data-q="101-29,108-45"><strong class="ex-n">ns 到 ps</strong></mark></td></tr>
</tbody>
</table>
<p class="ex-cite">p.3823–3824。</p>
<aside class="ex-trap"><strong>易錯</strong>Q-switched = 奈秒／皮秒級，用於色素與刺青；除毛用的是 <strong>long-pulsed（ms）</strong> alexandrite、diode、Nd:YAG（見 Table 208-1、208-2）。<span class="ex-ref">p.3824、p.3821、p.3829</span></aside>
</section>

<section class="ex-note" id="ipl">
<h2>3. Intense Pulsed Light（強脈衝光，IPL）</h2>
<ul>
<li><mark data-q="104-46">IPL <strong>不是雷射</strong>：flashlamp 發出 <strong>noncoherent</strong>、寬頻（broad spectrum）光</mark>，可調整 wavelength、fluence、pulse duration。<span class="ex-ref">p.3824</span></li>
<li>波長範圍約 <mark data-q="104-46"><strong class="ex-n">420 nm</strong> 到 far-infrared 約 <strong class="ex-n">1200 nm</strong></mark>。<span class="ex-ref">p.3824</span></li>
<li><mark data-q="105-25"><strong>Cutoff filter</strong> 只讓<strong>長於</strong>門檻值的波長通過</mark>，以不同 filter 與 handpiece「tune」到想要的 chromophore 與膚色。<span class="ex-ref">p.3824</span></li>
<li>例：<strong class="ex-n">560-nm filter</strong> 治療 vascular lesions（讓 &gt;560 nm 通過，對應血管吸收峰 <strong class="ex-n">585–595 nm</strong>）；<strong>較長的 cutoff filter</strong> 用於深膚色者的色素治療。<span class="ex-ref">p.3824</span></li>
<li>Fig. 208-8：<strong class="ex-n">500-nm</strong> cut-off 與 oxyhemoglobin 吸收重疊；<strong class="ex-n">650-nm</strong> cut-off 與 melanin 吸收重疊。<span class="ex-ref">p.3827</span></li>
<li>IPL applicator 透過 ultrasonic gel 直接接觸皮膚；radiant exposure 由 applicator 大小與能量決定。<span class="ex-ref">p.3824</span></li>
<li>寬頻光的吸收較複雜（不同波長被不同 chromophore 吸收），因此需要 cut-off filter。<span class="ex-ref">p.3826</span></li>
<li>極高強度＋極短脈衝造成的 ablation、explosion <strong>只有雷射能做到，IPL 不行</strong>。<span class="ex-ref">p.3827</span></li>
</ul>
<aside class="ex-trap"><strong>易錯</strong>IPL 波長範圍各章寫法不同：ch208 為 420–1200 nm（p.3824）；ch209（p.3836）、ch210（p.3848）為約 500–1200 nm；ch212 治療 telangiectasia 為 515–1200 nm（p.3890）。</aside>
</section>

<section class="ex-note" id="parameters">
<h2>4. Basic Parameters of Optical Radiation（光學參數）</h2>
<table class="ex-table">
<thead><tr><th scope="col">Parameter</th><th scope="col">Unit</th></tr></thead>
<tbody>
<tr><td>Energy</td><td>Joule（J）</td></tr>
<tr><td>Optical power</td><td>Watt（W）</td></tr>
<tr><td>Intensity（irradiance）</td><td>W/cm²</td></tr>
<tr><td>Radiant exposure（fluence）</td><td>J/cm²</td></tr>
<tr><td>Exposure time</td><td>second（s）</td></tr>
<tr><td>Irradiated area</td><td>cm²</td></tr>
</tbody>
</table>
<p class="ex-cite">p.3824。</p>
<ul>
<li><strong>Fluence（radiant exposure）</strong>是最常調整的參數 = <strong>intensity × exposure time</strong>；由 spot size 與光束能量決定。<span class="ex-ref">p.3824–3825</span></li>
<li>Pulsed radiation 的 fluence 約 <strong class="ex-n">1–400 J/cm²</strong>；cw 可超過此範圍。<span class="ex-ref">p.3825</span></li>
<li>Exposure time 從 <strong>picoseconds 到 seconds</strong>；pulsed 時 exposure time = 單一脈衝或一串脈衝。<span class="ex-ref">p.3824–3825</span></li>
<li><strong>E（J）= P（W）× t（s）</strong>：維持同樣能量時，功率降低就要延長脈衝，但組織效應不同（見第 7 節）。<span class="ex-ref">p.3828</span></li>
</ul>
</section>

<section class="ex-note" id="delivery">
<h2>5. Laser Energy Delivery（能量傳導系統）</h2>
<table class="ex-table">
<thead><tr><th scope="col">System</th><th scope="col">重點</th></tr></thead>
<tbody>
<tr><td>Articulated arms</td><td>中空相連管＋各接點反射鏡，保留 collimation 與 coherence；較笨重；<strong>CO2 雷射的主流</strong>，因 <strong>CO2 無法經 fiber optics 傳導</strong></td></tr>
<tr><td>Fiber optics</td><td>多為 <strong>quartz</strong> 細纖維，柔軟；多數 visible 與部分 invisible cw 雷射可傳；會損失能量與 coherence，限制聚焦；過度拉扯會斷裂</td></tr>
<tr><td>Micromanipulators</td><td>經顯微鏡耦合，精準移動；主要用於婦科（cervical lesions）與耳鼻喉（laryngeal、inner ear）</td></tr>
<tr><td>Fiber lasers</td><td>直接在 rare-earth 摻雜的玻璃纖維內產生雷射：<strong>erbium（1550 nm）</strong>、<strong>thulium（1927 nm）</strong>；多以 diode 為 pump；精準、可靠、體積小</td></tr>
</tbody>
</table>
<p class="ex-cite">p.3825。</p>
</section>

<section class="ex-note" id="tissue-interactions">
<h2>6. Laser–Tissue Interactions（雷射與組織交互作用）</h2>
<p><mark data-q="111-44">光到達組織時有 4 種反應：<strong>reflection、transmission、scattering、absorption</strong></mark>（Fig. 208-6）。<span class="ex-ref">p.3825</span></p>
<table class="ex-table">
<thead><tr><th scope="col">Interaction</th><th scope="col">定義與重點</th></tr></thead>
<tbody>
<tr><td>Absorption（吸收）</td><td><mark data-q="111-44">Photon 撞擊 target chromophore 後<strong>轉換為熱</strong>；雷射作用的根本取決於吸收</mark></td></tr>
<tr><td>Reflection（反射）</td><td>光束以斜角打到表面時部分彈開；<mark data-q="111-44,114-21">因 stratum corneum 的反射特性，即使完全垂直照射仍有約 <strong class="ex-n">5%</strong> 反射 → 即使技術完美仍<strong>必須戴護目鏡</strong></mark></td></tr>
<tr><td>Scattering（散射）</td><td><mark data-q="111-44">光穿過角質層後，在組織內碰到小分子而偏折；改變焦點、增加光在組織內的空間分布（擴大有效照射面積）</mark>；<mark data-q="110-29"><strong>短波長較易發生</strong></mark>。散射體大小：數 nm（小胞器、細胞膜）、數 µm（大胞器、細胞、collagen fibers）到數百 µm（hair follicle、sweat glands）</td></tr>
<tr><td>Transmission（穿透）</td><td>未被 chromophore 吸收而傳到更深層；<mark data-q="111-44,110-29"><strong>長波長與大 spot size</strong> 較易發生</mark></td></tr>
</tbody>
</table>
<p class="ex-cite">p.3825–3826。</p>
<ul>
<li>穿透深度：UVB（約 300 nm）只有零點幾 mm；infrared 可達數 mm。<span class="ex-ref">p.3826</span></li>
<li>但波長 &gt;約 <strong class="ex-n">1100 nm</strong> 時，因被皮膚中的水吸收，穿透深度隨波長增加的趨勢<strong>反轉</strong>。<span class="ex-ref">p.3826</span></li>
<li>At-a-glance：<mark data-q="110-29,115-30">在 visible spectrum 內<strong>波長越長穿透越深</strong></mark>；<mark data-q="110-29"><strong>spot size 越大穿透越深、散射越少</strong></mark>。<span class="ex-ref">p.3820</span></li>
</ul>
<aside class="ex-trap"><strong>易錯</strong>光穿過 stratum corneum 後在組織內碰到小分子而偏折，稱為 scattering。Stratum corneum 垂直照射仍約 5% reflection，因此即使技術完美仍需護目鏡。穿透深度隨波長增加的趨勢在約 1100 nm 以上反轉，因被皮膚中的水吸收。<span class="ex-ref">p.3825–3826</span></aside>
</section>

<section class="ex-note" id="effects">
<h2>7. Types of Effects &amp; Thermal Damage（作用型式與熱效應）</h2>
<table class="ex-table">
<thead><tr><th scope="col">Effect</th><th scope="col">機轉</th><th scope="col">例子</th></tr></thead>
<tbody>
<tr><td>Photochemical</td><td>極低能量；photons 被吸收後引發化學反應</td><td>Low-level laser therapy 治療落髮（推測被 mitochondria 吸收、活化 respiratory chain）</td></tr>
<tr><td>Photoacoustic／photomechanical（photodisruptive）</td><td>高能量 photons 被色素吸收，在顆粒內產生 acoustic waves 而使其碎裂</td><td><strong>ns 或 ps 雷射</strong>治療 pigmented lesions 與 tattoos</td></tr>
<tr><td>Photothermal</td><td>多數雷射所依賴；光能被 chromophore 吸收轉為熱，直接傷害鄰近細胞與結構；需相對高能量</td><td>血管、除毛、換膚</td></tr>
</tbody>
</table>
<p class="ex-cite">p.3826–3827。</p>
<h3>Temperature and tissue effect（溫度與組織反應，Fig. 208-9）</h3>
<table class="ex-table">
<thead><tr><th scope="col">Temperature</th><th scope="col">Tissue effect</th></tr></thead>
<tbody>
<tr><td><strong class="ex-n">&lt;50°C</strong></td><td>Reversible thermal damage、local vasodilation、inflammatory cascade 活化</td></tr>
<tr><td><strong class="ex-n">50–100°C</strong></td><td>Irreversible coagulation／protein denaturation；即使只維持 <strong class="ex-n">1 ms</strong> 也造成 coagulative necrosis</td></tr>
<tr><td><mark data-q="104-46"><strong class="ex-n">&gt;100°C</strong></mark></td><td><mark data-q="104-46">Tissue vaporization</mark>，產生含水蒸氣與組織成分的 plume</td></tr>
</tbody>
</table>
<p class="ex-cite">p.3827–3828。</p>
<ul>
<li>吸收後 target 內溫度上升，同時部分熱流向鄰近組織，限制最高溫度。熱傷害範圍取決於 wavelength、intensity 與 exposure duration。<span class="ex-ref">p.3827</span></li>
<li>短 CO2 脈衝快速加熱 → 迅速氣化，形成精準小洞、鄰近熱傷害極小。<span class="ex-ref">p.3827</span></li>
<li>能量夠高時可在組織深處形成 steam → explosion 與機械性傷害；<strong>Nd:YAG</strong> 穿透深，可產生 deep-seated steam cavities → tissue explosion 與 ulceration。<span class="ex-ref">p.3827</span></li>
<li>通則：<strong>intensity 越高、pulse 越短 → target 內最高溫越高</strong>；調整兩者可達到 coagulation、vaporization 或 explosion。<span class="ex-ref">p.3827–3828</span></li>
<li>High power＋short pulse → <strong>較多 vaporization、較少周邊 coagulative necrosis</strong>；lower power＋longer pulse → 較少 vaporization、氣化邊緣較多 coagulative necrosis（Fig. 208-10）。<span class="ex-ref">p.3828</span></li>
</ul>
</section>

<section class="ex-note" id="wavelength">
<h2>8. Wavelength &amp; Chromophores（波長與吸收體）</h2>
<ul>
<li>皮膚主要 chromophores（依位置深度順序）：<strong>water、melanin、hemoglobin</strong>。<span class="ex-ref">p.3829</span></li>
<li>單色雷射依各 chromophore 在該波長的 absorption coefficient 被吸收（Fig. 208-7）。<span class="ex-ref">p.3826</span></li>
</ul>
<table class="ex-table">
<thead><tr><th scope="col">Laser</th><th scope="col">Wavelength</th><th scope="col">Chromophore（吸收體）重點</th></tr></thead>
<tbody>
<tr><td><mark data-q="104-46,106-31">CO2</mark></td><td><mark data-q="104-46,106-31"><strong class="ex-n">10,600 nm</strong></mark></td><td><mark data-q="104-46">被 tissue water 吸收，穿透 <strong class="ex-n">&lt;0.1 mm</strong></mark>；大 spot＋低 power density 或聚焦高 power density；<mark data-q="106-31">可氣化、切割組織<strong>同時凝固血管</strong></mark></td></tr>
<tr><td><mark data-q="101-29,106-31">Er:YAG</mark></td><td><mark data-q="101-29,106-31"><strong class="ex-n">2940 nm</strong></mark></td><td>同樣優先被 water 吸收</td></tr>
<tr><td>Argon-ion</td><td>488、514 nm</td><td>Hemoglobin 與 melanin 都會吸收</td></tr>
<tr><td><mark data-q="115-30">KTP（frequency-doubled Nd:YAG）</mark></td><td>532 nm</td><td><mark data-q="115-30">Hemoglobin 與 melanin 都會吸收；優先與 oxyhemoglobin 作用</mark></td></tr>
<tr><td><mark data-q="115-30">Pulsed dye（PDL）</mark></td><td>585–595（–600）nm</td><td><mark data-q="115-30">Hemoglobin 與 melanin 都會吸收；優先與 oxyhemoglobin 作用</mark></td></tr>
<tr><td><mark data-q="104-48">Ruby</mark></td><td>694 nm</td><td><mark data-q="104-48">主要被 <strong>melanin</strong> 吸收</mark>，少量 hemoglobin 吸收</td></tr>
<tr><td><mark data-q="104-48">Alexandrite</mark></td><td>755 nm</td><td><mark data-q="104-48">優先被 melanin 吸收 → pigmented lesions 與 hair</mark></td></tr>
<tr><td>Diode</td><td>約 810 nm</td><td>Ruby、alexandrite、diode 較少被 oxyhemoglobin 吸收，較適合 benign pigmented lesions 與除毛</td></tr>
<tr><td>Nd:YAG</td><td>1064 nm</td><td><strong>沒有特定 chromophore</strong>，所有皮膚 chromophore 吸收都很少（hemoglobin、melanin 吸收少於其他可見光）；高 fluence 下可治療色素或血管病灶，cw 可做非特異凝固</td></tr>
<tr><td>Nonablative（fractional）</td><td>1440、1540、1550、1565、1927 nm</td><td>以 dermal tissue（water）為標的 → dermal collagen bulk heating，避免表皮傷害</td></tr>
</tbody>
</table>
<p class="ex-cite">p.3826、p.3829。</p>
<aside class="ex-trap"><strong>易錯</strong>內文 Er:YAG 為 <strong>2940 nm</strong>、CO2 為 <strong>10,600 nm</strong>，兩者都被 water 吸收；Fig. 208-7 圖中標示為 Er:YAG 2960 nm、CO2 11600 nm，與內文不同。Ruby（694 nm）主要被 melanin 吸收，少量 hemoglobin 吸收；alexandrite（755 nm）優先被 melanin 吸收，用於 pigmented lesions 與 hair。<span class="ex-ref">p.3827、p.3829</span></aside>
<h3>Table 208-1 Commonly used dermatologic lasers（常用皮膚科雷射）</h3>
<table class="ex-table">
<thead><tr><th scope="col">Laser（wavelength）</th><th scope="col">Target／effect</th><th scope="col">Mode</th><th scope="col">Applications</th></tr></thead>
<tbody>
<tr><td><mark data-q="104-46">Excimer（<strong class="ex-n">308 nm</strong>）</mark></td><td>DNA、proteins；photochemical</td><td>Pulsed（µs）</td><td><mark data-q="104-46">Comparable to <strong>narrow-band UVB 311</strong></mark></td></tr>
<tr><td>Argon（488/514 nm）</td><td>Vascular：semiselective coagulation；Tissue：coagulation</td><td>Pulsed（ms）</td><td>Telangiectases、spider nevi、venous lakes；syringoma、xanthelasma、epidermal nevi</td></tr>
<tr><td>KTP（532 nm）</td><td>Vascular：selective coagulation</td><td>Pulsed（ms）</td><td>Telangiectases、spider nevi、venous lakes</td></tr>
<tr><td><mark data-q="105-11,105-25,108-45,109-38">Frequency-doubled Nd:YAG（532 nm）</mark></td><td>Pigment／tattoos：selective fast heating（explosion）</td><td>Pulsed（ns、ps）</td><td>Ephelides、lentigines、<mark data-q="105-11,105-25,108-45,109-38">tattoos（<strong>red</strong>）</mark></td></tr>
<tr><td><mark data-q="101-29,108-45">Flashlamp-pumped pulsed dye（585–600 nm）</mark></td><td>Vascular：selective coagulation</td><td>Pulsed（ms）</td><td><mark data-q="101-29,108-45"><strong>Port-wine stains</strong></mark>、telangiectases、rosacea、spider nevi；scars、keloids、warts、photoaging</td></tr>
<tr><td><mark data-q="101-29,103-26,105-11,109-38">Ruby（694 nm）</mark></td><td>Pigment／tattoos：selective fast heating（explosion）</td><td>Pulsed（ns、ps）</td><td>Benign melanin-containing lesions、<mark data-q="105-11,109-38">tattoos（black、blue、green）</mark>、<mark data-q="101-29,103-26">dermal melanocytoses</mark></td></tr>
<tr><td><mark data-q="101-29,108-45">Alexandrite（755 nm）</mark></td><td>Vascular（selective coagulation）／Tissue</td><td><mark data-q="101-29,108-45">Pulsed（<strong>ms</strong>）</mark></td><td>Large vessels（leg veins、hypertrophic PWS）；<mark data-q="101-29,108-45"><strong>hair removal</strong></mark></td></tr>
<tr><td>Alexandrite（755 nm）</td><td>Pigment／tattoos：selective fast heating（explosion）</td><td><mark data-q="101-29,108-45">Pulsed（<strong>ns、ps</strong>）</mark></td><td>Benign melanin-containing lesions、tattoos（black、blue、green）、dermal melanocytoses</td></tr>
<tr><td>Diode（810 nm）</td><td>Vascular（selective coagulation）／Tissue</td><td>Pulsed（ms）</td><td>Large vessels（leg veins、hypertrophic PWS）；hair removal</td></tr>
<tr><td>Nd:YAG（1064 nm）</td><td>Vascular：unspecific coagulation</td><td>cw</td><td>Vascular malformations、tumors</td></tr>
<tr><td>Nd:YAG（1064 nm）</td><td>Vascular（selective coagulation）／Tissue</td><td>Pulsed（ms）</td><td>Large vessels（leg veins、hypertrophic PWS）；hair removal</td></tr>
<tr><td><mark data-q="109-38">Nd:YAG（1064 nm）</mark></td><td>Pigment：selective fast heating（explosion）</td><td>Pulsed（ns、ps）</td><td>Benign melanin-containing lesions、<mark data-q="109-38">tattoos（black、blue、green）</mark>、dermal melanocytoses</td></tr>
<tr><td>Erbium glass（1540 nm）</td><td>Tissue：selective coagulation（nonablative）</td><td>Pulsed（ms）</td><td>Skin remodeling、photoaging</td></tr>
<tr><td>Diode（1450–1550 nm）</td><td>Tissue：selective coagulation</td><td>Pulsed（ms）</td><td>Skin remodeling、photoaging</td></tr>
<tr><td>Thulium（1927 nm）</td><td>Tissue：selective coagulation（nonablative）</td><td>Pulsed（ms）</td><td>Skin remodeling、photoaging</td></tr>
<tr><td><mark data-q="101-29">Er:YAG（2940 nm）</mark></td><td>Tissue：selective fast heating（ablation）</td><td>Pulsed（ms）</td><td><mark data-q="101-29">Skin resurfacing、<strong>epidermal ablation</strong></mark></td></tr>
<tr><td>CO2（10,600 nm）</td><td>Tissue：nonspecific coagulation（vaporization）</td><td>cw</td><td>Vaporization of tissue</td></tr>
<tr><td>CO2（10,600 nm）</td><td>Tissue：selective fast heating ablation</td><td>Pulsed（ms）</td><td>Skin resurfacing、epidermal ablation</td></tr>
</tbody>
</table>
<p class="ex-cite">Table 208-1，p.3821。</p>
<aside class="ex-trap"><strong>易錯</strong>Table 208-1 中同一波長依 pulse duration 用途不同：alexandrite、Nd:YAG 的 <strong>ms</strong> 脈衝列為 large vessels 與 hair removal，<strong>ns、ps</strong> 脈衝列為 pigmented lesions 與 tattoos。Tattoos（red）列在 532 nm；ruby 列 tattoos（black、blue、green）。Table 208-1 把 Nd:YAG 1064 nm 也列為 tattoos（black、blue、green）；<mark data-q="109-38">ch210 Table 210-1 的 blue and green 為 QS alexandrite 755、QS ruby 694 nm，QS Nd:YAG 1064 nm 列在 black／dark blue</mark>。<span class="ex-ref">p.3821、p.3853</span></aside>
</section>

<section class="ex-note" id="selective-photothermolysis">
<h2>9. Selective Photothermolysis（選擇性光熱分解）</h2>
<ul>
<li><mark data-q="110-29">1980 年代由 <strong>Anderson 與 Parrish</strong> 提出（Science <strong class="ex-n">1983</strong>）</mark>；實驗用 <strong class="ex-n">577 nm</strong> 治療血管、<strong class="ex-n">351 nm</strong> 治療色素。<span class="ex-ref">p.3829</span>（1983 年見 ref 17，p.3833；ch210 p.3846）</li>
<li>兩個關鍵：①選擇能被 target chromophore 吸收的 <strong>wavelength</strong>；②正確的 <strong>pulse duration</strong> 讓熱侷限在 target（spatial confinement of heat）。<span class="ex-ref">p.3829</span></li>
<li><mark data-q="110-29">Pulse duration（exposure time）<strong>短於</strong> thermal relaxation time → 周邊組織傷害最小</mark>；內文另寫 pulse duration 應與 TRT「comparable」。<span class="ex-ref">p.3829</span></li>
<li><strong>Thermal relaxation time（TRT, tR）</strong>：被照射組織<strong>冷卻到加熱溫度一半</strong>所需的時間。<span class="ex-ref">p.3829</span></li>
<li><mark data-q="110-29"><strong>tR = ρc/(16k) × D²</strong>（ρ、c、k 為 target 的熱學參數，D 為直徑）；TRT 約與 target 平均直徑的<strong>平方成正比</strong></mark>。<span class="ex-ref">p.3829</span></li>
<li><mark data-q="110-29">Chromophore 越大 → 需要的 pulse duration 越長</mark>、整體加熱越多。<span class="ex-ref">p.3829</span></li>
<li>Pulse 長於 TRT → 過多熱流到 dermis，造成不必要的副作用（Fig. 208-11）。<span class="ex-ref">p.3829</span></li>
</ul>
<aside class="ex-trap"><strong>易錯</strong>TRT 約與 target 平均直徑的<strong>平方成正比</strong>。Pulse duration 短於 TRT（內文另寫 comparable to TRT）可使周邊傷害最小；長於 TRT 會使過多熱流到 dermis。<span class="ex-ref">p.3829</span></aside>
<h3>Table 208-2 Target chromophores, size, and pulse duration（標的大小與脈衝時間）</h3>
<table class="ex-table">
<thead><tr><th scope="col">Target</th><th scope="col">Approximate size</th><th scope="col">Pulse duration</th></tr></thead>
<tbody>
<tr><td>Blood vessels（小血管）</td><td><strong class="ex-n">50–150 µm</strong></td><td><strong>ms</strong></td></tr>
<tr><td><mark data-q="101-29">Hair follicles</mark></td><td><mark data-q="101-29"><strong class="ex-n">0.02–0.2 mm</strong>（內文；Table 208-2 寫 0.02–0.2 µm）</mark></td><td><mark data-q="101-29"><strong class="ex-n">10–50 ms</strong></mark></td></tr>
<tr><td>Melanocytes</td><td>數 µm（平均 <strong class="ex-n">7 µm</strong>）</td><td>ms 到 ns</td></tr>
<tr><td>Melanosomes</td><td><strong class="ex-n">1–1.5 µm</strong>（表格寫 1.5 µm）</td><td><strong>ns 到 ps</strong></td></tr>
<tr><td>Tattoo pigment particles</td><td>平均 <strong class="ex-n">100 nm（0.1 µm）</strong></td><td><strong>ns 到 ps</strong></td></tr>
</tbody>
</table>
<p class="ex-cite">Table 208-2，p.3829；內文 p.3829–3830。</p>
<ul>
<li>小血管（50–150 µm）凝固需 ms 級脈衝：先只升高血管內溫度，熱開始擴散到 dermis 時就應終止脈衝；leg veins 等大血管使用同樣範圍的 pulse duration。<span class="ex-ref">p.3829</span></li>
</ul>
<aside class="ex-trap"><strong>易錯</strong>Hair follicle 大小：Table 208-2 寫「0.02–0.2 µm」，內文寫 <strong>0.02–0.2 millimeters</strong>，以 10–50 ms 脈衝為標的。<span class="ex-ref">p.3829–3830</span></aside>
</section>

<section class="ex-note" id="fractional">
<h2>10. Fractional Photothermolysis（分段式光熱分解）</h2>
<ul>
<li>背景：1980 年代末到 1990 年代 ablative lasers（CO2、erbium）治療光老化與鬆弛效果顯著，但恢復期長、副作用嚴重；舊式 nonablative 效果不足 → 發展出 fractional photothermolysis。<span class="ex-ref">p.3830</span></li>
<li>在治療區內產生空間分布的柱狀微熱傷害，稱 <strong>microscopic treatment zones（MTZs）</strong>，柱間保留正常皮膚。<span class="ex-ref">p.3830</span></li>
<li>效果：較深入 dermis、controlled denaturation、<strong>transepidermal elimination</strong> of coagulated debris、reactive collagen remodeling，同時維持表皮完整、縮短癒合、減少副作用。<span class="ex-ref">p.3830</span></li>
</ul>
<table class="ex-table">
<thead><tr><th scope="col">Type</th><th scope="col">Lasers</th><th scope="col">特點</th></tr></thead>
<tbody>
<tr><td>Ablative fractional</td><td>CO2、erbium</td><td>表皮與真皮細柱狀 controlled vaporization；效果較明顯</td></tr>
<tr><td>Nonablative fractional</td><td><strong class="ex-n">1440、1540、1550、1565、1927 nm</strong></td><td>熱集中在 dermis，表皮相對或完全保留；耐受性佳、副作用少、癒合快，但效果不如 ablative；比舊式 nonfractionated nonablative（只造成均勻一層真皮加熱）好</td></tr>
</tbody>
</table>
<p class="ex-cite">p.3830。</p>
<ul>
<li>適應症：photoaging、acne scarring、traumatic scarring、skin laxity、dyschromias；也開啟 <strong>laser-assisted topical drug delivery</strong>。<span class="ex-ref">p.3830</span></li>
<li>Fractional photothermolysis 由 Manstein 等人於 <strong class="ex-n">2004</strong> 年首次報告。<span class="ex-ref">p.3846（ch210）</span></li>
</ul>
</section>

<section class="ex-note" id="cooling">
<h2>11. Skin Cooling（皮膚冷卻）</h2>
<ul>
<li>目的：photons 要穿過會吸收光的表皮，dermis 的熱也會回傳表皮 → 冷卻保護表皮，同時讓 dermis 得到足夠熱量。<span class="ex-ref">p.3830</span></li>
<li>時機：<strong>precooling、parallel cooling、postcooling</strong>（治療前、中、後）。<span class="ex-ref">p.3830</span></li>
</ul>
<table class="ex-table">
<thead><tr><th scope="col">Type</th><th scope="col">Methods</th><th scope="col">重點</th></tr></thead>
<tbody>
<tr><td>Contact cooling（又稱 bulk cooling）</td><td>Active：copper、sapphire tips；Passive：ice、aqueous gels</td><td>熱由皮膚傳到冷卻物；active tip 以 thermoelectric elements 或流動冷卻液主動移除熱</td></tr>
<tr><td>Noncontact cooling</td><td>Cryogen spray（liquid nitrogen）；pulsed cryogen spray（<strong>dynamic cooling device, DCD</strong>）；forced refrigerated air（Zimmer Cryo）</td><td>Liquid nitrogen 噴霧依賴操作者、不精準、有 cryonecrosis 風險；DCD 於雷射前一刻噴 <strong>1,1,1,2-tetrafluoroethane</strong>，<strong class="ex-n">−15°C</strong>，每發均勻可重複；forced cold air 可在前中後冷卻且不干擾光束，減少疼痛與熱傷害</td></tr>
</tbody>
</table>
<p class="ex-cite">Table 208-3，p.3830；p.3830–3831。</p>
</section>

<section class="ex-note" id="safety">
<h2>12. Laser Safety（雷射安全）</h2>
<h3>Regulation（法規）</h3>
<ul>
<li>規範機構：IEC、ANSI、CDRH（US FDA）、OSHA、CRCPD。<strong>ANSI Z136.3</strong> 為醫療雷射安全使用指引，由各機構強制執行。<span class="ex-ref">p.3831</span></li>
<li>醫療雷射<strong>必須指派 laser safety officer（LSO）</strong>：制定與執行安全規範、確認雷射分級、控制措施、medical surveillance。<span class="ex-ref">p.3832</span></li>
<li>Safety checklists：<strong>READ-DO</strong>（邊讀邊做）與 <strong>DO-CONFIRM</strong>（憑記憶做完後暫停核對）。<span class="ex-ref">p.3832</span></li>
</ul>
<h3>Skin safety（皮膚安全）</h3>
<ul>
<li><strong>Cutaneous injuries</strong> 是皮膚科雷射最常見的併發症，也是雷射相關訴訟最常見原因；最常被告的是 <strong>laser hair removal</strong>，其次是 rejuvenation（CO2 全換膚、fractional、IPL）。傷害包括 burns、scars、pigmentary changes。<span class="ex-ref">p.3831</span></li>
<li><mark data-q="114-21,115-30">深膚色降低風險：<strong>lower fluences、longer pulse durations、longer wavelengths 或 higher cutoff filters</strong></mark>；配合前、中、後冷卻。<span class="ex-ref">p.3831</span></li>
<li>Radiofrequency 裝置：避免用於 implantable devices 或 pacemakers 病人；刺青、金屬植入物、牙套處要小心。<span class="ex-ref">p.3831</span></li>
<li>風險：pigment-specific、vascular、nonablative 雷射較低；ablative 雷射較高（infection、scarring），fractional ablative 已大幅降低風險。<span class="ex-ref">p.3831</span></li>
</ul>
<aside class="ex-trap"><strong>易錯</strong>深膚色降低風險的是 <strong>lower</strong> fluences、<strong>longer</strong> pulse durations、<strong>longer</strong> wavelengths 或 <strong>higher</strong> cutoff filters（p.3831、Table 208-4）。</aside>
<h3>Eye safety（眼睛安全）</h3>
<ul>
<li><mark data-q="114-21,111-44">眼傷來自<strong>直接或間接（反射）</strong>雷射光</mark>；<strong class="ex-n">70%</strong> 眼傷源於未適當使用或未使用護目鏡。傷害類型依波長而定，嚴重度取決於能量、光束大小與暴露時間。<span class="ex-ref">p.3831</span></li>
</ul>
<table class="ex-table">
<thead><tr><th scope="col">Wavelength</th><th scope="col">吸收部位與傷害</th></tr></thead>
<tbody>
<tr><td><mark data-q="114-21"><strong class="ex-n">&lt;380 nm</strong></mark></td><td><mark data-q="114-21">被 <strong>cornea</strong> 的有機分子吸收</mark> → 角膜傷害或 cataract</td></tr>
<tr><td><mark data-q="114-21"><strong class="ex-n">380–1400 nm</strong></mark></td><td><mark data-q="114-21">穿過眼球被 <strong>retina</strong> 吸收</mark>；屈光介質聚焦使 irradiance 比角膜處高 <strong class="ex-n">&gt;10,000 倍</strong> → 低功率也能嚴重傷害視網膜</td></tr>
<tr><td><mark data-q="114-21"><strong class="ex-n">&gt;1000–1400 nm</strong></mark></td><td><mark data-q="114-21">被 water 吸收、穿透淺 → <strong>corneal</strong> injury</mark>（甚至 ablation、vaporization，thermal process）</td></tr>
</tbody>
</table>
<p class="ex-cite">p.3831。</p>
<table class="ex-table">
<thead><tr><th scope="col">Ocular injury type</th><th scope="col">Pulse duration／energy</th><th scope="col">機轉</th></tr></thead>
<tbody>
<tr><td><mark data-q="114-21">Thermal</mark></td><td><mark data-q="114-21"><strong>µs 到 s</strong></mark></td><td>Chromophore（如 retina melanin）吸收，產熱快於散熱 → 蛋白變性、細胞死亡</td></tr>
<tr><td><mark data-q="114-21">Mechanical</mark></td><td><mark data-q="114-21"><strong>ps 到 ns</strong></mark></td><td>快速升溫剝離電子 → <strong>plasma</strong>；水氣化產生 compressive pressure pulse（explosion）破壞周邊組織</td></tr>
<tr><td><mark data-q="114-21">Photochemical</mark></td><td><mark data-q="114-21">較低能量、較長時間（<strong>&gt;數秒</strong>）</mark></td><td>熱不足以造成熱傷害，但單一 photon 可打斷 nucleic acids 與 proteins 的鍵結；視網膜細胞可在數週內恢復，超過門檻則不可逆</td></tr>
</tbody>
</table>
<p class="ex-cite">p.3831–3832。</p>
<ul>
<li>Blink reflex 在 <strong class="ex-n">150–250 ms</strong> 內啟動，另有 aversion response（轉頭）；但多數雷射脈衝 <strong>&lt;250 ms</strong>，反射來不及保護；周邊視網膜受光時反而可能本能轉向光源。<span class="ex-ref">p.3832</span></li>
<li>不可見的長波長雷射（<strong>Nd:YAG、CO2</strong>）造成的傷害可能完全不被察覺。<span class="ex-ref">p.3832</span></li>
<li>護目鏡：以 filter 反射或吸收特定波長；以 <strong>optical density（OD）</strong>評級，<strong class="ex-n">OD ≥4</strong> 視為安全；需標示 wavelength range、laser mode、scale number；<strong>eye protection 是 device-specific</strong>，多波長機器換波長要換護目鏡。最大限制是人員不願配戴。<span class="ex-ref">p.3832</span></li>
<li>用於組織氣化時，<strong>plume 必須抽除</strong>以避免感染性物質（Table 208-4）。<span class="ex-ref">p.3831</span></li>
</ul>
<aside class="ex-trap"><strong>易錯</strong>380–1400 nm 傷 retina，&lt;380 nm 與 &gt;1000–1400 nm 傷 cornea。眼傷三型依 pulse duration 與能量區分：ps–ns = mechanical、µs–s = thermal、低能量長時間 = photochemical。<span class="ex-ref">p.3831–3832</span></aside>
<h3>Table 208-4 Principles of laser safety（雷射安全原則）</h3>
<ul>
<li>Set realistic expectations；詳細說明程序與副作用。</li>
<li>依 target chromophore 與膚色選擇正確裝置。</li>
<li>深膚色：lower fluences、longer pulse durations、longer wavelengths、higher cutoff filters。</li>
<li>Precooling、parallel cooling、postprocedural cooling。</li>
<li>Radiofrequency：避免 implantable devices／pacemakers。</li>
<li>Lowest risk：vascular、pigment-specific、nonablative；ablative 較高風險（infection、scarring）。</li>
<li>Appropriate、device-specific eye protection。</li>
<li>Tissue vaporization 時抽除 plume。</li>
</ul>
<p class="ex-cite">Table 208-4，p.3831。</p>
</section>

<section class="ex-note" id="clinical-correlations">
<h2>13. Clinical Correlations（ch209／210／212 與 McKee 交叉補充）</h2>
<p>本章歷屆題常混合後續章節的臨床應用，以下只列與考點相關的重點；詳見各章整理。</p>
<h3>Ablative lasers：Er:YAG vs CO2（ch209）</h3>
<ul>
<li><mark data-q="106-31">Er:YAG <strong class="ex-n">2940 nm</strong>，water absorption coefficient <strong class="ex-n">12,800 cm⁻¹</strong>，CO2 為 <strong class="ex-n">800 cm⁻¹</strong> → 被水吸收效率高 <strong class="ex-n">12–18 倍</strong></mark>；每 J/cm² 剝除 <strong class="ex-n">2–4 µm</strong>，熱壞死帶窄（<strong class="ex-n">20–50 µm</strong>）。<span class="ex-ref">p.3836</span></li>
<li><mark data-q="106-31">Short pulse（平均 <strong class="ex-n">250 µs</strong>）熱擴散少 → <strong>止血較差、術中出血較多</strong>，真皮穿透淺，妨礙深層治療與明顯 collagen contraction；但熱效應少帶來<strong>較短的術後恢復期</strong></mark>。<span class="ex-ref">p.3836</span></li>
<li>Modulated Er:YAG（短＋長 coagulative pulses）可達類似 CO2 的熱凝固帶，改善止血與膠原重塑。<span class="ex-ref">p.3836</span></li>
<li>Table 209-2 適合 laser skin resurfacing 的病灶包括 epidermal lesions：<mark data-q="101-29"><strong>seborrheic keratosis</strong></mark>、epidermal nevi、verrucae；另有 actinic keratoses、superficial dyschromia、atrophic scars、syringomas、xanthelasma 等。<span class="ex-ref">p.3838</span></li>
</ul>
<h3>Vascular lesions（ch210、ch212）</h3>
<ul>
<li><mark data-q="101-29,108-45">Flashlamp-pumped PDL（現多用 <strong class="ex-n">595 nm</strong>）是 <strong>port-wine stain 的 gold standard</strong></mark>；PDL 以 flashlamp 激發 rhodamine dye 產生黃光。<span class="ex-ref">p.3848</span></li>
<li><mark data-q="115-30">早期用 585 nm，較新的 PDL 改用 595 nm，因較長波長的 <strong>tissue penetration 較深</strong></mark>。<mark data-q="115-30">PWS 常用 <strong class="ex-n">0.45–1.5 ms</strong> 短脈衝 → purpura 持續約 <strong class="ex-n">1–2 週</strong></mark>；&gt;85% 病人至少淡化 50%。<span class="ex-ref">p.3849</span></li>
<li><mark data-q="104-48">PWS 位置：臉部<strong>外側</strong>較易清除，<strong>中央臉（cheeks、upper lip）較頑固</strong>；四肢（尤其腿）大病灶比軀幹、頭頸差；小病灶清除較完全</mark>。<span class="ex-ref">p.3849</span></li>
<li><mark data-q="115-30">KTP 與 Nd:YAG 有效治療單一 telangiectases（通常無 purpura）；大範圍 hypervascularity 用 PDL；extended pulse（<strong class="ex-n">≥6 ms</strong>）可 purpura-free</mark>。<span class="ex-ref">p.3850</span></li>
<li><mark data-q="115-30">Oxyhemoglobin 吸收峰 <strong class="ex-n">418、540、575–580 nm</strong></mark>（deoxyhemoglobin 550–560 nm）；PDL（585–595 nm）與 532 nm 對應這些峰；<mark data-q="105-25">IPL（515–1200 nm）也可治療 telangiectasias</mark>。<span class="ex-ref">p.3890</span></li>
<li><mark data-q="105-25">EVLA：原認為較短波長（<strong>810、940、980、1064 nm</strong>）以血中 hemoglobin 為標的，較長波長（<strong>1320、1470、1500 nm</strong> 以上）以靜脈壁的 water 為標的</mark>；新模型認為熱傷害主要來自光纖尖端極熱層經殘餘血液傳熱。<span class="ex-ref">p.3888</span></li>
</ul>
<h3>Pigmented lesions &amp; hair removal（ch210）</h3>
<ul>
<li><mark data-q="101-29,103-26,108-45">Nevus of Ota／Ito 色素較深，用穿透較深的 <strong>QS ruby、QS alexandrite、QS Nd:YAG</strong>，通常需多次治療</mark>。<span class="ex-ref">p.3851</span></li>
<li><mark data-q="101-29,108-45">除毛以 <strong>long-pulsed alexandrite（755 nm）</strong>與 diode（810 nm）屬最有效的裝置之一（among the most effective）</mark>；1064 nm Nd:YAG 對深膚色較安全；白色或金色毛髮缺乏 eumelanin 而無效。<span class="ex-ref">p.3851–3852</span></li>
<li><mark data-q="104-48">較長波長被表皮 melanin 吸收相對較少 → 降低 dyspigmentation 等併發症，但能量仍足以被毛囊深處含色素結構吸收</mark>（1064 nm Nd:YAG 讓深膚色者可安全除毛）；深膚色者用較長 pulse duration 加熱較慢，進一步降低 hypopigmentation／hyperpigmentation 風險。<span class="ex-ref">p.3852</span></li>
</ul>
<h3>Tattoo removal（ch210）</h3>
<ul>
<li>QS 雷射以 photoacoustic／photomechanical 作用，把 lysosome 內的墨水逐出到細胞外，再經 lymphatic 帶走；ns 脈衝正好配合次細胞大小的墨水顆粒。<span class="ex-ref">p.3852</span></li>
</ul>
<table class="ex-table">
<thead><tr><th scope="col">Ink color</th><th scope="col">Preferred lasers（Table 210-1）</th></tr></thead>
<tbody>
<tr><td><mark data-q="109-38">Black／dark blue</mark></td><td><mark data-q="109-38">QS Nd:YAG 1064、QS alexandrite 755、QS ruby 694 nm</mark></td></tr>
<tr><td><mark data-q="109-38,110-29">Blue and green</mark></td><td><mark data-q="109-38,110-29">QS alexandrite 755、QS ruby 694 nm</mark>（及 picosecond）</td></tr>
<tr><td><mark data-q="105-11,105-25,108-45,109-38">Red</mark></td><td><mark data-q="105-11,105-25,108-45,109-38">QS frequency-doubled Nd:YAG 532 nm</mark></td></tr>
<tr><td><mark data-q="109-38,110-29">Purple and orange</mark></td><td><mark data-q="109-38,110-29">532 nm 或 755 nm</mark></td></tr>
<tr><td><mark data-q="110-29">Yellow</mark></td><td><mark data-q="110-29">不易清除，可能對 QS 532 nm 有反應</mark></td></tr>
</tbody>
</table>
<p class="ex-cite">Table 210-1，p.3853；內文 p.3852。</p>
<ul>
<li><mark data-q="108-12"><strong>大、較新、多色、專業</strong>刺青最難清除；<strong>小、較舊、單色、業餘</strong>刺青通常反應較好（tend to respond best）</mark>。<span class="ex-ref">p.3854</span></li>
<li><mark data-q="103-32,105-25,108-12">部分墨水雷射後發生 oxidization reaction → <strong>立即變深</strong>；含 <strong>titanium dioxide</strong> 的墨水（常為<strong>白色或粉紅色</strong>）特別容易 → 先做小範圍測試</mark>。<span class="ex-ref">p.3854</span></li>
<li>對刺青墨水過敏（pruritus、induration、erythema）者避免 QS 雷射（可能擴散成局部或全身過敏）。<span class="ex-ref">p.3854</span></li>
<li>曾接受 systemic gold 治療者，QS 雷射可引起 localized <strong>chrysiasis</strong>（藍灰色）。<span class="ex-ref">p.3854</span> McKee：QS ruby laser 後可見典型 chrysiasis 病灶；組織為深層網狀真皮血管與汗腺周圍 macrophage 內的黑色小顆粒，cross-polarized light 呈 orange-red birefringence，無發炎反應。<span class="ex-ref ex-ref-mckee">McKee p.663</span></li>
</ul>
<aside class="ex-trap"><strong>易錯</strong>ch210 寫明特別容易在雷射後立即變深的是含 <strong>titanium dioxide</strong> 的墨水（常為白色或粉紅色）；治療已知高風險顏色時先做小範圍測試。<span class="ex-ref">p.3854</span></aside>
<h3>Tattoo reactions：pathology（McKee 補充）</h3>
<ul>
<li><mark data-q="105-11,108-12">刺青可發生 B-cell（較多）或 T-cell pseudolymphomatous reaction，<strong>最常見元凶為紅色</strong>色素，藍、綠、黑也有報告</mark>；數月到數年後出現侷限於刺青的丘疹、結節。<span class="ex-ref ex-ref-mckee">McKee p.657</span></li>
<li>組織：除 pseudolymphoma 特徵外，<mark data-q="105-11">刺青色素位於細胞外與 macrophages 內</mark>；少數有 lichenoid infiltrate。<span class="ex-ref ex-ref-mckee">McKee p.659</span></li>
<li><mark data-q="105-11,108-12">紅色刺青的 <strong>mercuric sulfide（cinnabar）</strong>可引起 lichenoid 與 granulomatous 反應</mark>；汞顆粒位於 macrophages 內與細胞外，分布在表淺血管周圍。<span class="ex-ref ex-ref-mckee">McKee p.664</span></li>
</ul>
</section>
