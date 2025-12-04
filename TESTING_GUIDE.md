# PowerPoint Generation - Testing Guide

## Quick Test Checklist

### Prerequisites
- Have a test RFP/proposal with typical content (team, deliverables, timeline, budget)
- Access to the PPT generation system
- Ability to generate presentations

---

## 🔴 CRITICAL TESTS (Must Pass)

### 1. Empty Slide Prevention
**What to check**: No slides should be completely empty

**How to test**:
1. Generate a presentation
2. Open the PowerPoint file
3. Go through EVERY slide
4. ✅ PASS: All slides have visible content (text, table, chart, or image)
5. ❌ FAIL: Any slide is completely blank

**Expected Result**: Zero empty slides

---

### 2. Table Slides (Slides 22-23, 29, 33, 34)
**What to check**: Tables render with actual data

**How to test**:
1. Look for these slides by title:
   - "Team Structure" or similar (around slide 22-23)
   - "Deliverables" or "Project Deliverables" (around slide 29)
   - "Payment Structure" or "Payment Schedule" (around slide 33)
   - "Performance Indicators" or "KPIs" (around slide 34)

2. For EACH table slide, verify:
   - ✅ Table is visible (not empty)
   - ✅ Has headers (3-5 columns)
   - ✅ Has 4+ rows of data
   - ✅ All cells have meaningful text (not "TBD" or "N/A")
   - ✅ Data is specific (not "Various tools" or generic)

**Expected Result**: All tables render with specific data

**What if it fails?**:
- Check backend logs for "Table has no headers" or "Table has no rows"
- Verify OpenAI generated `table_data` in response
- Check if source markdown has relevant information

---

### 3. Chart Slides (Slide 26, others)
**What to check**: Charts render with data

**How to test**:
1. Look for these slides by title:
   - "Timeline" or "Project Timeline" (around slide 26)
   - "Budget" or "Budget Allocation"
   - "Performance Metrics" or "KPIs"

2. For EACH chart slide, verify:
   - ✅ Chart is visible (not blank)
   - ✅ Has data bars/lines/pie sections
   - ✅ Has axis labels (for bar/column/line charts)
   - ✅ Has legend (if multiple series)
   - ✅ Shows actual numbers (not all zeros)

**Expected Result**: All charts render with real data

**What if it fails?**:
- Check for error message textbox on slide (red text)
- Check backend logs for "Invalid chart data"
- Verify chart_data structure in OpenAI response

---

### 4. Text Formatting (Slides 5, 27, 30)
**What to check**: Long text broken into bullets

**How to test**:
1. Look for these slides:
   - Executive Overview/Summary (around slide 5)
   - Methodology/Phases (around slide 27)
   - Assumptions (around slide 30)

2. For EACH text slide, verify:
   - ✅ Text is in bullet format (not long paragraph)
   - ✅ Each bullet is < 120 characters
   - ✅ Has 4-6 bullets maximum
   - ✅ Text is readable and well-spaced

**Expected Result**: No dense text blocks

**What if it fails?**:
- Check if `text_formatter.py` is being called
- Check logs for "Converting long paragraph to bullets"
- Verify paragraph length in source

---

## 🟡 IMPORTANT TESTS (Should Pass)

### 5. Content Detail Preservation
**What to check**: Specific details from Phase 1 retained

**How to test**:
1. Compare with Phase 1 presentation or source RFP

2. Check these specific slides:
   - **Technical Framework (Slide 12)**:
     - ✅ Mentions specific framework names (e.g., "SWOT Analysis", not "various methods")
     - ✅ Includes how components work together
   
   - **Methodology (Slide 14)**:
     - ✅ Lists specific procedural steps (not just "Phase 1, Phase 2")
     - ✅ Includes tools/techniques used
     - ✅ Shows timeframes (weeks, durations)
   
   - **Team slides**:
     - ✅ Shows specific roles (not just "Team Member")
     - ✅ Includes detailed responsibilities (not just "Various tasks")
     - ✅ Shows experience levels (years)
     - ✅ Shows time allocation percentages

**Expected Result**: Specific details preserved, no generic text

---

### 6. Contact Information (Last Slide)
**What to check**: Closing slide has contact info

**How to test**:
1. Go to the last slide (Thank You slide)
2. Check if there's a follow-up slide with:
   - ✅ Company/team name
   - ✅ Contact person name and title
   - ✅ Email address
   - ✅ Phone number (if in source)
   - ✅ Website (if in source)

**Expected Result**: Contact information present if available in source

---

## 🟢 NICE-TO-HAVE TESTS

### 7. Visual Quality
- Images are diverse (not same image repeated)
- Icons are relevant to slide content
- Colors are consistent
- Layout is balanced

### 8. Content Completeness
- All sections from source RFP are covered
- Agenda items match section headers
- No orphaned section headers (section without content)
- Thank You slide is last

---

## Test Scenarios

### Scenario A: Complete RFP (Full Test)
**Input**: Full RFP with all sections (team, budget, timeline, etc.)

**Expected Output**:
- 20-30 slides
- 3+ tables (team, deliverables, payment)
- 3+ charts (timeline, budget, KPIs)
- All specific details preserved
- No empty slides

**How to verify**:
1. Count tables: Should be 3-5
2. Count charts: Should be 3+
3. Check detail level: Specific, not generic
4. Check formatting: Bullets not paragraphs

---

### Scenario B: Minimal Content (Edge Case)
**Input**: Brief proposal with limited details

**Expected Output**:
- 10-15 slides minimum
- At least 1 table (even if estimated)
- At least 1 chart (even if estimated)
- Error placeholders if data truly missing
- No crashes or blank slides

**How to verify**:
1. Check for error messages: Should be visible, not crashes
2. Check for placeholders: "No data provided" is acceptable
3. System should complete without errors

---

### Scenario C: Arabic Language (RTL Test)
**Input**: RFP in Arabic

**Expected Output**:
- All text right-aligned
- Tables render correctly (RTL)
- Charts have Arabic labels
- Icons still load (icon names in English)
- All other tests pass

**How to verify**:
- Text alignment is right-to-left
- Tables read right-to-left
- No broken layouts

---

## Debugging Guide

### If Tables Are Empty

1. **Check Backend Logs**:
   ```
   Look for:
   - "❌ Table has no headers"
   - "❌ Table has no rows"
   - "⚠️ Creating error placeholder table"
   ```

2. **Check OpenAI Response**:
   - Does the JSON have `table_data` field?
   - Does `table_data` have `headers` and `rows`?
   - Are rows populated with data?

3. **Check Validation**:
   - Look in `content_validator.py` logs
   - Check if `_has_valid_table()` returned False

4. **Quick Fix**:
   - If AI didn't generate tables, check prompt clarity
   - Ensure source markdown has relevant info
   - Check if table requirements are in prompt

---

### If Charts Are Empty

1. **Check Backend Logs**:
   ```
   Look for:
   - "❌ Invalid chart data: Categories array is empty"
   - "❌ Invalid chart data: Series values are empty"
   - "Data mismatch: X categories but Y values"
   ```

2. **Check OpenAI Response**:
   - Does JSON have `chart_data` field?
   - Does it have `categories` and `series`?
   - Do series have `values` arrays?

3. **Check Validation**:
   - Look for "Chart Error" text on slide (red)
   - Check error message for specific issue

4. **Quick Fix**:
   - Verify chart structure matches expected format
   - Ensure categories and values have same length
   - Check if values are numeric

---

### If Text Is Too Dense

1. **Check Logs**:
   ```
   Look for:
   - "📝 Converting long paragraph to bullets"
   - "✅ Converted to X bullet points"
   ```

2. **Check Paragraph Length**:
   - If > 500 chars, should auto-convert
   - If not converting, check `text_formatter.py` import

3. **Quick Fix**:
   - Verify `should_convert_to_bullets()` is being called
   - Check if text formatter is imported in `pptx_generator.py`

---

## Performance Benchmarks

### Generation Time
- Small presentation (10-15 slides): 1-2 minutes
- Medium presentation (20-25 slides): 2-4 minutes
- Large presentation (30+ slides): 4-6 minutes

### Success Rates (Expected)
- Table generation: 95%+ (with error placeholders for failures)
- Chart generation: 90%+ (with error messages for failures)
- Text formatting: 95%+ automatic conversion
- No empty slides: 100% (always has content or error message)

---

## Reporting Issues

### Issue Template

**Issue**: [Brief description]

**Slide Number**: [Which slide has the issue]

**Expected**: [What should appear]

**Actual**: [What actually appears]

**Logs**: [Relevant log excerpts]

**Screenshot**: [If possible]

**Source**: [Relevant section from input markdown]

---

### Common Issues and Solutions

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| All tables empty | AI didn't generate table_data | Check prompt, verify source has data |
| Specific table empty | Table validation failed | Check validation logs, verify data structure |
| Chart has error message | Invalid chart data | Check categories/values alignment |
| Text still in paragraphs | Formatter not triggered | Verify text length > 500 or sentences > 3 |
| Generic content | Source lacks detail OR AI summarized | Enhance prompt emphasis, check source |
| Empty slide | Content validation failed | Check logs, verify slide has at least one content field |

---

## Success Metrics

✅ **Excellent Quality**:
- 0 empty slides
- All tables render with specific data
- All charts render with valid data
- Text well-formatted (bullets not paragraphs)
- Specific details preserved from source

✅ **Good Quality**:
- 0 empty slides
- 90%+ tables render
- 90%+ charts render
- Most text well-formatted
- Most details preserved

⚠️ **Needs Improvement**:
- 1-2 empty slides
- 70-90% tables render
- 70-90% charts render
- Some dense text blocks
- Some generic content

❌ **Poor Quality**:
- 3+ empty slides
- < 70% tables render
- < 70% charts render
- Many dense text blocks
- Mostly generic content

---

## Next Steps After Testing

### If All Tests Pass ✅
1. Deploy to production
2. Monitor first few generations
3. Collect user feedback

### If Some Tests Fail ⚠️
1. Review logs for specific errors
2. Check AI prompt clarity
3. Verify source markdown quality
4. Re-test after adjustments

### If Many Tests Fail ❌
1. Review implementation
2. Check for integration issues
3. Verify all files are updated
4. Check OpenAI API responses

---

## Support

For issues:
1. Check this testing guide first
2. Review `IMPROVEMENTS_IMPLEMENTED.md` for details
3. Check code comments in modified files
4. Review backend logs for errors

