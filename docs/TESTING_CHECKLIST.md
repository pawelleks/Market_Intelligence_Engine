# TESTING CHECKLIST

**Purpose**: Mandatory pre-completion checklist for all development tasks  
**Rule**: Do NOT mark task "complete" until ALL applicable checks pass

---

## 📋 Universal Checks (Every Task)

- [ ] **Code runs without errors**
- [ ] **Follows 6-step pipeline pattern** (Fetch → Raw → Calculate → Processed → API → Frontend)
- [ ] **No hardcoded values** (0.000, placeholder data, etc.)
- [ ] **Documented changes** (what was modified and why)

---

## 📊 Data Pipeline Scripts

For any script in `scripts/`:

- [ ] **Runs individually** without errors
- [ ] **Loads from correct location** (raw data from `data/raw/`, NOT from API)
- [ ] **Saves to correct location** (processed to `data/processed/`)
- [ ] **Output file exists** and is not empty
- [ ] **Output has expected columns** and data types
- [ ] **Date ranges are correct** (start/end dates make sense)
- [ ] **No NaN values** in critical columns (or properly handled)
- [ ] **File size is reasonable** (not 0 bytes, not unexpectedly huge)

**Test command**: 
```bash
python3 scripts/{your_script}.py
ls -lh data/processed/{output_file}.parquet
```

---

## 🔌 API Endpoints

For any endpoint in `backend/routers/`:

- [ ] **Endpoint is registered** in router
- [ ] **Returns 200 status** (not 500 error)
- [ ] **Returns valid JSON** (not empty, not error message)
- [ ] **Data structure matches frontend expectations**
- [ ] **Latest data point is recent** (not outdated)
- [ ] **Historical data is complete** (no unexpected gaps)

**Test command**:
```bash
curl http://localhost:8000/api/macro/{endpoint}
# Should return JSON, not error
```

---

## 🖥️ Frontend Pages

For any page in `frontend/src/pages/`:

- [ ] **Page loads without errors** (check browser console)
- [ ] **Fetches data from API** (not hardcoded)
- [ ] **Displays current values correctly** (no 0.000 unless actually zero)
- [ ] **Charts render properly** (not blank, not error)
- [ ] **Status badges show correct states** (colors match values)
- [ ] **Responsive layout** (works on different screen sizes)
- [ ] **Loading states handled** (spinner or message while fetching)
- [ ] **Error states handled** (graceful failure if API down)

**Test steps**:
1. Open page in browser
2. Check browser console (F12) for errors
3. Verify data loads and displays
4. Refresh page - should load fresh data
5. Check mobile view if applicable

---

## 🔄 Full Pipeline Tests

For changes affecting multiple components:

- [ ] **Pipeline script executes** all steps without error
- [ ] **All intermediate files created** correctly
- [ ] **Final outputs exist** and are valid
- [ ] **API serves updated data** after pipeline runs
- [ ] **Frontend reflects new data** after refresh
- [ ] **No breaking changes** to existing functionality

**Test command**:
```bash
# Run full economic pipeline
python3 scripts/economic_pipeline.py

# Verify all outputs exist
ls -lh data/processed/
ls -lh data/analytics/

# Test API
curl http://localhost:8000/api/macro/lei
curl http://localhost:8000/api/macro/hamilton

# Open frontend and verify
```

---

## 🐛 Bug Fixes

For any bug fix:

- [ ] **Bug is reproducible** before fix
- [ ] **Fix addresses root cause** (not just symptom)
- [ ] **Bug no longer occurs** after fix
- [ ] **No new bugs introduced** (regression test)
- [ ] **Related functionality still works** (didn't break other features)

---

## 📝 Documentation

- [ ] **Code has comments** explaining non-obvious logic
- [ ] **New features documented** in appropriate place
- [ ] **Breaking changes noted** (if any)
- [ ] **Examples provided** for complex features

---

## 🚨 Critical Red Flags

**STOP and investigate if you see:**

- ⚠️ Output file is 0 bytes
- ⚠️ All values are 0.000 or NaN
- ⚠️ Date range doesn't cover expected period
- ⚠️ API returns error instead of data
- ⚠️ Frontend shows "undefined" or "null"
- ⚠️ Console has errors or warnings
- ⚠️ Script takes unusually long (>5 minutes for simple task)

**Do not proceed until these are resolved.**

---

## ✅ Completion Criteria

**Task is "complete" only when:**

1. ✅ All applicable checklist items pass
2. ✅ You've personally verified each component works
3. ✅ No known issues or warnings remain
4. ✅ Changes are documented

**If you skip testing and bugs appear in production, you must:**
1. Acknowledge the oversight
2. Fix all issues found
3. Re-test thoroughly
4. Document what went wrong and how to prevent it

---

## 📊 Example: Adding New Economic Model

**Checklist for complete implementation:**

- [ ] FRED series added to `data/fred_series.yaml`
- [ ] Calculation script created and tested
- [ ] Output parquet file exists in `data/processed/`
- [ ] Data looks correct (spot-check values)
- [ ] API endpoint added to router
- [ ] API returns valid JSON (curl test)
- [ ] Frontend page created
- [ ] Page loads without console errors
- [ ] Current values display correctly (not 0.000)
- [ ] Charts render with real data
- [ ] Status badge shows correct state
- [ ] Added to navigation menu
- [ ] Tested full flow: pipeline → API → frontend
- [ ] Documented in appropriate places

**Only then** can you say: "Complete! New model is live."

---

**Remember**: Quality over speed. Taking 10 extra minutes to test properly saves hours of debugging later.
