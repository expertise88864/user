/* ChenDermatologist article visual bundle. Loaded on demand by blog-shared.js. */
(function () {
  var DN = (window.DN = window.DN || {});

  function magCover(bg, body) {
    return '<svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">' +
      '<rect width="400" height="300" fill="' + (bg || '#dcd9d1') + '"/>' +
      body +
      '<rect width="400" height="300" fill="url(#mag-dots)" opacity="0.35"/>' +
      '</svg>';
  }
  DN.MAG_COVERS = {
    // Acne — face profile + comedones
    '痘痘': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<path d="M120 80 Q90 100 95 160 Q100 220 150 245 Q200 260 240 240 Q280 215 285 165 Q290 110 250 85 Q200 65 160 70 Q140 73 120 80 Z" fill="#fff" stroke="#2a2620" stroke-width="2.5"/>' +
      '<circle cx="160" cy="135" r="6" fill="#dc2626"/><circle cx="160" cy="135" r="2" fill="#fff"/>' +
      '<circle cx="220" cy="125" r="5" fill="#9a3412"/>' +
      '<circle cx="195" cy="170" r="4.5" fill="#9a3412"/>' +
      '<circle cx="240" cy="190" r="3.5" fill="#7a9285"/>' +
      '<circle cx="170" cy="200" r="3" fill="#dc2626"/>' +
      '<path d="M175 215 Q200 230 230 215" fill="none" stroke="#2a2620" stroke-width="2" stroke-linecap="round"/>' +
      '<text x="40" y="270" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">ACNE · 尋常痤瘡</text>' +
      '</g>'
    ),
    '痘疤': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<rect x="80" y="60" width="240" height="180" rx="6" fill="#fff" stroke="#2a2620" stroke-width="2"/>' +
      '<circle cx="140" cy="120" r="14" fill="none" stroke="#9a3412" stroke-width="2"/>' +
      '<circle cx="140" cy="120" r="4" fill="#7c2d12"/>' +
      '<path d="M200 100 L210 130 L196 135 Z" fill="#9a3412"/>' +
      '<path d="M250 145 Q260 155 250 165 Q240 155 250 145" fill="#7c2d12"/>' +
      '<path d="M165 175 Q180 165 195 175 Q180 185 165 175" fill="#a4b5a8"/>' +
      '<path d="M225 195 L240 195 L240 205 L225 205 Z" fill="#7a9285"/>' +
      '<text x="40" y="270" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">SCAR · 痘疤治療</text>' +
      '</g>'
    ),
    // Sunscreen — sun + UV waves
    '防曬': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<circle cx="310" cy="90" r="52" fill="#a4b5a8" opacity="0.85"/>' +
      '<g stroke="#7a9285" stroke-width="3" stroke-linecap="round">' +
      '<line x1="375" y1="90" x2="392" y2="90"/><line x1="245" y1="90" x2="228" y2="90"/>' +
      '<line x1="310" y1="25" x2="310" y2="42"/><line x1="310" y1="155" x2="310" y2="138"/>' +
      '<line x1="358" y1="42" x2="346" y2="54"/><line x1="262" y1="138" x2="274" y2="126"/>' +
      '<line x1="358" y1="138" x2="346" y2="126"/><line x1="262" y1="42" x2="274" y2="54"/>' +
      '</g>' +
      '<path d="M40 240 Q60 200 100 210 Q140 220 180 200 Q220 180 260 195 Q300 210 340 195 Q380 180 400 200 L400 300 L40 300 Z" fill="#4d6358" stroke="#2a2620" stroke-width="2"/>' +
      '<text x="40" y="270" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#fff">SUN · 紫外線</text>' +
      '</g>'
    ),
    // Eczema — patch with scratch lines
    '異膚': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<rect x="60" y="60" width="280" height="190" rx="14" fill="#fde68a" stroke="#9a3412" stroke-width="2.5" stroke-dasharray="4 3"/>' +
      '<circle cx="130" cy="140" r="6" fill="#dc2626"/>' +
      '<circle cx="180" cy="160" r="5" fill="#dc2626"/>' +
      '<circle cx="220" cy="130" r="7" fill="#dc2626"/>' +
      '<circle cx="260" cy="170" r="4" fill="#dc2626"/>' +
      '<circle cx="155" cy="195" r="5.5" fill="#dc2626"/>' +
      '<g stroke="#7c2d12" stroke-width="1.5" stroke-linecap="round" opacity="0.55">' +
      '<line x1="100" y1="100" x2="125" y2="115"/><line x1="200" y1="105" x2="225" y2="120"/><line x1="280" y1="180" x2="305" y2="195"/>' +
      '</g>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">ATOPIC · 異位性皮膚炎</text>' +
      '</g>'
    ),
    '兒童異膚': magCover('#cffafe',
      '<g filter="url(#mag-rough)">' +
      '<circle cx="200" cy="140" r="80" fill="#fde68a" stroke="#0c5159" stroke-width="2.5"/>' +
      '<circle cx="178" cy="130" r="3.5" fill="#0f172a"/>' +
      '<circle cx="222" cy="130" r="3.5" fill="#0f172a"/>' +
      '<path d="M180 160 Q200 175 220 160" fill="none" stroke="#0f172a" stroke-width="2" stroke-linecap="round"/>' +
      '<circle cx="160" cy="155" r="6" fill="#fee2e2" stroke="#dc2626" stroke-width="1.2"/>' +
      '<circle cx="245" cy="160" r="5" fill="#fee2e2" stroke="#dc2626" stroke-width="1.2"/>' +
      '<path d="M120 240 Q200 220 280 240" fill="none" stroke="#0c5159" stroke-width="2.5" stroke-linecap="round"/>' +
      '<text x="40" y="275" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#0c5159">PEDIATRIC · 兒童照護</text>' +
      '</g>'
    ),
    // Melasma / whitening — face with patches
    '肝斑': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<ellipse cx="200" cy="155" rx="100" ry="120" fill="#fff" stroke="#2a2620" stroke-width="2.5"/>' +
      '<path d="M150 110 Q165 95 185 105 Q175 130 150 125 Z" fill="#9a3412" opacity="0.7"/>' +
      '<path d="M215 110 Q235 95 250 110 Q240 130 215 125 Z" fill="#9a3412" opacity="0.7"/>' +
      '<path d="M170 175 Q195 165 230 175 Q210 195 175 195 Q160 185 170 175 Z" fill="#7c2d12" opacity="0.6"/>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">MELASMA · 肝斑</text>' +
      '</g>'
    ),
    '美白': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<rect x="140" y="50" width="60" height="200" rx="8" fill="#cffafe" stroke="#0c5159" stroke-width="2"/>' +
      '<rect x="155" y="40" width="30" height="20" fill="#0c5159"/>' +
      '<text x="170" y="160" font-family="Inter,sans-serif" font-size="22" font-weight="700" fill="#0c5159" text-anchor="middle">VC</text>' +
      '<rect x="220" y="80" width="50" height="170" rx="6" fill="#fff" stroke="#0c5159" stroke-width="2"/>' +
      '<text x="245" y="170" font-family="Inter,sans-serif" font-size="14" font-weight="700" fill="#0c5159" text-anchor="middle">TXA</text>' +
      '<circle cx="320" cy="130" r="28" fill="#fff" stroke="#0c5159" stroke-width="2"/>' +
      '<text x="320" y="135" font-family="Inter,sans-serif" font-size="13" font-weight="700" fill="#0c5159" text-anchor="middle">HQ</text>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">WHITENING · 美白成分</text>' +
      '</g>'
    ),
    // Rosacea — face with red flush
    '酒糟肌': magCover('#fee2e2',
      '<g filter="url(#mag-rough)">' +
      '<ellipse cx="200" cy="150" rx="100" ry="120" fill="#fff" stroke="#2a2620" stroke-width="2.5"/>' +
      '<ellipse cx="160" cy="170" rx="32" ry="22" fill="#fca5a5" opacity="0.7"/>' +
      '<ellipse cx="240" cy="170" rx="32" ry="22" fill="#fca5a5" opacity="0.7"/>' +
      '<ellipse cx="200" cy="180" rx="20" ry="15" fill="#dc2626" opacity="0.5"/>' +
      '<g stroke="#dc2626" stroke-width="1" opacity="0.7">' +
      '<line x1="145" y1="160" x2="165" y2="170"/><line x1="235" y1="160" x2="255" y2="170"/>' +
      '<line x1="155" y1="180" x2="170" y2="185"/><line x1="240" y1="180" x2="225" y2="185"/>' +
      '</g>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#7c2d12">ROSACEA · 玫瑰痤瘡</text>' +
      '</g>'
    ),
    '玫瑰斑': magCover('#fee2e2',
      '<g filter="url(#mag-rough)">' +
      '<ellipse cx="200" cy="150" rx="100" ry="120" fill="#fff" stroke="#2a2620" stroke-width="2.5"/>' +
      '<ellipse cx="200" cy="170" rx="60" ry="35" fill="#fca5a5" opacity="0.55"/>' +
      '<g fill="#7c2d12" opacity="0.7">' +
      '<circle cx="170" cy="155" r="1.2"/><circle cx="195" cy="160" r="1.4"/><circle cx="220" cy="155" r="1.2"/>' +
      '<circle cx="180" cy="175" r="1.2"/><circle cx="210" cy="180" r="1.4"/><circle cx="225" cy="175" r="1.2"/>' +
      '</g>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#7c2d12">DEMODEX · 蠕形蟎</text>' +
      '</g>'
    ),
    // Hair loss
    '落髮': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<path d="M100 200 Q100 110 200 90 Q300 110 300 200" fill="none" stroke="#2a2620" stroke-width="2.5" stroke-linecap="round"/>' +
      '<g stroke="#2a2620" stroke-width="1.5" stroke-linecap="round">' +
      '<line x1="125" y1="115" x2="120" y2="135"/><line x1="145" y1="100" x2="143" y2="125"/>' +
      '<line x1="170" y1="92" x2="170" y2="120"/><line x1="200" y1="88" x2="200" y2="118"/>' +
      '<line x1="230" y1="92" x2="232" y2="120"/><line x1="255" y1="100" x2="258" y2="125"/>' +
      '<line x1="278" y1="115" x2="282" y2="135"/>' +
      '</g>' +
      '<g stroke="#a4b5a8" stroke-width="1" stroke-linecap="round" opacity="0.6">' +
      '<line x1="60" y1="240" x2="68" y2="265"/><line x1="100" y1="245" x2="105" y2="270"/>' +
      '<line x1="320" y1="240" x2="328" y2="265"/><line x1="345" y1="250" x2="355" y2="275"/>' +
      '</g>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">HAIR LOSS · 雄性禿</text>' +
      '</g>'
    ),
    '圓禿': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<circle cx="200" cy="150" r="95" fill="#fff" stroke="#2a2620" stroke-width="2.5"/>' +
      '<circle cx="195" cy="135" r="32" fill="#fde68a" stroke="#9a3412" stroke-width="1.5"/>' +
      '<circle cx="160" cy="170" r="14" fill="#fde68a" stroke="#9a3412" stroke-width="1"/>' +
      '<g stroke="#2a2620" stroke-width="1.2" stroke-linecap="round">' +
      '<line x1="120" y1="100" x2="115" y2="120"/><line x1="240" y1="100" x2="245" y2="120"/>' +
      '<line x1="270" y1="135" x2="275" y2="155"/>' +
      '</g>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">ALOPECIA AREATA · 圓禿</text>' +
      '</g>'
    ),
    // Tinea / warts
    '足癬': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<path d="M120 70 Q90 110 110 200 Q130 270 200 270 Q260 270 280 220 Q295 175 270 130 Q250 95 200 80 Q160 70 120 70 Z" fill="#fff" stroke="#2a2620" stroke-width="2.5"/>' +
      '<circle cx="160" cy="130" r="12" fill="#fef3c7" stroke="#9a3412" stroke-width="1"/>' +
      '<circle cx="200" cy="155" r="10" fill="#fef3c7" stroke="#9a3412" stroke-width="1"/>' +
      '<circle cx="240" cy="135" r="9" fill="#fef3c7" stroke="#9a3412" stroke-width="1"/>' +
      '<g stroke="#16a34a" stroke-width="1.2" fill="none">' +
      '<path d="M150 200 Q160 195 165 205 Q170 215 180 205"/><path d="M210 195 Q220 190 225 200 Q230 210 240 200"/>' +
      '</g>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">TINEA · 皮癬菌</text>' +
      '</g>'
    ),
    '病毒疣': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<rect x="80" y="80" width="240" height="160" rx="14" fill="#fff" stroke="#2a2620" stroke-width="2.5"/>' +
      '<g fill="#a4b5a8" stroke="#4d6358" stroke-width="1.2">' +
      '<circle cx="140" cy="140" r="11"/><circle cx="180" cy="125" r="9"/>' +
      '<circle cx="220" cy="155" r="13"/><circle cx="260" cy="135" r="10"/>' +
      '<circle cx="170" cy="175" r="8"/><circle cx="240" cy="195" r="11"/>' +
      '</g>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">HPV · 病毒疣</text>' +
      '</g>'
    ),
    // Shingles
    '皮蛇': magCover('#fee2e2',
      '<g filter="url(#mag-rough)">' +
      '<path d="M40 150 Q90 90 150 150 Q210 210 270 150 Q330 90 390 150" fill="none" stroke="#dc2626" stroke-width="6" stroke-linecap="round"/>' +
      '<g fill="#fee2e2" stroke="#dc2626" stroke-width="2">' +
      '<circle cx="80" cy="125" r="9"/><circle cx="125" cy="155" r="8"/>' +
      '<circle cx="175" cy="180" r="9"/><circle cx="225" cy="170" r="8"/>' +
      '<circle cx="270" cy="155" r="9"/><circle cx="320" cy="125" r="8"/>' +
      '</g>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#7c2d12">SHINGLES · 帶狀皰疹</text>' +
      '</g>'
    ),
    // Urticaria / Prurigo
    '蕁麻疹': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<g fill="#fee2e2" stroke="#dc2626" stroke-width="2">' +
      '<ellipse cx="120" cy="120" rx="38" ry="26"/><ellipse cx="220" cy="100" rx="32" ry="22"/>' +
      '<ellipse cx="295" cy="155" rx="42" ry="28"/><ellipse cx="155" cy="195" rx="35" ry="22"/>' +
      '<ellipse cx="265" cy="220" rx="28" ry="18"/>' +
      '</g>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">URTICARIA · 蕁麻疹</text>' +
      '</g>'
    ),
    '結節性癢疹': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<g fill="#fed7aa" stroke="#9a3412" stroke-width="2">' +
      '<circle cx="120" cy="120" r="14"/><circle cx="180" cy="105" r="11"/><circle cx="240" cy="115" r="13"/>' +
      '<circle cx="290" cy="155" r="15"/><circle cx="150" cy="180" r="12"/><circle cx="220" cy="190" r="14"/>' +
      '<circle cx="280" cy="220" r="11"/><circle cx="160" cy="230" r="13"/>' +
      '</g>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#7c2d12">PRURIGO · 結節性癢疹</text>' +
      '</g>'
    ),
    // Psoriasis
    '乾癬': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<rect x="70" y="60" width="260" height="200" rx="6" fill="#fee2e2" stroke="#dc2626" stroke-width="2.5"/>' +
      '<g stroke="#fff" stroke-width="2.2">' +
      '<line x1="90" y1="90" x2="310" y2="90"/><line x1="90" y1="115" x2="310" y2="115"/>' +
      '<line x1="100" y1="140" x2="300" y2="140"/><line x1="90" y1="165" x2="310" y2="165"/>' +
      '<line x1="100" y1="190" x2="300" y2="190"/><line x1="90" y1="215" x2="310" y2="215"/>' +
      '<line x1="100" y1="240" x2="300" y2="240"/>' +
      '</g>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">PSORIASIS · 乾癬</text>' +
      '</g>'
    ),
    // HS
    '化膿性汗腺炎': magCover('#fee2e2',
      '<g filter="url(#mag-rough)">' +
      '<g fill="#fee2e2" stroke="#dc2626" stroke-width="2.5">' +
      '<circle cx="130" cy="140" r="22"/><circle cx="220" cy="120" r="26"/>' +
      '<circle cx="300" cy="160" r="20"/><circle cx="180" cy="220" r="24"/>' +
      '</g>' +
      '<g stroke="#9a3412" stroke-width="1.5" stroke-dasharray="3 3" fill="none">' +
      '<line x1="130" y1="140" x2="220" y2="120"/><line x1="220" y1="120" x2="300" y2="160"/>' +
      '<line x1="130" y1="140" x2="180" y2="220"/><line x1="220" y1="120" x2="180" y2="220"/>' +
      '</g>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#7c2d12">HS · 化膿性汗腺炎</text>' +
      '</g>'
    ),
    // Mpox
    '猴痘': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<g fill="#fef3c7" stroke="#9a3412" stroke-width="2">' +
      '<circle cx="120" cy="100" r="14"/><circle cx="200" cy="90" r="13"/><circle cx="280" cy="105" r="14"/>' +
      '<circle cx="155" cy="160" r="15"/><circle cx="245" cy="160" r="15"/>' +
      '<circle cx="115" cy="220" r="13"/><circle cx="200" cy="230" r="14"/><circle cx="285" cy="220" r="13"/>' +
      '</g>' +
      '<g fill="#9a3412">' +
      '<circle cx="120" cy="100" r="3"/><circle cx="200" cy="90" r="3"/><circle cx="280" cy="105" r="3"/>' +
      '<circle cx="155" cy="160" r="3"/><circle cx="245" cy="160" r="3"/>' +
      '<circle cx="115" cy="220" r="3"/><circle cx="200" cy="230" r="3"/><circle cx="285" cy="220" r="3"/>' +
      '</g>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#7c2d12">MPOX · 猴痘</text>' +
      '</g>'
    ),
    // Topical acids — tube
    '酸類': magCover('#cffafe',
      '<g filter="url(#mag-rough)">' +
      '<path d="M150 60 L250 60 L250 75 Q250 90 240 95 L240 245 Q240 260 220 260 L180 260 Q160 260 160 245 L160 95 Q150 90 150 75 Z" fill="#fff" stroke="#0c5159" stroke-width="2.5"/>' +
      '<rect x="170" y="50" width="60" height="14" fill="#0c5159"/>' +
      '<text x="200" y="155" font-family="Inter,sans-serif" font-size="20" font-weight="700" fill="#0c5159" text-anchor="middle">AHA</text>' +
      '<text x="200" y="180" font-family="Inter,sans-serif" font-size="14" fill="#0c5159" text-anchor="middle">/ BHA</text>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#0c5159">ACIDS · 外用酸類</text>' +
      '</g>'
    ),
    // Isotretinoin — pill
    '口服 A 酸': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<g transform="translate(200 150) rotate(-25)">' +
      '<rect x="-90" y="-25" width="180" height="50" rx="25" fill="#fde68a" stroke="#9a3412" stroke-width="2.5"/>' +
      '<rect x="-90" y="-25" width="90" height="50" rx="25" fill="#fef3c7" stroke="#9a3412" stroke-width="2.5"/>' +
      '<text x="-50" y="6" font-family="Inter,sans-serif" font-size="14" font-weight="700" fill="#9a3412" text-anchor="middle">10mg</text>' +
      '<text x="45" y="6" font-family="Inter,sans-serif" font-size="14" font-weight="700" fill="#9a3412" text-anchor="middle">A 酸</text>' +
      '</g>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#7c2d12">ISOTRETINOIN · 口服 A 酸</text>' +
      '</g>'
    ),
    // Topical steroids — tube
    '外用類固醇': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<path d="M155 60 L245 60 L245 75 Q245 88 235 92 L235 240 Q235 258 215 258 L185 258 Q165 258 165 240 L165 92 Q155 88 155 75 Z" fill="#fff" stroke="#4d6358" stroke-width="2.5"/>' +
      '<rect x="175" y="50" width="50" height="14" fill="#4d6358"/>' +
      '<rect x="170" y="100" width="60" height="40" fill="#a4b5a8"/>' +
      '<text x="200" y="125" font-family="Inter,sans-serif" font-size="13" font-weight="700" fill="#fff" text-anchor="middle">CLASS</text>' +
      '<text x="200" y="170" font-family="Inter,sans-serif" font-size="20" font-weight="700" fill="#0c5159" text-anchor="middle">I-VII</text>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">TOPICAL STEROID · 類固醇藥膏</text>' +
      '</g>'
    ),
    // Biologics — syringe
    '生物製劑': magCover('#cffafe',
      '<g filter="url(#mag-rough)">' +
      '<g transform="translate(60 145) rotate(-15)">' +
      '<rect x="0" y="-20" width="220" height="40" rx="6" fill="#fff" stroke="#0c5159" stroke-width="2.5"/>' +
      '<rect x="0" y="-20" width="100" height="40" fill="#a5f3fc"/>' +
      '<rect x="-30" y="-30" width="30" height="60" fill="#0c5159"/>' +
      '<line x1="220" y1="0" x2="270" y2="0" stroke="#0c5159" stroke-width="3"/>' +
      '<line x1="270" y1="-5" x2="270" y2="5" stroke="#0c5159" stroke-width="2"/>' +
      '<g stroke="#0c5159" stroke-width="1.2">' +
      '<line x1="20" y1="-22" x2="20" y2="-30"/><line x1="50" y1="-22" x2="50" y2="-32"/>' +
      '<line x1="80" y1="-22" x2="80" y2="-30"/><line x1="110" y1="-22" x2="110" y2="-32"/>' +
      '<line x1="140" y1="-22" x2="140" y2="-30"/></g>' +
      '</g>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#0c5159">BIOLOGICS · 生物製劑</text>' +
      '</g>'
    ),
    // Vitiligo — depigmented patches
    '白斑': magCover('#a4b5a8',
      '<g filter="url(#mag-rough)">' +
      '<rect x="60" y="60" width="280" height="200" rx="12" fill="#a4b5a8"/>' +
      '<g fill="#fff">' +
      '<ellipse cx="130" cy="125" rx="32" ry="22"/><ellipse cx="230" cy="115" rx="38" ry="26"/>' +
      '<ellipse cx="290" cy="180" rx="28" ry="22"/><ellipse cx="160" cy="200" rx="34" ry="24"/>' +
      '<ellipse cx="245" cy="220" rx="22" ry="16"/>' +
      '</g>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#fff">VITILIGO · 白斑</text>' +
      '</g>'
    ),
    // Targeted therapy — molecule
    '標靶藥物': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<g stroke="#0c5159" stroke-width="2" fill="#fff">' +
      '<circle cx="200" cy="150" r="22"/>' +
      '<circle cx="120" cy="100" r="18"/><circle cx="280" cy="100" r="18"/>' +
      '<circle cx="120" cy="200" r="18"/><circle cx="280" cy="200" r="18"/>' +
      '</g>' +
      '<g stroke="#0c5159" stroke-width="2">' +
      '<line x1="138" y1="115" x2="183" y2="138"/><line x1="262" y1="115" x2="217" y2="138"/>' +
      '<line x1="138" y1="185" x2="183" y2="162"/><line x1="262" y1="185" x2="217" y2="162"/>' +
      '</g>' +
      '<text x="200" y="156" font-family="Inter,sans-serif" font-size="13" font-weight="700" fill="#0c5159" text-anchor="middle">EGFR</text>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">TKI · 標靶藥物</text>' +
      '</g>'
    ),
    // FAQ — book/question
    '常見問題': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<rect x="100" y="70" width="200" height="180" rx="8" fill="#fff" stroke="#2a2620" stroke-width="2.5"/>' +
      '<line x1="200" y1="70" x2="200" y2="250" stroke="#2a2620" stroke-width="1.5"/>' +
      '<g stroke="#7a9285" stroke-width="1.5">' +
      '<line x1="115" y1="100" x2="185" y2="100"/><line x1="115" y1="120" x2="185" y2="120"/>' +
      '<line x1="115" y1="140" x2="170" y2="140"/>' +
      '<line x1="215" y1="100" x2="285" y2="100"/><line x1="215" y1="120" x2="285" y2="120"/>' +
      '<line x1="215" y1="140" x2="270" y2="140"/>' +
      '</g>' +
      '<text x="200" y="225" font-family="Noto Serif TC,Georgia,serif" font-size="50" font-weight="700" fill="#0c5159" text-anchor="middle">?</text>' +
      '<text x="40" y="280" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">FAQ · 常見問題</text>' +
      '</g>'
    ),
    // Cyst — round bump
    '粉瘤': magCover('#ebe4d8',
      '<g filter="url(#mag-rough)">' +
      '<path d="M40 230 Q40 200 80 200 L320 200 Q360 200 360 230" fill="#ebe4d8" stroke="#4d6358" stroke-width="2"/>' +
      '<ellipse cx="200" cy="200" rx="65" ry="50" fill="#fed7aa" stroke="#4d6358" stroke-width="2.5"/>' +
      '<circle cx="200" cy="180" r="3.5" fill="#9a3412"/>' +
      '<line x1="200" y1="170" x2="200" y2="180" stroke="#4d6358" stroke-width="1.5"/>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">CYST · 表皮囊腫</text>' +
      '</g>'
    ),
    // NHI — clipboard
    '健保規範': magCover('#cffafe',
      '<g filter="url(#mag-rough)">' +
      '<rect x="120" y="60" width="160" height="200" rx="8" fill="#fff" stroke="#0c5159" stroke-width="2.5"/>' +
      '<rect x="160" y="50" width="80" height="22" rx="4" fill="#0c5159"/>' +
      '<g stroke="#0c5159" stroke-width="1.5">' +
      '<line x1="135" y1="100" x2="265" y2="100"/><line x1="135" y1="125" x2="265" y2="125"/>' +
      '<line x1="135" y1="150" x2="240" y2="150"/><line x1="135" y1="175" x2="265" y2="175"/>' +
      '<line x1="135" y1="200" x2="220" y2="200"/></g>' +
      '<text x="200" y="240" font-family="Inter,sans-serif" font-size="22" font-weight="700" fill="#0c5159" text-anchor="middle">NHI</text>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#0c5159">NHI · 健保給付</text>' +
      '</g>'
    ),
    // Laser
    '雷射 / 光電': magCover('#dcd9d1',
      '<g filter="url(#mag-rough)">' +
      '<rect x="50" y="130" width="120" height="40" rx="4" fill="#a4b5a8" stroke="#2a2620" stroke-width="2"/>' +
      '<line x1="170" y1="150" x2="370" y2="150" stroke="#dc2626" stroke-width="6" stroke-linecap="round"/>' +
      '<g stroke="#dc2626" stroke-width="2" opacity="0.6">' +
      '<line x1="180" y1="140" x2="370" y2="140"/><line x1="180" y1="160" x2="370" y2="160"/></g>' +
      '<circle cx="370" cy="150" r="14" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#4d6358">LASER · 皮膚雷射</text>' +
      '</g>'
    ),
    // CTCL — lymphocyte
    '皮膚淋巴瘤': magCover('#fee2e2',
      '<g filter="url(#mag-rough)">' +
      '<g fill="#fff" stroke="#7c2d12" stroke-width="2">' +
      '<circle cx="140" cy="130" r="22"/><circle cx="220" cy="105" r="20"/><circle cx="290" cy="155" r="24"/>' +
      '<circle cx="170" cy="200" r="22"/><circle cx="260" cy="220" r="20"/></g>' +
      '<g fill="#9a3412">' +
      '<circle cx="140" cy="130" r="9"/><circle cx="220" cy="105" r="8"/><circle cx="290" cy="155" r="10"/>' +
      '<circle cx="170" cy="200" r="9"/><circle cx="260" cy="220" r="8"/></g>' +
      '<text x="40" y="285" font-family="Inter,sans-serif" font-size="13" letter-spacing="3" fill="#7c2d12">CTCL/MF · 皮膚淋巴瘤</text>' +
      '</g>'
    )
  };

  // Tag aliases — map DN.ARTICLES tags to MAG_COVERS keys
  DN.MAG_COVER_ALIAS = {
    '健保規範':     '健保規範',
    '結節性癢疹':   '結節性癢疹',
    '皮膚淋巴瘤':   '皮膚淋巴瘤'
  };
  DN.getMagCover = function (tag) {
    if (!tag) return DN.MAG_COVERS['常見問題'];
    var key = DN.MAG_COVER_ALIAS[tag] || tag;
    return DN.MAG_COVERS[key] || DN.MAG_COVERS['常見問題'];
  };

  // ─────────────────────────────────────────────────────────────────────
  // Article HERO SVG — inserts a large disease-themed illustration
  // immediately after the article H1 (and before the TLDR). Auto-keyed by
  // article tag from DN.ARTICLES.
  // ─────────────────────────────────────────────────────────────────────
  DN.injectArticleHero = function () {
    if (document.getElementById('dn-article-hero')) return;
    var slug = DN.currentSlug && DN.currentSlug();
    if (!slug) return;
    var meta = (DN.ARTICLES || []).find(function (a) { return a.slug === slug; });
    if (!meta) return;

    // Each hero is ~720x240, cream/teal palette, hand-drawn feel.
    // Wrapped in a <picture>-like figure that auto-resizes.
    var HEROES = {
      // Acne family
      '痘痘': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(60 30)"><circle cx="100" cy="100" r="90" fill="#fff" stroke="#4d6358" stroke-width="2.5"/>' +
        '<circle cx="80" cy="85" r="6" fill="#dc2626"/><circle cx="80" cy="85" r="2" fill="#fff"/>' +
        '<circle cx="120" cy="100" r="5" fill="#9a3412"/><circle cx="105" cy="125" r="4" fill="#9a3412"/>' +
        '<circle cx="135" cy="80" r="3" fill="#7a9285"/><path d="M75 145 Q100 160 125 145" fill="none" stroke="#4d6358" stroke-width="2" stroke-linecap="round"/>' +
        '</g><g transform="translate(380 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">皮膚科衛教</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">DERMATOLOGY · ACNE</text>' +
        '<line x1="0" y1="100" x2="240" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">尋常痤瘡 · Acne vulgaris</text>' +
        '</g></svg>',
      // Sunscreen / sun
      '防曬': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<defs><radialGradient id="sun-g" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#fef3c7"/><stop offset="100%" stop-color="#a4b5a8"/></radialGradient></defs>' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(120 120)"><circle r="55" fill="url(#sun-g)" stroke="#4d6358" stroke-width="2"/>' +
        '<g stroke="#4d6358" stroke-width="3" stroke-linecap="round">' +
        '<line x1="0" y1="-80" x2="0" y2="-65"/><line x1="0" y1="65" x2="0" y2="80"/>' +
        '<line x1="-80" y1="0" x2="-65" y2="0"/><line x1="65" y1="0" x2="80" y2="0"/>' +
        '<line x1="-56" y1="-56" x2="-46" y2="-46"/><line x1="46" y1="46" x2="56" y2="56"/>' +
        '<line x1="-56" y1="56" x2="-46" y2="46"/><line x1="46" y1="-46" x2="56" y2="-56"/></g></g>' +
        '<g transform="translate(280 60)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">防曬與光老化</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">UV PROTECTION · PHOTOAGING</text>' +
        '<line x1="0" y1="100" x2="280" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">SPF / PA · UVA / UVB / 可見光</text>' +
        '</g></svg>',
      // Eczema / atopic
      '異膚': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(40 50)"><path d="M20 110 Q30 50 90 40 Q160 30 220 70 L220 130 Q200 145 180 140 Q175 165 195 175 L20 175 Z" fill="#fde68a" stroke="#4d6358" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<circle cx="60" cy="100" r="3" fill="#dc2626"/><circle cx="100" cy="120" r="4" fill="#dc2626"/><circle cx="140" cy="105" r="3" fill="#dc2626"/><circle cx="170" cy="135" r="2.5" fill="#dc2626"/>' +
        '<circle cx="80" cy="135" r="2" fill="#dc2626"/><path d="M30 90 Q50 88 60 92" fill="none" stroke="#4d6358" stroke-width="1"/>' +
        '</g><g transform="translate(310 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">異位性皮膚炎</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">ATOPIC DERMATITIS</text>' +
        '<line x1="0" y1="100" x2="320" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">屏障受損 · 慢性發炎 · 強烈搔癢</text>' +
        '</g></svg>',
      // Psoriasis
      '乾癬': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(60 50)"><rect x="20" y="30" width="160" height="120" rx="6" fill="#fee2e2" stroke="#dc2626" stroke-width="2.5"/>' +
        '<line x1="40" y1="50" x2="160" y2="50" stroke="#fef3c7" stroke-width="3"/><line x1="35" y1="65" x2="155" y2="65" stroke="#fef3c7" stroke-width="3"/>' +
        '<line x1="42" y1="80" x2="162" y2="80" stroke="#fef3c7" stroke-width="3"/><line x1="38" y1="95" x2="158" y2="95" stroke="#fef3c7" stroke-width="3"/>' +
        '<line x1="40" y1="110" x2="160" y2="110" stroke="#fef3c7" stroke-width="3"/><line x1="44" y1="125" x2="154" y2="125" stroke="#fef3c7" stroke-width="3"/>' +
        '</g><g transform="translate(290 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">乾癬 / Psoriasis</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">IL-17 · IL-23 PATHWAY</text>' +
        '<line x1="0" y1="100" x2="340" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">紅斑 · 銀白鱗屑 · 系統性疾病</text>' +
        '</g></svg>',
      // Hair loss
      '落髮': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(60 40)"><path d="M40 140 Q40 50 130 50 Q220 50 220 140" fill="none" stroke="#4d6358" stroke-width="3" stroke-linecap="round"/>' +
        '<g stroke="#4d6358" stroke-width="1.6" stroke-linecap="round" opacity="0.9">' +
        '<line x1="60" y1="55" x2="55" y2="40"/><line x1="80" y1="50" x2="78" y2="35"/>' +
        '<line x1="100" y1="48" x2="100" y2="33"/><line x1="120" y1="48" x2="120" y2="32"/>' +
        '<line x1="140" y1="48" x2="140" y2="33"/><line x1="160" y1="50" x2="162" y2="35"/>' +
        '<line x1="180" y1="55" x2="185" y2="40"/></g>' +
        '<path d="M40 145 Q130 155 220 145" fill="none" stroke="#a4b5a8" stroke-width="2" stroke-dasharray="4 4"/>' +
        '</g><g transform="translate(290 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">落髮 / 圓禿</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">ALOPECIA · HAIR LOSS</text>' +
        '<line x1="0" y1="100" x2="320" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">雄性禿 / 圓禿 / 休止期落髮</text>' +
        '</g></svg>',
      // Melasma
      '肝斑 / 美白': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(50 30)"><circle cx="100" cy="100" r="85" fill="#fff" stroke="#4d6358" stroke-width="2.5"/>' +
        '<path d="M70 80 Q85 70 100 78 Q90 92 70 80 Z" fill="#9a3412" opacity="0.65"/>' +
        '<path d="M120 75 Q140 65 145 80 Q135 95 120 75 Z" fill="#7c2d12" opacity="0.55"/>' +
        '<circle cx="100" cy="120" r="4" fill="#9a3412" opacity="0.65"/>' +
        '<circle cx="80" cy="100" r="1.5" fill="#0f172a"/><circle cx="120" cy="100" r="1.5" fill="#0f172a"/>' +
        '</g><g transform="translate(290 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">肝斑 / 色素</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">MELASMA · PIGMENTATION</text>' +
        '<line x1="0" y1="100" x2="320" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">UV · 荷爾蒙 · 慢性發炎</text>' +
        '</g></svg>',
      // Rosacea
      '玫瑰斑': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(50 30)"><circle cx="100" cy="100" r="85" fill="#fee2e2" stroke="#dc2626" stroke-width="2.5"/>' +
        '<circle cx="80" cy="95" r="2" fill="#dc2626"/><circle cx="120" cy="95" r="2" fill="#dc2626"/>' +
        '<g stroke="#dc2626" stroke-width="1" stroke-linecap="round" opacity="0.6">' +
        '<line x1="65" y1="80" x2="78" y2="92"/><line x1="135" y1="80" x2="122" y2="92"/>' +
        '<line x1="60" y1="115" x2="80" y2="118"/><line x1="140" y1="115" x2="120" y2="118"/></g>' +
        '<circle cx="100" cy="120" r="2" fill="#dc2626"/></g>' +
        '<g transform="translate(290 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">玫瑰斑 / 酒糟</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">ROSACEA · DEMODEX</text>' +
        '<line x1="0" y1="100" x2="320" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">微血管擴張 · 反覆潮紅 · Demodex</text>' +
        '</g></svg>',
      // Urticaria
      '蕁麻疹': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(60 50)"><circle cx="50" cy="60" r="22" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '<circle cx="120" cy="100" r="32" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '<circle cx="200" cy="60" r="20" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '<circle cx="80" cy="140" r="18" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '<circle cx="180" cy="140" r="22" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '</g><g transform="translate(310 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">蕁麻疹</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">URTICARIA · CSU</text>' +
        '<line x1="0" y1="100" x2="320" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">急性 · 慢性 · 物理性 · 自體免疫</text>' +
        '</g></svg>',
      // Tinea
      '香港腳 / 灰指甲': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(60 60)"><path d="M40 30 Q60 10 110 15 Q150 20 160 60 L155 130 Q150 145 130 145 L40 145 Z" fill="#ebe4d8" stroke="#4d6358" stroke-width="2.5"/>' +
        '<circle cx="50" cy="20" r="9" fill="#ebe4d8" stroke="#4d6358" stroke-width="2"/>' +
        '<circle cx="68" cy="14" r="7" fill="#ebe4d8" stroke="#4d6358" stroke-width="2"/>' +
        '<circle cx="86" cy="11" r="6" fill="#ebe4d8" stroke="#4d6358" stroke-width="2"/>' +
        '<circle cx="104" cy="13" r="5" fill="#ebe4d8" stroke="#4d6358" stroke-width="2"/>' +
        '<circle cx="118" cy="20" r="4" fill="#ebe4d8" stroke="#4d6358" stroke-width="2"/>' +
        '<circle cx="80" cy="60" r="3" fill="#16a34a"/><circle cx="100" cy="80" r="2.5" fill="#16a34a"/>' +
        '<circle cx="60" cy="100" r="2" fill="#16a34a"/><circle cx="120" cy="110" r="2" fill="#16a34a"/>' +
        '</g><g transform="translate(260 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">香港腳 / 灰指甲</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">TINEA · ONYCHOMYCOSIS</text>' +
        '<line x1="0" y1="100" x2="380" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">皮癬菌 · 外用 / 口服 · 復發率高</text>' +
        '</g></svg>',
      // Vitiligo
      '白斑': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(60 50)"><rect x="20" y="20" width="200" height="140" rx="14" fill="#7a9285" stroke="#4d6358" stroke-width="2"/>' +
        '<circle cx="60" cy="60" r="22" fill="#fff"/><circle cx="120" cy="50" r="18" fill="#fff"/>' +
        '<circle cx="160" cy="100" r="28" fill="#fff"/><circle cx="80" cy="120" r="20" fill="#fff"/>' +
        '<circle cx="180" cy="140" r="14" fill="#fff"/></g>' +
        '<g transform="translate(310 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">白斑 / Vitiligo</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">DEPIGMENTATION</text>' +
        '<line x1="0" y1="100" x2="320" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">黑色素細胞自體免疫攻擊</text>' +
        '</g></svg>',
      // Shingles
      '帶狀皰疹 / 皮蛇': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(60 60)"><path d="M0 60 Q40 0 90 60 Q140 120 200 60 Q230 30 240 60" fill="none" stroke="#dc2626" stroke-width="3" stroke-linecap="round"/>' +
        '<circle cx="30" cy="40" r="6" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '<circle cx="60" cy="60" r="7" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '<circle cx="90" cy="60" r="8" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '<circle cx="130" cy="90" r="7" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '<circle cx="160" cy="80" r="6" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '<circle cx="195" cy="55" r="6" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>' +
        '</g><g transform="translate(330 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">帶狀皰疹</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">HERPES ZOSTER · SHINGLES</text>' +
        '<line x1="0" y1="100" x2="320" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">VZV 再活化 · 神經皮節分布</text>' +
        '</g></svg>',
      // Generic / FAQ default
      '常見問題 FAQ': '<svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<rect width="720" height="240" fill="#faf7f2"/>' +
        '<g transform="translate(80 30)"><circle cx="90" cy="90" r="80" fill="#fff" stroke="#4d6358" stroke-width="2.5"/>' +
        '<text x="90" y="115" text-anchor="middle" font-family="Noto Serif TC,Georgia,serif" font-size="80" font-weight="700" fill="#0c5159">?</text>' +
        '</g><g transform="translate(280 50)"><text x="0" y="40" font-family="Noto Serif TC,Georgia,serif" font-size="32" font-weight="700" fill="#0c5159">' + (meta.title.length > 14 ? meta.title.slice(0, 14) + '⋯' : meta.title) + '</text>' +
        '<text x="0" y="78" font-family="Inter,sans-serif" font-size="14" letter-spacing="3" fill="#7a9285">' + (meta.tag_en || 'DERMATOLOGY') + '</text>' +
        '<line x1="0" y1="100" x2="340" y2="100" stroke="#a4b5a8" stroke-width="2"/>' +
        '<text x="0" y="140" font-family="Noto Sans TC,sans-serif" font-size="13" fill="#5e574e">陳翊嘉醫師 · 皮膚科衛教筆記</text>' +
        '</g></svg>'
    };

    var heroSvg = HEROES[meta.tag] || HEROES['常見問題 FAQ'];
    var article = document.querySelector('article.max-w-3xl');
    var h1 = (article && article.querySelector('h1')) ||
      document.querySelector('main h1') ||
      document.querySelector('h1');
    if (!h1) return;
    var fig = document.createElement('figure');
    fig.id = 'dn-article-hero';
    fig.style.cssText = 'margin:18px 0 8px;padding:0;border-radius:14px;overflow:hidden;box-shadow:0 4px 14px -8px rgba(15,23,42,.15)';
    fig.innerHTML = heroSvg;
    var svg = fig.querySelector('svg');
    if (svg) {
      svg.style.cssText = 'display:block;width:100%;height:auto';
      svg.setAttribute('preserveAspectRatio', 'xMidYMid slice');
    }
    var secondaryMeta = document.getElementById('dn-secondary-meta');
    if (secondaryMeta) secondaryMeta.appendChild(fig);
    else h1.parentNode.insertBefore(fig, h1.nextSibling);
  };

  DN.enhanceArticleImages = function () {
    if (document.getElementById('dn-img-css')) return;
    var st = document.createElement('style');
    st.id = 'dn-img-css';
    st.textContent =
      '/* Article images — make them substantial */' +
      '.prose img, article.max-w-3xl img:not(.no-zoom){' +
      '  display:block;width:100%;max-width:760px;height:auto;' +
      '  margin:24px auto;border-radius:12px;' +
      '  box-shadow:0 4px 14px -8px rgba(15,23,42,.15);' +
      '  cursor:zoom-in;' +
      '}' +
      '.prose svg, article.max-w-3xl svg{' +
      '  display:block;max-width:100%;height:auto;margin:20px auto;' +
      '}' +
      '/* Infographic SVG containers */' +
      '.infographic, .types-grid, .wave-card{' +
      '  max-width:100%;' +
      '}' +
      '/* Lightbox overlay (simple click-to-zoom) */' +
      '.dn-img-lightbox{position:fixed;inset:0;background:rgba(15,23,42,.92);z-index:9999;display:none;align-items:center;justify-content:center;padding:24px;cursor:zoom-out}' +
      '.dn-img-lightbox.open{display:flex}' +
      '.dn-img-lightbox img{max-width:96%;max-height:96vh;border-radius:8px;box-shadow:0 24px 60px rgba(0,0,0,.5)}';
    document.head.appendChild(st);

    // Patch each article image with missing attrs
    var imgs = document.querySelectorAll('.prose img, article.max-w-3xl img:not(.no-zoom)');
    imgs.forEach(function (img) {
      if (!img.hasAttribute('loading')) img.setAttribute('loading', 'lazy');
      if (!img.hasAttribute('decoding')) img.setAttribute('decoding', 'async');
      // Provide a sensible default width/height to reduce CLS — only if missing
      if (!img.hasAttribute('width') && !img.hasAttribute('height')) {
        img.setAttribute('width', '760');
        img.setAttribute('height', '480');
        img.style.aspectRatio = 'auto'; // let actual image dictate after load
      }
    });

    // Click-to-zoom lightbox
    var box = document.createElement('div');
    box.className = 'dn-img-lightbox';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', '圖片預覽');
    box.tabIndex = -1;
    box.innerHTML = '<img alt="" />';
    document.body.appendChild(box);
    var bigImg = box.querySelector('img');
    bigImg.setAttribute('decoding', 'async');
    imgs.forEach(function (img) {
      img.addEventListener('click', function () {
        bigImg.src = img.currentSrc || img.src;
        bigImg.alt = img.alt || '';
        box.classList.add('open');
        box.focus();
      });
    });
    box.addEventListener('click', function () { box.classList.remove('open'); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') box.classList.remove('open');
    });
  };

})();
