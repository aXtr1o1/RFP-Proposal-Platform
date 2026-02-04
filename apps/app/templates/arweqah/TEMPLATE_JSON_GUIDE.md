# Template JSON Files – What Each One Does

This guide explains every JSON file in a template folder and how the system uses it.

---

## 1. `config.json` (required)

**Role:** Main runtime configuration for the **native** generator. It drives which background to use, where to put text/icons, which fonts and colors to use, and how slide types map to layouts.

**Used by:** `pptx_generator.py`, `template_service.py`, `template_registry.py` (when registering legacy templates).

**Main sections:**

| Section | Purpose |
|--------|---------|
| `template_id`, `template_name`, `version`, `template_mode` | Identity and mode (e.g. `"native"`) |
| `slide_dimensions` | Width, height, aspect ratio (inches) |
| `language_settings` | Per-language: `rtl`, `alignment`, `default_font`, `heading_font` (e.g. `ar` / `en`) |
| `colors` | Palette: `primary`, `text.dark`, `text.light`, `elements.separator_line`, `elements.page_number_bg`, `elements.page_number_text`, `four_box` colors |
| `fonts` | Per slide type and element: `title_slide`, `section_header`, `content`, `agenda`, `four_box`, `page_number` — each with `name_en`, `name_ar`, `size`, `bold`, `color` |
| `icons` | `default_title`, `default_section`, `agenda_items[]`, `box_icons[]` — paths under the template folder (e.g. `Icons/icon_title_xxx.png`) |
| `layout_mapping` | Maps logical type (e.g. `blank`, `content`, `section_header`) to slide layout index in `template.pptx` |
| `content_type_mapping` | Maps content type (e.g. `bullets`, `chart`, `table`) to layout key (e.g. `title_and_content`) |
| `background_images` | Which background image file to use per type: `title_slide`, `section`, `content`, `chart`, `agenda`, etc. |
| `slide_color` | **Light/dark per slide type:** `"light"` = use dark text/icons, `"dark"` = use light text/icons. Keys: `title_slide`, `section`, `agenda`, `agenda_items`, `content`, `chart`, `table`, etc. |
| `element_positions` | Pixel-perfect positions (x, y, width, height in inches) for each slide type: `title_slide`, `section_header`, `content`, `agenda`, `four_box` (title, icon, separator, body, boxes) |
| `page_numbering` | `enabled`, `skip_title`, `skip_section`, `position_ar` / `position_en`, `shape`, `font` |
| `features` | Flags: `auto_fit_text`, `icon_integration`, `chart_generation`, `table_generation`, `rtl_support` |
| `localization` | Translated strings per language, e.g. `agenda_title`, `thank_you`, `questions` |

**In short:** For native generation, `config.json` is the single source for “what slide type uses which background, where elements go, which font/color, and whether the slide is light or dark.”

---

## 2. `constraints.json` (optional but recommended)

**Role:** Design and validation rules: sizes, limits, and default styling for tables, charts, bullets, typography, and colors. Used so tables/charts/bullets look consistent and stay within safe bounds.

**Used by:** `chart_service.py`, `table_service.py`, `pptx_generator.py` (e.g. `slide_color` fallback).

**Main sections:**

| Section | Purpose |
|--------|---------|
| `layout` | Slide size, margins, content area, safe zone |
| `text_constraints` | Max lengths for title, subtitle, bullet, paragraph; truncation |
| `bullets` | Max bullets per slide, indent (AR/EN), spacing, symbols, colors, font sizes by level |
| `table` | Max rows/columns, header/body fonts and colors, borders, padding, RTL |
| `chart` | Max data points/series, default size, color palette, fonts, axis/legend/data-label colors, grid |
| `typography` | Fonts and sizes for title, heading_1–3, body, caption, agenda |
| `colors` | Same idea as config (primary, background, text, accents) — can mirror or extend config |
| `alignment` | Per language: default, title, body, bullets, table, agenda, section, caption |
| `slide_color` | Same as config: which slide types are `"light"` vs `"dark"` (fallback if missing in config) |
| `icons` | Sizes and behavior: `section_icon_size`, `agenda_icon_size`, `auto_select`, `position_ar` / `position_en` |
| `agenda`, `boxes` | Layout and sizing for agenda and four-box slides |
| `page_numbering` | Style and position details |
| `images` | Max size, quality, aspect ratio |
| `validation` | Strict mode, truncation, color/font checks |

**In short:** `constraints.json` defines “how big, how many, and what default style” for content (tables, charts, bullets) and can supply `slide_color` and colors if you prefer to keep design rules here.

---

## 3. `layouts.json` (optional – layout definitions)

**Role:** Declarative layout definitions: for each slide type (title_slide, agenda_slide, title_and_content, section_header_*, table_slide, chart_slide, four_box_with_icons, etc.) it lists elements (logo, title, subtitle, icon, content, table, chart, boxes) with positions and styles. Used by code paths that build slides from a “layout recipe” rather than only from `config.json` positions.

**Used by:** `template_registry.py` (when converting legacy config + layouts into a manifest), and potentially placeholder/layout-driven builders.

**Structure:** One key per layout (e.g. `title_slide`, `agenda_slide`, `title_and_content`). Each has:

- `name`, `description`, `master_layout`
- `background`: `type`, `path`, `fit`
- `elements[]`: each with `id`, `type` (text, text_bullets, image, icon, line, table, chart, boxes), `placeholder`, `position` / `position_ar` / `position_en`, `size`, `style` (font, color, alignment, etc.)

**In short:** `layouts.json` describes “for this slide type, these are the elements, their types, positions, and styles.” The native generator mainly uses `config.json` + `element_positions`; `layouts.json` is used for registration and for any layout-driven generation.

---

## 4. `manifest.json` (optional – analyzed from PPTX)

**Role:** Describes the actual slide layouts inside `template.pptx`: layout index, placeholder types and positions. Used to choose the correct layout index for a content type and to know where placeholders are. Can be **generated** by analyzing the PPTX (e.g. `template_analyzer.py`).

**Used by:** `pptx_generator.py` (fallback for `element_positions`, `fonts`, `icons`, `colors`), `layout_mapper.py`, `slide_builder.py`, `template_registry.py`, `template_service.py`.

**Main sections:**

| Section | Purpose |
|--------|---------|
| `template_id`, `template_name`, `version`, `template_mode` | Same idea as config |
| `slide_dimensions` | Width, height, aspect ratio |
| `layouts` | One entry per layout in the PPTX: `index`, `name`, `placeholders[]` (idx, type, name, position, content_hint) |
| `content_type_mapping` | Maps content type (e.g. `bullets`, `chart`) to a layout key (e.g. `title_and_content`) |
| `background_images` | Background image path per layout/slide type |
| `element_positions` | Same idea as config — fallback if not in config |
| `fonts` / `colors` / `icons` | Fallback theme data if not in config |

**In short:** `manifest.json` is the “map” of the PPTX (layout indices and placeholders). The generator prefers `config.json`; when something is missing in config it can fall back to the manifest.

---

## 5. `theme.json` (optional)

**Role:** Theme-level colors, typography, and spacing. Used for icon keyword mapping and as a single place to define “brand” look (e.g. for IconService or other consumers that read theme rather than config).

**Used by:** `pptx_generator.py` (fallback theme), `icon_service.py` (e.g. `theme.json` under template folder for icon keyword/tag mapping).

**Main sections:**

- `theme_id`, `theme_name`, `version`, `description`
- `colors`: primary, background, text, accents (same kind of names as config/constraints)
- `typography`: font_families (primary, heading, body, english_primary, …), font_sizes (title, heading_1–4, body, caption, table), line_spacing
- `spacing`: slide_margin, content_padding, element_spacing

**In short:** `theme.json` is the theme/brand layer (colors + fonts + spacing). The native generator gets most of what it needs from `config.json` and `constraints.json`; `theme.json` is used for defaults and for services like IconService.

---

## 6. `icon_keywords.json` (optional)

**Role:** Maps **heading keyword categories** (e.g. strategy, team, goals, data) to **specific icon filenames** in the template’s `Icons/` folder. So when a slide title matches a keyword, that slide gets the corresponding icon instead of a random or generic one.

**Used by:** `pptx_generator.py` when selecting an icon for a content or section heading (`_select_icon_for_content`).

**Structure:**

- `description`: short explanation
- `category_to_icon`: object mapping category name → path, e.g.  
  `"strategy": "Icons/icon_title_97cc958fb024.png"`,  
  `"team": "Icons/icon_title_9a2209e06283.png"`

Categories should align with the keyword list used in the generator (e.g. strategy, team, leadership, goals, growth, technology, data, security, process, …). You can add or change entries to match your icon set.

**In short:** `icon_keywords.json` makes “heading text → icon” deterministic and relevant by mapping keyword categories to specific icon files.

---

## How they work together (native generation)

1. **config.json** – Primary source for: slide type → background, positions, fonts, colors, `slide_color`, icons list, page numbering, localization.
2. **constraints.json** – Rules and defaults for tables, charts, bullets, and optional `slide_color`/color fallbacks.
3. **slide_color** (in config or constraints) – Decides per slide type whether to use light or dark text/icons (bright slide → dark font, dark slide → light font).
4. **manifest.json** – Layout indices and placeholders from the PPTX; used when config doesn’t have positions/fonts/icons/colors.
5. **theme.json** – Theme/brand defaults; used by IconService and as fallback theme.
6. **icon_keywords.json** – Picks which icon file to use for a given heading category.
7. **layouts.json** – Layout “recipes” (elements and styles); used for registration and layout-driven flows, not the main path for the native generator.

If you only care about “what does the generator use at runtime,” the order is: **config.json** first, then **constraints.json** and **manifest.json** for fallbacks, then **theme.json** and **icon_keywords.json** for theme and icon choice.
