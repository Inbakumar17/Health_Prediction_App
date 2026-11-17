# Design

The interface blends two design references extracted by [Inspo](https://github.com/Nutlope/inspo) (MIT): **Newglyph** (a type foundry) and **Blockstream** (a fintech product site). Both are adapted, not copied: no logos, wording or paid fonts.

| | Newglyph | Blockstream |
|---|---|---|
| Mode | Dark | Dark |
| Layout | Type specimen: one huge headline | Feature stack: hero, then a row of feature cards |
| Signature colours | Electric yellow `#fbfb0c`, greys `#161616`–`#525252` | Teal `#00b093`, green `#00d395`, cyan `#04c3fb`, amber `#fcc076`, `#111316` / `#1e2024` |
| Shapes | Square inputs and buttons | 2px tags, 8px fields, 12px cards, 27px pill buttons |
| Type | Display face (africa), Baikal | Square technical headings (rigid-square), Inter body |

## What each part of the page uses

| Element | From | How |
|---|---|---|
| Page background | Blockstream `#111316` | Lifted with soft teal and cyan glows so it is not flat black |
| Headline "HEALTH **PREDICTION**" | Newglyph | Huge uppercase Anton; the second word in electric yellow with a faint glow |
| Eyebrow and table headings | Blockstream cyan | Monospace, uppercase, cyan |
| Three stat cards | Blockstream feature trio | Records (green), High risk (red), Rejected entries (Newglyph yellow), each with a coloured top line |
| Cards | Blockstream `#1e2024` | 12px corners, thin light border, soft shadow |
| Section titles | Blockstream headings | Square technical font (Chakra Petch), uppercase, with a small coloured square marker |
| "Save record" button | Blockstream teal → green | Pill shape, gradient; turns Newglyph yellow on hover |
| Inputs | Both | 8px corners (Blockstream), teal focus ring |
| Edit / Delete, search | Blockstream | Pill shapes; cyan on hover, red when confirming delete |
| Risk tags | Blockstream tokens | Red = high, amber = moderate, teal-green = low; 2px corners |
| Toast | Newglyph yellow | Yellow pill with black text |

## Fonts (free stand-ins for the paid ones)

| Role | Font |
|---|---|
| Display headline | Anton |
| Section titles and stat numbers | Chakra Petch |
| Body text | Inter |
| Units, labels, numbers in the table | IBM Plex Mono |

All fonts load from Google Fonts. If they can't load, system fallbacks are used.
