# Arweqah Template JSON Configuration

## Overview
Complete JSON configuration for the **Arweqah Horizontal Professional Theme** PowerPoint template.
This is a professional bilingual (Arabic/English) template with elegant teal, cream, and warm accent colors.

## Template Specifications

### Dimensions
- **Width:** 13.33 inches (12,192,000 EMUs)
- **Height:** 7.5 inches (6,858,000 EMUs)
- **Aspect Ratio:** 16:9 (widescreen)

### Color Palette
| Color Name | Hex Code | Usage |
|------------|----------|-------|
| Primary (Dark Teal) | #01415C | Main brand color, headers, section backgrounds |
| Primary Dark (Very Dark Teal) | #0D2026 | Text color, dark backgrounds |
| Primary Light (Medium Teal) | #40697A | Secondary text, accents |
| Secondary (Sage Green) | #84BA93 | Section headers, borders, success elements |
| Accent (Rust Orange) | #C26325 | Call-to-action, highlights, important sections |
| Accent Alt (Golden Yellow) | #F9D462 | Warning, emphasis |
| Accent Green (Mint) | #B1D8BE | Subtle accents, charts |
| Background (Cream) | #FFFDED | Master background |
| Background Alt (Ivory) | #FFFCEC | Text on dark backgrounds, card backgrounds |
| Background Gray (Warm Taupe) | #C6C3BE | Neutral backgrounds, alternate rows |
| Background Beige | #F7F4E7 | Alternate table rows, subtle backgrounds |

### Typography

#### Fonts
- **Arabic:** Tajawal (regular, medium, extrabold)
- **English:** Montserrat SemiBold
- **Fallback:** Arial

#### Font Sizes
| Element | Size (pt) |
|---------|-----------|
| Title | 44 |
| Heading | 32 |
| Subheading | 28 |
| Body | 18 |
| Sub-bullet | 16 |
| Caption | 14 |
| Table Header | 16 |
| Table Body | 14 |

### Features
- ✅ RTL (Right-to-Left) text support
- ✅ Bilingual mode (Arabic/English)
- ✅ 11 versatile layouts
- ✅ Custom embedded fonts
- ✅ Cultural sensitivity in design
- ✅ Professional color scheme
- ✅ Flexible content structures

## File Descriptions

### 1. arweqah_config.json
Master configuration file containing:
- Template metadata (ID, name, version, description)
- Theme colors (primary, secondary, accent, background, text colors)
- Typography settings (fonts, sizes, RTL support)
- Slide dimensions
- Background definitions for different layout types
- Decorative elements configuration
- Icon settings
- Content limits and constraints
- Table configuration
- Image generation settings
- AI configuration for smart features

**Key Features:**
- Bilingual font configuration
- RTL text support enabled
- Custom color palette matching template exactly
- Image generation prompts for Middle Eastern context

### 2. arweqah_constraints.json
Visual styling constraints and standards:
- Table styling (header colors, alternating rows, borders)
- Chart color palettes (bar, pie, line charts)
- Layout spacing constraints (margins, padding, content areas)
- Text constraints (max widths, line spacing, alignment)
- RTL-specific settings

**Key Features:**
- Consistent visual standards
- RTL-aware alignment rules
- Template-specific color usage guidelines

### 3. arweqah_theme.json
Comprehensive theme system:
- Complete color palette with all shades and variations
- Gradient definitions
- Typography system (families, sizes, weights, line heights)
- Spacing standards (padding, margins, element spacing)
- Icon configuration with keyword mapping
- Bullet styles
- Chart colors
- Table styles
- Image configuration
- Content limits
- Pagination settings
- Localization settings (RTL, bilingual mode)

**Key Features:**
- 30+ color definitions
- 7 font families
- Intelligent icon keyword mapping
- Cultural localization support

### 4. arweqah_layouts.json
Detailed definitions for all 11 slide layouts:

#### Layout 1: Title Slide 1
- **Type:** Title
- **Background:** Split design (35% image with teal overlay, 65% cream)
- **Use:** Presentation opening, cover slides
- **Features:** Abstract decorative imagery, bilingual title support

#### Layout 2: Title and Content
- **Type:** Content
- **Background:** Cream solid
- **Use:** Bullet points, text-heavy content, general information
- **Features:** Full-width content area, supports tables

#### Layout 3: Section Header 2
- **Type:** Section
- **Background:** Mint green (#84BA93)
- **Use:** Gentle section breaks, growth topics
- **Features:** Centered placeholder box, large readable text

#### Layout 4: Section Header 1
- **Type:** Section
- **Background:** Dark teal (#01415C)
- **Use:** Major section breaks, corporate dividers
- **Features:** High contrast, professional feel

#### Layout 5: Section Header 3
- **Type:** Section
- **Background:** Rust orange (#C26325)
- **Use:** Action sections, call-to-action dividers
- **Features:** Warm energetic feel, eye-catching

#### Layout 6: Two Content
- **Type:** Two Column
- **Background:** Cream solid
- **Use:** Comparisons, side-by-side content
- **Features:** Equal-width columns, balanced layout

#### Layout 7: Title Only
- **Type:** Content
- **Background:** Cream solid
- **Use:** Large charts, full-slide tables, custom graphics
- **Features:** Maximum content flexibility, full content area

#### Layout 8: BLANK
- **Type:** Blank
- **Background:** Very dark teal (#0D2026)
- **Use:** Full-screen images, dramatic transitions
- **Features:** No constraints, creative freedom

#### Layout 9: Blank
- **Type:** Blank
- **Background:** Cream solid
- **Use:** Custom layouts, clean canvas
- **Features:** Light background, flexible positioning

#### Layout 10: Custom Layout
- **Type:** Content
- **Background:** Cream solid
- **Use:** Unique arrangements, mixed media
- **Features:** Supports decorative images, flexible design

#### Layout 11: 4_Blank
- **Type:** Blank
- **Background:** Warm gray (#C6C3BE)
- **Use:** Subtle transitions, neutral content
- **Features:** Sophisticated neutral tone

## Metadata in Layouts

Each layout includes comprehensive metadata:

### suitable_for
Array of use cases and content types ideal for the layout

### content_structure
Detailed specifications for:
- Title positioning, max length, font size, alignment
- Content areas with dimensions and constraints
- Column specifications for multi-column layouts
- RTL support indicators

### table_support
- Enabled status
- Maximum columns and rows
- Positioning guidelines
- Styling recommendations

### chart_support
- Size constraints
- Ideal use cases

### visual_elements
Array describing the visual design elements present

### constraints
Precise positioning data:
- Content area coordinates (left, top, width, height)
- Title area coordinates
- Column spacing
- Margins and padding
- Special layout-specific constraints

## Usage Guidelines

### RTL Text Support
All layouts support RTL text rendering:
- Text alignment defaults to "right" for Arabic
- Font selection automatically switches between Tajawal (Arabic) and Montserrat (English)
- Bullet points and list formatting respect text direction

### Color Usage
- **Primary colors (#01415C, #0D2026):** Professional, corporate content
- **Secondary colors (#84BA93):** Growth, success, positive content
- **Accent colors (#C26325):** Call-to-action, highlights, warnings
- **Backgrounds (#FFFDED, #FFFCEC):** Content slides, light areas
- **Text (#0D2026 on light, #FFFCEC on dark):** Ensure readability

### Table Styling
- Header: Dark teal background (#01415C), cream text (#FFFCEC)
- Body: Dark teal text (#0D2026), alternate beige rows (#F7F4E7)
- Borders: Sage green (#84BA93)
- No rounded corners (set to 0)

### Chart Colors
Use in order for consistency:
1. #01415C (Dark Teal)
2. #C26325 (Rust Orange)
3. #84BA93 (Sage Green)
4. #F9D462 (Golden Yellow)
5. #40697A (Medium Teal)
6. #B1D8BE (Mint Green)
7. #0D2026 (Very Dark Teal)
8. #C6C3BE (Warm Gray)

## Implementation Notes

### Font Embedding
Ensure fonts are embedded in the final PPTX:
- Tajawal-regular.fntdata
- Tajawal-bold.fntdata
- TajawalMedium-regular.fntdata
- TajawalMedium-bold.fntdata
- TajawalExtraBold-bold.fntdata
- MontserratSemiBold-regular.fntdata
- MontserratSemiBold-bold.fntdata
- MontserratSemiBold-italic.fntdata
- MontserratSemiBold-boldItalic.fntdata

### Layout Selection Logic
Recommended automatic selection:
- **Title slides:** Use "Title Slide 1"
- **Bullet content:** Use "Title and Content"
- **Section breaks:** Alternate between Section Header 1, 2, 3 based on tone
- **Comparisons:** Use "Two Content"
- **Large tables/charts:** Use "Title Only"
- **Full-screen images:** Use appropriate Blank layout
- **Creative content:** Use "Custom Layout"

### Content Optimization
- Keep titles under 80 characters
- Limit bullet points to 5 per slide
- Maximum 120 characters per bullet
- Maximum 3 sub-bullets per main bullet
- Tables: 8 rows × 6 columns maximum
- Auto-pagination enabled for overflow

## Support
This configuration was generated through deep analysis of the actual PowerPoint template file.
All colors, fonts, dimensions, and layout structures are extracted directly from the template
and do NOT use reference template values.

---
**Note:** This is a professional template configuration designed for both Arabic and English
presentations with cultural sensitivity and modern design principles.
