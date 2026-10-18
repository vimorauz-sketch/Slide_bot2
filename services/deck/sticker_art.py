"""
Subject stickers: small multi-colour illustrations on a 100x100 canvas.

Colours are roles, replaced at render time from the template palette (see stickers.py):
  $P primary  $S secondary  $A accent  $T light tint of primary  $U light tint of secondary
  $L white    $D dark outline  $G light grey
Shapes inherit the outline stroke from the wrapping group; `stroke="none"` marks highlights and
details that must never be outlined, `fill="none"` marks pure line work.
"""
import math

ART = {
    # ------------------------------------------------------------------ biology / nature
    "leaf": '<path d="M20 80 C18 45 45 18 82 18 C82 55 58 82 20 80Z" fill="$P"/><path d="M24 76 C40 60 55 45 72 28" fill="none"/>'
            '<path d="M40 60 L38 46 M52 48 L50 36 M45 55 L58 56 M57 42 L68 44" fill="none"/><ellipse cx="62" cy="30" rx="6" ry="3" fill="$L" stroke="none" opacity=".55" transform="rotate(-40 62 30)"/>',
    "dna": '<path d="M34 10 C34 36 66 36 66 50 C66 64 34 64 34 90" fill="none" stroke-width="6"/>'
           '<path d="M66 10 C66 36 34 36 34 50 C34 64 66 64 66 90" fill="none" stroke-width="6"/>'
           '<path d="M34 10 C34 36 66 36 66 50 C66 64 34 64 34 90" fill="none" stroke="$P" stroke-width="3.2"/>'
           '<path d="M66 10 C66 36 34 36 34 50 C34 64 66 64 66 90" fill="none" stroke="$S" stroke-width="3.2"/>'
           '<path d="M38 20 H62 M44 30 H56 M44 70 H56 M38 80 H62" fill="none" stroke-width="3"/><circle cx="50" cy="50" r="5" fill="$A"/>',
    "microscope": '<rect x="20" y="80" width="56" height="9" rx="4" fill="$D"/><path d="M60 80 C78 70 76 46 58 40" fill="none" stroke-width="7"/>'
                  '<path d="M60 80 C78 70 76 46 58 40" fill="none" stroke="$S" stroke-width="3.5"/>'
                  '<rect x="34" y="14" width="14" height="40" rx="4" fill="$P" transform="rotate(-25 41 34)"/>'
                  '<rect x="28" y="62" width="34" height="7" rx="3" fill="$G"/><rect x="40" y="52" width="10" height="12" rx="2" fill="$T"/>'
                  '<circle cx="53" cy="22" r="5" fill="$A"/><rect x="38" y="20" width="4" height="22" rx="2" fill="$L" stroke="none" opacity=".6" transform="rotate(-25 41 34)"/>',
    "cell": '<ellipse cx="50" cy="52" rx="38" ry="32" fill="$T"/><ellipse cx="44" cy="48" rx="14" ry="12" fill="$P"/><circle cx="41" cy="45" r="4" fill="$D" stroke="none"/>'
            '<ellipse cx="70" cy="62" rx="8" ry="4" fill="$S" transform="rotate(25 70 62)"/><ellipse cx="62" cy="34" rx="6" ry="3.5" fill="$A"/>'
            '<circle cx="30" cy="68" r="3" fill="$S"/><circle cx="74" cy="44" r="2.5" fill="$S"/><path d="M28 30 C34 26 40 26 44 28" fill="none" stroke="$L" stroke-width="3" stroke-linecap="round"/>',
    "tree": '<rect x="44" y="60" width="12" height="30" rx="3" fill="$D"/><path d="M50 60 L40 70 M50 66 L60 74" fill="none"/>'
            '<path d="M30 70 C14 70 10 52 20 44 C16 30 28 18 40 22 C44 10 60 8 66 20 C80 18 90 32 82 44 C92 52 86 70 70 70Z" fill="$P"/>'
            '<path d="M30 38 C32 32 38 28 44 30" fill="none" stroke="$L" stroke-width="4" stroke-linecap="round" opacity=".6"/><circle cx="62" cy="48" r="4" fill="$A"/><circle cx="38" cy="56" r="3.5" fill="$A"/><circle cx="70" cy="34" r="3" fill="$A"/>',
    "flower": '<path d="M50 60 V92" fill="none" stroke-width="5"/><path d="M50 78 C40 70 30 72 26 80 C34 84 44 84 50 78Z" fill="$S"/>'
              + "".join(f'<ellipse cx="50" cy="26" rx="10" ry="16" fill="$P" transform="rotate({a} 50 42)"/>' for a in range(0, 360, 60))
              + '<circle cx="50" cy="42" r="10" fill="$A"/>',
    "butterfly": '<path d="M50 50 C30 20 10 26 14 44 C16 56 34 56 50 50Z" fill="$P"/><path d="M50 50 C70 20 90 26 86 44 C84 56 66 56 50 50Z" fill="$P"/>'
                 '<path d="M50 52 C36 62 24 76 34 82 C42 86 48 70 50 52Z" fill="$S"/><path d="M50 52 C64 62 76 76 66 82 C58 86 52 70 50 52Z" fill="$S"/>'
                 '<rect x="47" y="34" width="6" height="40" rx="3" fill="$D"/><path d="M48 34 C44 24 40 22 36 20 M52 34 C56 24 60 22 64 20" fill="none"/>'
                 '<circle cx="28" cy="40" r="4" fill="$A"/><circle cx="72" cy="40" r="4" fill="$A"/>',
    "fish": '<path d="M14 50 C30 26 62 26 76 50 C62 74 30 74 14 50Z" fill="$P"/><path d="M76 50 L92 34 V66Z" fill="$S"/>'
            '<circle cx="30" cy="46" r="5" fill="$L"/><circle cx="30" cy="46" r="2.4" fill="$D" stroke="none"/><path d="M46 36 C52 44 52 56 46 64 M58 38 C63 45 63 55 58 62" fill="none"/>',
    "sun": "".join(f'<rect x="47" y="6" width="6" height="16" rx="3" fill="$A" transform="rotate({a} 50 50)"/>' for a in range(0, 360, 45))
           + '<circle cx="50" cy="50" r="24" fill="$A"/><circle cx="50" cy="50" r="17" fill="$P" stroke="none" opacity=".25"/><circle cx="42" cy="44" r="5" fill="$L" stroke="none" opacity=".6"/>',
    "drop": '<path d="M50 10 C64 32 78 46 78 62 C78 78 66 90 50 90 C34 90 22 78 22 62 C22 46 36 32 50 10Z" fill="$S"/>'
            '<path d="M36 62 C36 72 42 78 50 80" fill="none" stroke="$L" stroke-width="4" stroke-linecap="round"/>',
    "volcano": '<path d="M10 88 L38 40 H62 L90 88Z" fill="$D"/><path d="M38 40 H62 L56 52 L50 46 L44 54Z" fill="$A"/>'
               '<circle cx="42" cy="22" r="9" fill="$G"/><circle cx="56" cy="16" r="11" fill="$G"/><circle cx="66" cy="26" r="7" fill="$G"/><path d="M50 40 C48 30 52 28 50 22" fill="none" stroke="$A" stroke-width="4"/>',
    "mountain": '<path d="M6 86 L38 30 L56 60 L66 46 L94 86Z" fill="$P"/><path d="M38 30 L48 48 L42 46 L36 52 L30 44Z" fill="$L"/>'
                '<path d="M66 46 L74 58 L68 56 L62 60Z" fill="$L"/><circle cx="78" cy="22" r="9" fill="$A"/>',
    "recycle": '<circle cx="50" cy="50" r="40" fill="$P"/>'
               + "".join(f'<g transform="rotate({a} 50 50)"><path d="M50 22 A28 28 0 0 1 74 36" fill="none" stroke="$L" stroke-width="7"/><path d="M68 28 L80 40 L64 42Z" fill="$L" stroke="none"/></g>' for a in (0, 120, 240))
               + '<circle cx="50" cy="50" r="8" fill="$A"/>',
    "earth": '<circle cx="50" cy="50" r="38" fill="$S"/><path d="M28 30 C38 26 44 34 40 42 C36 50 26 46 22 54 C18 44 20 36 28 30Z" fill="$P"/>'
             '<path d="M56 18 C66 22 70 30 64 36 C58 40 62 48 72 46 C80 44 84 56 80 64 C72 78 58 84 50 80 C56 70 50 62 56 56 C60 50 52 40 50 32 C48 24 52 20 56 18Z" fill="$P"/>'
             '<path d="M30 70 C36 72 38 78 34 82" fill="none" stroke="$L" stroke-width="3" opacity=".7"/>',
    # ------------------------------------------------------------------ chemistry / physics / space
    "flask": '<path d="M40 12 H60 V36 L80 78 C83 85 78 90 71 90 H29 C22 90 17 85 20 78 L40 36Z" fill="$T"/>'
             '<path d="M30 64 H70 L77 80 C79 85 76 88 71 88 H29 C24 88 21 85 23 80Z" fill="$P"/><rect x="36" y="8" width="28" height="7" rx="3" fill="$G"/>'
             '<circle cx="44" cy="74" r="4" fill="$L" stroke="none" opacity=".7"/><circle cx="58" cy="78" r="3" fill="$L" stroke="none" opacity=".7"/><circle cx="54" cy="52" r="3" fill="$A"/><circle cx="48" cy="44" r="2" fill="$A"/>',
    "atom": '<ellipse cx="50" cy="50" rx="40" ry="15" fill="none" stroke-width="5"/><ellipse cx="50" cy="50" rx="40" ry="15" fill="none" stroke-width="5" transform="rotate(60 50 50)"/>'
            '<ellipse cx="50" cy="50" rx="40" ry="15" fill="none" stroke-width="5" transform="rotate(-60 50 50)"/>'
            '<ellipse cx="50" cy="50" rx="40" ry="15" fill="none" stroke="$P" stroke-width="2.5"/><ellipse cx="50" cy="50" rx="40" ry="15" fill="none" stroke="$S" stroke-width="2.5" transform="rotate(60 50 50)"/>'
            '<ellipse cx="50" cy="50" rx="40" ry="15" fill="none" stroke="$P" stroke-width="2.5" transform="rotate(-60 50 50)"/><circle cx="50" cy="50" r="9" fill="$A"/><circle cx="88" cy="47" r="5" fill="$S"/><circle cx="30" cy="16" r="5" fill="$P"/>',
    "molecule": '<path d="M30 30 L52 50 L30 72 M52 50 L78 44 M78 44 L84 22 M78 44 L84 70" fill="none" stroke-width="5"/>'
                '<circle cx="52" cy="50" r="14" fill="$P"/><circle cx="30" cy="30" r="10" fill="$S"/><circle cx="30" cy="72" r="10" fill="$S"/>'
                '<circle cx="78" cy="44" r="10" fill="$A"/><circle cx="84" cy="20" r="7" fill="$T"/><circle cx="84" cy="72" r="7" fill="$T"/><circle cx="47" cy="45" r="4" fill="$L" stroke="none" opacity=".6"/>',
    "magnet": '<path d="M22 20 H40 V54 C40 62 60 62 60 54 V20 H78 V54 C78 92 22 92 22 54Z" fill="$P"/><rect x="22" y="20" width="18" height="14" fill="$G"/><rect x="60" y="20" width="18" height="14" fill="$G"/>'
              '<path d="M86 30 L94 26 M88 42 H96 M8 30 L2 26" fill="none" stroke="$A" stroke-width="3"/>',
    "bulb": '<path d="M50 10 C30 10 18 26 22 44 C25 56 36 60 36 72 H64 C64 60 75 56 78 44 C82 26 70 10 50 10Z" fill="$A"/>'
            '<rect x="36" y="72" width="28" height="8" rx="2" fill="$G"/><rect x="38" y="80" width="24" height="7" rx="2" fill="$G"/><path d="M44 90 H56" fill="none" stroke-width="5"/>'
            '<path d="M42 60 L46 40 L50 52 L54 40 L58 60" fill="none"/><path d="M32 30 C34 22 40 18 46 17" fill="none" stroke="$L" stroke-width="4" stroke-linecap="round"/>',
    "rocket": '<path d="M50 8 C68 22 72 46 66 70 H34 C28 46 32 22 50 8Z" fill="$L"/><path d="M50 8 C60 16 65 26 67 36 H33 C35 26 40 16 50 8Z" fill="$P"/>'
              '<circle cx="50" cy="48" r="8" fill="$S"/><path d="M34 54 L18 72 L32 72Z" fill="$P"/><path d="M66 54 L82 72 L68 72Z" fill="$P"/>'
              '<path d="M40 72 C40 84 50 94 50 94 C50 94 60 84 60 72Z" fill="$A"/>',
    "planet": '<circle cx="50" cy="50" r="26" fill="$P"/><path d="M28 40 C40 46 60 46 74 40" fill="none" stroke="$S" stroke-width="5" stroke-linecap="round"/>'
              '<ellipse cx="50" cy="54" rx="46" ry="12" fill="none" stroke-width="5" transform="rotate(-14 50 54)"/><ellipse cx="50" cy="54" rx="46" ry="12" fill="none" stroke="$A" stroke-width="2.6" transform="rotate(-14 50 54)"/>'
              '<circle cx="40" cy="38" r="5" fill="$L" stroke="none" opacity=".5"/><path d="M84 14 L86 20 L92 22 L86 24 L84 30 L82 24 L76 22 L82 20Z" fill="$A"/>',
    "telescope": '<rect x="18" y="30" width="58" height="18" rx="6" fill="$P" transform="rotate(-24 47 39)"/><rect x="70" y="14" width="12" height="24" rx="3" fill="$S" transform="rotate(-24 76 26)"/>'
                 '<path d="M46 50 L30 88 M50 50 L54 88 M48 50 L70 86" fill="none" stroke-width="5"/><circle cx="48" cy="50" r="6" fill="$A"/><path d="M14 16 L16 22 L22 24 L16 26 L14 32 L12 26 L6 24 L12 22Z" fill="$A"/>',
    "star": '<path d="M50 8 L61 36 L91 38 L68 57 L76 87 L50 70 L24 87 L32 57 L9 38 L39 36Z" fill="$A"/><path d="M42 40 L50 22" fill="none" stroke="$L" stroke-width="4" stroke-linecap="round"/>',
    "lightning": '<path d="M58 6 L22 56 H46 L38 94 L80 40 H54Z" fill="$A"/>',
    "thermometer": '<rect x="40" y="10" width="20" height="62" rx="10" fill="$L"/><circle cx="50" cy="76" r="15" fill="$P"/><rect x="46" y="34" width="8" height="40" rx="4" fill="$P" stroke="none"/>'
                   '<path d="M64 24 H72 M64 36 H70 M64 48 H72" fill="none"/>',
    "gear": '<path d="M44 8 H56 L58 20 L67 24 L77 17 L85 25 L78 35 L82 44 L94 46 V56 L82 58 L78 67 L85 77 L77 85 L67 78 L58 82 L56 94 H44 L42 82 L33 78 L23 85 L15 77 L22 67 L18 58 L6 56 V46 L18 44 L22 35 L15 25 L23 17 L33 24 L42 20Z" fill="$S"/>'
            '<circle cx="50" cy="51" r="14" fill="$L"/><circle cx="50" cy="51" r="6" fill="$P"/>',
    # ------------------------------------------------------------------ maths
    "compass": '<circle cx="50" cy="16" r="7" fill="$A"/><path d="M50 22 L26 88 M50 22 L74 88" fill="none" stroke-width="6"/><path d="M50 22 L26 88" fill="none" stroke="$P" stroke-width="3"/>'
               '<path d="M50 22 L74 88" fill="none" stroke="$S" stroke-width="3"/><path d="M34 62 C44 70 56 70 66 62" fill="none" stroke-width="4"/><path d="M70 82 L80 92" fill="none" stroke="$D" stroke-width="3"/>',
    "ruler": '<rect x="10" y="38" width="80" height="24" rx="3" fill="$A" transform="rotate(-20 50 50)"/>'
             + "".join(f'<path d="M{18 + i * 9} 38 V{48 if i % 2 else 52}" fill="none" stroke-width="2.4" transform="rotate(-20 50 50)"/>' for i in range(8)),
    "triangle": '<path d="M14 86 L14 14 L86 86Z" fill="$S"/><path d="M28 72 L28 48 L52 72Z" fill="$L"/>'
                + "".join(f'<path d="M{20 + i * 9} 86 V80" fill="none" stroke-width="2"/>' for i in range(7)),
    "pi": '<rect x="12" y="12" width="76" height="76" rx="18" fill="$P"/><path d="M28 34 H74 M42 34 V72 M60 34 V66 C60 72 66 74 72 70" fill="none" stroke="$L" stroke-width="8" stroke-linecap="round"/>',
    "calculator": '<rect x="22" y="8" width="56" height="84" rx="8" fill="$D"/><rect x="30" y="16" width="40" height="18" rx="3" fill="$T"/>'
                  + "".join(f'<rect x="{30 + (i % 3) * 14}" y="{42 + (i // 3) * 13}" width="10" height="9" rx="2" fill="{"$A" if i % 3 == 2 else "$L"}" stroke="none"/>' for i in range(12))
                  + '<path d="M56 26 H66" fill="none" stroke="$D" stroke-width="3"/>',
    "abacus": '<rect x="10" y="14" width="80" height="72" rx="6" fill="none" stroke-width="6"/><rect x="10" y="14" width="80" height="72" rx="6" fill="none" stroke="$S" stroke-width="3"/>'
              + "".join(f'<path d="M14 {30 + r * 18} H86" fill="none" stroke-width="2"/>' for r in range(3))
              + "".join(f'<circle cx="{22 + c * 11 + (r * 7 % 22)}" cy="{30 + r * 18}" r="5.5" fill="{["$P", "$A", "$S"][r]}"/>' for r in range(3) for c in range(3)),
    "cube": '<path d="M50 10 L86 30 V70 L50 90 L14 70 V30Z" fill="$P"/><path d="M50 10 L86 30 L50 50 L14 30Z" fill="$T"/><path d="M50 50 L86 30 V70 L50 90Z" fill="$S"/>',
    "protractor": '<path d="M8 74 A42 42 0 0 1 92 74Z" fill="$T"/><path d="M28 74 A22 22 0 0 1 72 74" fill="$L"/>'
                  + "".join(f'<path d="M50 74 L{50 + 42 * math.cos(math.radians(a)):.1f} {74 - 42 * math.sin(math.radians(a)):.1f}" fill="none" stroke-width="1.5" opacity=".5"/>' for a in range(15, 180, 15))
                  + '<path d="M50 74 L76 40" fill="none" stroke="$P" stroke-width="4"/><circle cx="50" cy="74" r="4" fill="$A"/>',
    "chart": '<rect x="10" y="10" width="80" height="80" rx="10" fill="$L"/><rect x="22" y="58" width="12" height="22" rx="2" fill="$S"/><rect x="40" y="44" width="12" height="36" rx="2" fill="$P"/>'
             '<rect x="58" y="30" width="12" height="50" rx="2" fill="$A"/><path d="M20 46 L40 32 L54 38 L78 18" fill="none" stroke="$D" stroke-width="3"/><path d="M70 16 H80 V26" fill="none" stroke="$D" stroke-width="3"/>',
    # ------------------------------------------------------------------ humanities
    "book": '<path d="M16 20 H74 C80 20 84 24 84 30 V88 H26 C20 88 16 84 16 78Z" fill="$P"/><path d="M26 74 H84 V88 H26 C22 88 20 85 20 81 C20 77 22 74 26 74Z" fill="$L"/>'
            '<rect x="30" y="32" width="40" height="10" rx="2" fill="$A"/><path d="M30 52 H64" fill="none" stroke="$L" stroke-width="3" opacity=".7"/>',
    "openbook": '<path d="M50 30 C36 20 20 20 8 24 V80 C20 76 36 76 50 86Z" fill="$L"/><path d="M50 30 C64 20 80 20 92 24 V80 C80 76 64 76 50 86Z" fill="$T"/>'
                '<path d="M16 36 C26 34 36 34 44 40 M16 48 C26 46 36 46 44 52 M16 60 C26 58 36 58 44 64 M56 40 C64 34 74 34 84 36 M56 52 C64 46 74 46 84 48" fill="none" stroke-width="2.4" opacity=".6"/>'
                '<path d="M50 30 V86" fill="none"/><path d="M70 14 V40 L76 34 L82 40 V14Z" fill="$A"/>',
    "quill": '<path d="M86 8 C50 14 30 40 24 76 L32 72 C40 52 54 36 70 28 C56 40 46 54 40 68 C62 60 80 38 86 8Z" fill="$P"/>'
             '<path d="M24 76 L16 92" fill="none" stroke-width="5"/><path d="M20 90 C36 88 50 90 66 92" fill="none" stroke="$S" stroke-width="3"/><path d="M60 26 L46 50" fill="none" stroke="$L" stroke-width="2.5" opacity=".7"/>',
    "scroll": '<rect x="22" y="20" width="56" height="60" fill="$T"/><rect x="14" y="12" width="72" height="12" rx="6" fill="$A"/><rect x="14" y="76" width="72" height="12" rx="6" fill="$A"/>'
              '<path d="M32 38 H68 M32 48 H62 M32 58 H66" fill="none" stroke-width="3" opacity=".6"/>',
    "column": '<rect x="18" y="12" width="64" height="12" rx="2" fill="$G"/><path d="M14 24 H86 L80 30 H20Z" fill="$L"/><rect x="18" y="80" width="64" height="10" rx="2" fill="$G"/>'
              + "".join(f'<rect x="{26 + i * 13}" y="30" width="9" height="50" fill="$L"/>' for i in range(4)) + '<path d="M50 6 L82 12 H18Z" fill="$P"/>',
    "hourglass": '<rect x="20" y="8" width="60" height="10" rx="3" fill="$S"/><rect x="20" y="82" width="60" height="10" rx="3" fill="$S"/>'
                 '<path d="M28 18 H72 C72 38 56 44 56 50 C56 56 72 62 72 82 H28 C28 62 44 56 44 50 C44 44 28 38 28 18Z" fill="$L"/>'
                 '<path d="M36 28 H64 C62 36 54 40 50 46 C46 40 38 36 36 28Z" fill="$A" stroke="none"/><path d="M34 80 C38 68 46 66 50 64 C54 66 62 68 66 80Z" fill="$A" stroke="none"/>',
    "globe": '<circle cx="50" cy="44" r="32" fill="$S"/><path d="M30 26 C40 30 38 40 30 44 C26 50 30 58 36 60" fill="none" stroke="$P" stroke-width="7" stroke-linecap="round"/>'
             '<path d="M58 16 C62 26 70 26 74 34 C70 44 62 42 60 52 C58 62 66 66 64 72" fill="none" stroke="$P" stroke-width="7" stroke-linecap="round"/>'
             '<path d="M20 30 C14 52 26 76 50 78" fill="none" stroke-width="4"/><rect x="46" y="76" width="8" height="10" fill="$G"/><rect x="30" y="86" width="40" height="7" rx="3" fill="$D"/>',
    "pin": '<path d="M50 92 C50 92 20 60 20 40 C20 22 33 10 50 10 C67 10 80 22 80 40 C80 60 50 92 50 92Z" fill="$P"/><circle cx="50" cy="40" r="12" fill="$L"/><circle cx="50" cy="40" r="5" fill="$A"/>',
    "castle": '<path d="M14 90 V36 H24 V44 H32 V36 H42 V44 H58 V36 H68 V44 H76 V36 H86 V90Z" fill="$G"/><path d="M42 90 V66 C42 58 58 58 58 66 V90Z" fill="$D"/>'
              '<path d="M50 10 V36" fill="none"/><path d="M50 10 L68 16 L50 22Z" fill="$P"/><rect x="22" y="56" width="8" height="12" rx="4" fill="$S"/><rect x="70" y="56" width="8" height="12" rx="4" fill="$S"/>',
    "crown": '<path d="M12 76 L18 28 L36 50 L50 18 L64 50 L82 28 L88 76Z" fill="$A"/><rect x="12" y="76" width="76" height="12" rx="3" fill="$P"/>'
             '<circle cx="50" cy="62" r="6" fill="$S"/><circle cx="30" cy="64" r="4" fill="$L"/><circle cx="70" cy="64" r="4" fill="$L"/>',
    "palette": '<path d="M50 10 C24 10 8 30 10 52 C12 74 30 90 50 90 C58 90 60 84 56 78 C52 72 56 66 64 66 H76 C86 66 92 58 90 46 C86 24 70 10 50 10Z" fill="$L"/>'
               '<circle cx="30" cy="46" r="7" fill="$P"/><circle cx="42" cy="28" r="7" fill="$A"/><circle cx="64" cy="28" r="7" fill="$S"/><circle cx="76" cy="46" r="6" fill="$D"/><circle cx="32" cy="68" r="7" fill="$T"/>',
    "brush": '<rect x="44" y="6" width="12" height="46" rx="4" fill="$S" transform="rotate(30 50 50)"/><rect x="42" y="50" width="16" height="10" fill="$G" transform="rotate(30 50 50)"/>'
             '<path d="M30 74 C22 74 16 82 14 92 C26 92 38 88 40 80Z" fill="$P"/><path d="M14 92 C30 90 52 92 80 86" fill="none" stroke="$P" stroke-width="4" stroke-linecap="round"/>',
    "note": '<path d="M38 70 V20 L82 10 V60" fill="none" stroke-width="7"/><path d="M38 20 L82 10 V22 L38 32Z" fill="$P"/>'
            '<ellipse cx="28" cy="72" rx="13" ry="10" fill="$P" transform="rotate(-18 28 72)"/><ellipse cx="72" cy="62" rx="13" ry="10" fill="$S" transform="rotate(-18 72 62)"/>',
    "mic": '<rect x="34" y="8" width="32" height="50" rx="16" fill="$P"/><path d="M40 22 H60 M40 32 H60 M40 42 H60" fill="none" stroke="$L" stroke-width="2.4" opacity=".7"/>'
           '<path d="M24 44 C24 70 76 70 76 44" fill="none" stroke-width="5"/><path d="M50 68 V84 M34 88 H66" fill="none" stroke-width="5"/>',
    "masks": '<path d="M14 18 H52 V44 C52 60 42 70 33 70 C24 70 14 60 14 44Z" fill="$A"/><path d="M48 32 H86 V58 C86 74 76 84 67 84 C58 84 48 74 48 58Z" fill="$P"/>'
             '<path d="M24 36 C26 32 30 32 32 36 M36 36 C38 32 42 32 44 36 M25 52 C30 58 38 58 42 52" fill="none" stroke-width="3"/>'
             '<path d="M58 50 C60 46 64 46 66 50 M70 50 C72 46 76 46 78 50 M58 72 C62 66 72 66 76 72" fill="none" stroke-width="3"/>',
    "camera": '<path d="M12 32 H32 L38 22 H62 L68 32 H88 V80 H12Z" fill="$D"/><circle cx="50" cy="56" r="18" fill="$S"/><circle cx="50" cy="56" r="10" fill="$P"/>'
              '<circle cx="45" cy="51" r="3.5" fill="$L" stroke="none"/><rect x="72" y="38" width="10" height="6" rx="2" fill="$A"/>',
    "lamp": '<path d="M24 64 C24 46 36 40 50 40 C64 40 76 46 76 64Z" fill="$A"/><path d="M50 40 V24 L62 14" fill="none" stroke-width="5"/>'
            '<path d="M36 64 H64 L60 80 H40Z" fill="$P"/><rect x="30" y="80" width="40" height="8" rx="3" fill="$D"/><path d="M50 18 C46 10 54 8 50 2" fill="none" stroke="$A" stroke-width="3"/>',
    # ------------------------------------------------------------------ IT / technology
    "laptop": '<rect x="18" y="16" width="64" height="44" rx="5" fill="$D"/><rect x="24" y="22" width="52" height="32" rx="2" fill="$S"/>'
              '<path d="M8 66 H92 L86 78 H14Z" fill="$G"/><path d="M32 34 L26 38 L32 42 M44 34 L50 38 L44 42 M37 44 L41 32" fill="none" stroke="$L" stroke-width="2.6"/>'
              '<rect x="54" y="30" width="16" height="4" rx="2" fill="$A" stroke="none"/><rect x="54" y="38" width="10" height="4" rx="2" fill="$L" stroke="none"/>',
    "code": '<rect x="10" y="16" width="80" height="68" rx="12" fill="$P"/><path d="M38 36 L24 50 L38 64 M62 36 L76 50 L62 64 M54 30 L46 70" fill="none" stroke="$L" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>',
    "robot": '<rect x="22" y="30" width="56" height="44" rx="12" fill="$L"/><circle cx="38" cy="50" r="7" fill="$S"/><circle cx="62" cy="50" r="7" fill="$S"/>'
             '<path d="M40 64 H60" fill="none" stroke-width="4"/><path d="M50 30 V16" fill="none" stroke-width="4"/><circle cx="50" cy="14" r="5" fill="$A"/>'
             '<rect x="12" y="44" width="10" height="16" rx="4" fill="$P"/><rect x="78" y="44" width="10" height="16" rx="4" fill="$P"/><rect x="34" y="74" width="32" height="14" rx="4" fill="$P"/>',
    "chip": '<rect x="24" y="24" width="52" height="52" rx="8" fill="$D"/><rect x="36" y="36" width="28" height="28" rx="4" fill="$P"/>'
            + "".join(f'<path d="M{34 + i * 10} 24 V12 M{34 + i * 10} 76 V88 M24 {34 + i * 10} H12 M76 {34 + i * 10} H88" fill="none" stroke-width="4"/>' for i in range(4))
            + '<circle cx="42" cy="42" r="3" fill="$A" stroke="none"/>',
    "cloud": '<path d="M28 74 C14 74 8 62 12 52 C16 42 26 40 32 42 C34 28 46 20 58 22 C72 24 80 36 78 48 C90 48 94 58 92 64 C90 72 84 74 78 74Z" fill="$L"/>'
             '<path d="M50 66 V44 M40 52 L50 42 L60 52" fill="none" stroke="$P" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
    "wifi": '<path d="M12 40 C34 18 66 18 88 40" fill="none" stroke="$P" stroke-width="9" stroke-linecap="round"/><path d="M26 54 C40 40 60 40 74 54" fill="none" stroke="$S" stroke-width="9" stroke-linecap="round"/>'
            '<path d="M38 68 C46 60 54 60 62 68" fill="none" stroke="$A" stroke-width="9" stroke-linecap="round"/><circle cx="50" cy="80" r="6" fill="$D"/>',
    "gamepad": '<path d="M24 32 H76 C88 32 94 46 92 60 C90 76 80 80 72 72 L64 64 H36 L28 72 C20 80 10 76 8 60 C6 46 12 32 24 32Z" fill="$P"/>'
               '<path d="M28 44 V56 M22 50 H34" fill="none" stroke="$L" stroke-width="5" stroke-linecap="round"/><circle cx="68" cy="46" r="4.5" fill="$A"/><circle cx="76" cy="54" r="4.5" fill="$S"/>',
    "magnifier": '<circle cx="42" cy="42" r="26" fill="$T"/><circle cx="42" cy="42" r="18" fill="$L"/><path d="M62 62 L88 88" fill="none" stroke-width="12" stroke-linecap="round"/>'
                 '<path d="M62 62 L88 88" fill="none" stroke="$P" stroke-width="6" stroke-linecap="round"/><path d="M32 32 C36 28 42 26 48 28" fill="none" stroke="$S" stroke-width="3" stroke-linecap="round"/>',
    # ------------------------------------------------------------------ economics / business
    "coins": '<ellipse cx="40" cy="72" rx="26" ry="10" fill="$A"/><rect x="14" y="56" width="52" height="16" fill="$A"/><ellipse cx="40" cy="56" rx="26" ry="10" fill="$A"/>'
             '<ellipse cx="40" cy="56" rx="16" ry="5" fill="none" opacity=".5"/><circle cx="68" cy="38" r="22" fill="$A"/><circle cx="68" cy="38" r="15" fill="none" opacity=".5"/>'
             '<path d="M68 28 V48 M62 32 C64 28 74 28 74 34 C74 40 62 36 62 42 C62 48 72 48 74 44" fill="none" stroke-width="3"/>',
    "piggy": '<ellipse cx="50" cy="56" rx="34" ry="26" fill="$T"/><circle cx="76" cy="52" r="10" fill="$T"/><ellipse cx="80" cy="54" rx="5" ry="4" fill="$P"/>'
             '<path d="M34 34 L40 22 L48 32" fill="$T"/><rect x="34" y="76" width="9" height="12" rx="3" fill="$T"/><rect x="58" y="76" width="9" height="12" rx="3" fill="$T"/>'
             '<rect x="40" y="28" width="22" height="6" rx="3" fill="$D"/><circle cx="66" cy="46" r="3" fill="$D" stroke="none"/><circle cx="50" cy="16" r="9" fill="$A"/>',
    "briefcase": '<rect x="12" y="30" width="76" height="54" rx="8" fill="$P"/><path d="M36 30 V22 C36 18 40 16 44 16 H56 C60 16 64 18 64 22 V30" fill="none" stroke-width="6"/>'
                 '<path d="M12 50 H88" fill="none"/><rect x="42" y="44" width="16" height="12" rx="3" fill="$A"/>',
    "target": '<circle cx="46" cy="54" r="36" fill="$L"/><circle cx="46" cy="54" r="26" fill="$P"/><circle cx="46" cy="54" r="16" fill="$L"/><circle cx="46" cy="54" r="7" fill="$P"/>'
              '<path d="M46 54 L86 14" fill="none" stroke-width="5"/><path d="M76 12 L88 12 L88 24 L80 20Z" fill="$A"/>',
    "megaphone": '<path d="M14 40 H30 L74 16 V84 L30 60 H14Z" fill="$P"/><rect x="10" y="38" width="20" height="24" rx="4" fill="$S"/><path d="M30 60 L36 84 H46 L42 64" fill="$G"/>'
                 '<path d="M84 36 L94 30 M86 50 H96 M84 64 L94 70" fill="none" stroke="$A" stroke-width="4" stroke-linecap="round"/>',
    "wallet": '<rect x="10" y="26" width="76" height="56" rx="10" fill="$P"/><rect x="58" y="44" width="34" height="22" rx="8" fill="$S"/><circle cx="70" cy="55" r="4.5" fill="$A"/>'
              '<path d="M18 26 L62 12 L70 26" fill="$L"/>',
    "trend": '<rect x="8" y="8" width="84" height="84" rx="18" fill="$S"/><path d="M20 70 L40 50 L52 60 L78 30" fill="none" stroke="$L" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>'
             '<path d="M64 28 H80 V44" fill="none" stroke="$L" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>',
    # ------------------------------------------------------------------ medicine
    "heart": '<path d="M50 88 C20 66 8 50 8 34 C8 20 18 10 31 10 C40 10 46 16 50 22 C54 16 60 10 69 10 C82 10 92 20 92 34 C92 50 80 66 50 88Z" fill="$P"/>'
             '<path d="M20 46 H36 L42 34 L50 60 L56 44 H80" fill="none" stroke="$L" stroke-width="4" stroke-linejoin="round"/>',
    "pill": '<rect x="10" y="34" width="80" height="32" rx="16" fill="$L" transform="rotate(-35 50 50)"/><path d="M50 34 H74 C83 34 90 41 90 50 C90 59 83 66 74 66 H50Z" fill="$P" transform="rotate(-35 50 50)"/>'
            '<circle cx="76" cy="80" r="10" fill="$A"/><path d="M70 80 H82" fill="none"/>',
    "cross": '<rect x="10" y="10" width="80" height="80" rx="22" fill="$L"/><path d="M40 22 H60 V40 H78 V60 H60 V78 H40 V60 H22 V40 H40Z" fill="$P"/>',
    "tooth": '<path d="M24 22 C32 12 44 18 50 18 C56 18 68 12 76 22 C84 34 76 52 72 64 C68 76 66 90 60 90 C54 90 54 70 50 70 C46 70 46 90 40 90 C34 90 32 76 28 64 C24 52 16 34 24 22Z" fill="$L"/>'
             '<path d="M34 30 C38 26 42 26 46 28" fill="none" stroke="$S" stroke-width="3" stroke-linecap="round"/>',
    "brain": '<path d="M48 16 C36 10 22 16 20 28 C10 32 8 46 14 54 C8 64 14 78 26 80 C30 90 44 92 48 84Z" fill="$T"/>'
             '<path d="M52 16 C64 10 78 16 80 28 C90 32 92 46 86 54 C92 64 86 78 74 80 C70 90 56 92 52 84Z" fill="$P"/>'
             '<path d="M30 34 C36 38 36 46 30 50 M28 64 C34 62 40 66 40 72 M70 34 C64 38 64 46 70 50 M72 64 C66 62 60 66 60 72" fill="none" stroke-width="2.6"/>',
    # ------------------------------------------------------------------ school / general
    "pencil": '<rect x="38" y="6" width="24" height="64" fill="$A" transform="rotate(35 50 50)"/><rect x="38" y="6" width="24" height="12" fill="$P" transform="rotate(35 50 50)"/>'
              '<path d="M38 70 H62 L50 92Z" fill="$T" transform="rotate(35 50 50)"/><path d="M46 84 H54 L50 92Z" fill="$D" transform="rotate(35 50 50)"/>',
    "cap": '<path d="M50 18 L94 38 L50 58 L6 38Z" fill="$D"/><path d="M26 48 V68 C26 76 74 76 74 68 V48 L50 58Z" fill="$P"/>'
           '<path d="M86 42 V66" fill="none" stroke-width="3"/><circle cx="86" cy="70" r="5" fill="$A"/>',
    "trophy": '<path d="M28 12 H72 V36 C72 50 62 60 50 60 C38 60 28 50 28 36Z" fill="$A"/><path d="M28 20 H14 C14 36 22 42 30 42 M72 20 H86 C86 36 78 42 70 42" fill="none" stroke-width="5"/>'
              '<rect x="44" y="60" width="12" height="14" fill="$A"/><rect x="30" y="74" width="40" height="14" rx="3" fill="$P"/><path d="M40 20 V36" fill="none" stroke="$L" stroke-width="4" stroke-linecap="round"/>',
    "medal": '<path d="M30 8 H46 L58 40 H42Z" fill="$P"/><path d="M70 8 H54 L42 40 H58Z" fill="$S"/><circle cx="50" cy="62" r="26" fill="$A"/>'
             '<path d="M50 48 L54 58 L65 58 L56 65 L59 76 L50 69 L41 76 L44 65 L35 58 L46 58Z" fill="$L"/>',
    "clock": '<circle cx="50" cy="54" r="36" fill="$L"/><circle cx="24" cy="18" r="10" fill="$P"/><circle cx="76" cy="18" r="10" fill="$P"/>'
             '<path d="M50 54 V32 M50 54 L66 62" fill="none" stroke-width="5" stroke-linecap="round"/><circle cx="50" cy="54" r="4" fill="$A"/><path d="M28 86 L22 94 M72 86 L78 94" fill="none" stroke-width="5"/>',
    "puzzle": '<path d="M14 30 H36 C34 22 38 16 46 16 C54 16 58 22 56 30 H78 V52 C86 50 92 54 92 62 C92 70 86 74 78 72 V90 H14Z" fill="$P"/>'
              '<path d="M14 60 H36 C34 52 38 46 46 46 C54 46 58 52 56 60 H78" fill="none" stroke-width="3"/>',
    "bubble": '<path d="M14 18 H86 C90 18 92 20 92 24 V64 C92 68 90 70 86 70 H44 L26 88 V70 H14 C10 70 8 68 8 64 V24 C8 20 10 18 14 18Z" fill="$S"/>'
              '<circle cx="32" cy="44" r="6" fill="$L"/><circle cx="50" cy="44" r="6" fill="$L"/><circle cx="68" cy="44" r="6" fill="$L"/>',
    "plane": '<path d="M8 46 L92 12 L66 88 L48 60Z" fill="$L"/><path d="M48 60 L92 12 L40 72Z" fill="$T"/><path d="M48 60 L40 72 L42 56" fill="$P"/>',
    "calendar": '<rect x="12" y="18" width="76" height="70" rx="10" fill="$L"/><path d="M12 28 C12 22 16 18 22 18 H78 C84 18 88 22 88 28 V38 H12Z" fill="$P"/>'
                '<path d="M32 10 V26 M68 10 V26" fill="none" stroke-width="6" stroke-linecap="round"/>'
                + "".join(f'<rect x="{22 + (i % 4) * 15}" y="{46 + (i // 4) * 14}" width="10" height="9" rx="2" fill="{"$A" if i == 5 else "$T"}" stroke="none"/>' for i in range(12)),
    "backpack": '<path d="M24 34 C24 22 34 14 50 14 C66 14 76 22 76 34 V84 C76 88 72 90 68 90 H32 C28 90 24 88 24 84Z" fill="$P"/>'
                '<rect x="32" y="56" width="36" height="24" rx="6" fill="$S"/><path d="M40 14 C40 6 60 6 60 14" fill="none" stroke-width="5"/><rect x="44" y="62" width="12" height="5" rx="2" fill="$A"/>',
    "ball": '<circle cx="50" cy="50" r="38" fill="$L"/><path d="M50 32 L66 44 L60 62 H40 L34 44Z" fill="$D"/>'
            '<path d="M50 32 V14 M66 44 L84 38 M60 62 L70 80 M40 62 L30 80 M34 44 L16 38" fill="none" stroke-width="3"/>',
    "dumbbell": '<rect x="28" y="44" width="44" height="12" rx="3" fill="$G"/><rect x="14" y="28" width="14" height="44" rx="4" fill="$P"/><rect x="72" y="28" width="14" height="44" rx="4" fill="$P"/>'
                '<rect x="6" y="38" width="8" height="24" rx="3" fill="$S"/><rect x="86" y="38" width="8" height="24" rx="3" fill="$S"/>',
    "flag": '<path d="M22 10 V92" fill="none" stroke-width="6"/><path d="M24 14 C40 6 54 22 80 14 V54 C54 62 40 46 24 54Z" fill="$P"/><circle cx="22" cy="10" r="5" fill="$A"/>',
    "sparkle": '<path d="M50 6 C54 34 66 46 94 50 C66 54 54 66 50 94 C46 66 34 54 6 50 C34 46 46 34 50 6Z" fill="$A"/><circle cx="80" cy="20" r="6" fill="$S"/><circle cx="22" cy="80" r="4" fill="$P"/>',
    "law": '<path d="M50 12 V84 M30 88 H70 M18 28 H82" fill="none" stroke-width="5"/><path d="M18 28 L8 56 H28Z" fill="$A"/><path d="M82 28 L72 56 H92Z" fill="$A"/><circle cx="50" cy="16" r="6" fill="$P"/>',
    "tractor": '<rect x="26" y="34" width="30" height="28" rx="3" fill="$P"/><rect x="30" y="38" width="16" height="12" rx="2" fill="$T"/><rect x="56" y="46" width="30" height="16" rx="3" fill="$P"/>'
               '<circle cx="36" cy="72" r="16" fill="$D"/><circle cx="36" cy="72" r="6" fill="$G"/><circle cx="78" cy="76" r="10" fill="$D"/><circle cx="78" cy="76" r="4" fill="$G"/><path d="M74 46 V30" fill="none" stroke-width="5"/>',
    "wheat": '<path d="M50 92 V22" fill="none" stroke-width="4"/>'
             + "".join(f'<ellipse cx="{50 + s * 9}" cy="{30 + i * 12}" rx="6" ry="10" fill="$A" transform="rotate({s * 30} {50 + s * 9} {30 + i * 12})"/>' for i in range(4) for s in (-1, 1))
             + '<ellipse cx="50" cy="18" rx="5" ry="9" fill="$A"/>',
}

# subject -> (keywords in uz / ru / en, stickers)
SUBJECTS = {
    "biology": (["biolog", "botan", "zoolog", "fotosintez", "hujayra", "o‘simlik", "o'simlik", "hayvon", "genetik", "биолог", "клетк", "растен", "biology", "cell", "plant"],
                ["leaf", "dna", "microscope", "cell", "butterfly", "flower", "tree", "fish", "sun", "drop"]),
    "chemistry": (["kimyo", "химия", "chemi", "molekul", "reaksiya", "element"],
                  ["flask", "atom", "molecule", "drop", "microscope", "thermometer", "lightning", "magnifier"]),
    "physics": (["fizika", "физик", "physic", "mexanika", "elektr", "optika", "energiya"],
                ["atom", "magnet", "bulb", "lightning", "rocket", "gear", "thermometer", "planet"]),
    "astronomy": (["astronom", "koinot", "kosmos", "sayyora", "астроном", "космос", "space", "planet"],
                  ["planet", "rocket", "telescope", "star", "sun", "earth", "sparkle", "atom"]),
    "math": (["matemat", "algebra", "geometr", "hisob", "математ", "алгебр", "геометр", "math", "statist"],
             ["compass", "ruler", "triangle", "pi", "calculator", "abacus", "cube", "protractor", "chart"]),
    "geography": (["geograf", "ekolog", "iqlim", "tabiat", "география", "эколог", "geograph", "ecolog", "climate"],
                  ["earth", "globe", "mountain", "pin", "volcano", "recycle", "tree", "drop", "sun"]),
    "history": (["tarix", "история", "histor", "arxeolog", "sivilizats", "imperiya"],
                ["column", "scroll", "hourglass", "castle", "crown", "quill", "globe", "flag"]),
    "literature": (["adabiyot", "ona tili", "til ", "tili", "she‘r", "she'r", "литератур", "язык", "literat", "language", "poetry"],
                   ["openbook", "quill", "book", "scroll", "lamp", "bubble", "masks", "pencil"]),
    "it": (["informat", "dastur", "kompyuter", "axborot", "it ", "sun’iy", "sun'iy", "intellekt", "информат", "программ", "computer", "program", "software", "ai"],
           ["laptop", "code", "robot", "chip", "cloud", "wifi", "gear", "gamepad"]),
    "economics": (["iqtisod", "moliya", "biznes", "menejment", "marketing", "buxgalter", "bank", "экономик", "финанс", "бизнес", "econom", "business", "finance", "market"],
                  ["coins", "piggy", "chart", "briefcase", "target", "megaphone", "wallet", "trend"]),
    "medicine": (["tibbiyot", "medits", "sog‘liq", "sog'liq", "anatom", "farmak", "stomatolog", "медицин", "здоров", "анатом", "medic", "health", "anatomy"],
                 ["heart", "pill", "cross", "tooth", "brain", "dna", "microscope", "thermometer"]),
    "psychology": (["psixolog", "pedagog", "falsafa", "психолог", "педагог", "философ", "psycholog", "philosoph", "pedagog"],
                   ["brain", "bubble", "lamp", "puzzle", "heart", "openbook", "sparkle", "target"]),
    "art": (["san’at", "san'at", "rasm", "dizayn", "musiqa", "teatr", "kino", "искусств", "музык", "дизайн", "art", "music", "design", "theatre"],
            ["palette", "brush", "note", "mic", "masks", "camera", "sparkle", "star"]),
    "law": (["huquq", "qonun", "davlat", "siyosat", "право", "закон", "law", "politic"],
            ["law", "scroll", "column", "flag", "book", "briefcase", "megaphone", "crown"]),
    "sport": (["sport", "jismoniy", "tarbiya", "спорт", "физкульт", "fitness"],
              ["ball", "dumbbell", "medal", "trophy", "clock", "target", "flag", "heart"]),
    "agriculture": (["qishloq", "agro", "dehqon", "сельск", "агро", "agricult", "farm"],
                    ["tractor", "wheat", "sun", "drop", "tree", "leaf", "flower", "recycle"]),
    "general": ([], ["bulb", "book", "target", "rocket", "pencil", "cap", "trophy", "puzzle", "calendar", "plane", "magnifier", "star"]),
}
