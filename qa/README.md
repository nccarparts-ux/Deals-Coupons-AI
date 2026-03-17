# Autonomous QA/Repair Agent

## Overview
This QA system automatically crawls the BidYard website, detects issues (console errors, broken images, navigation failures, accessibility problems), groups them by root cause, and attempts to fix common issues. It logs unresolved issues to `issues.jsonl` and resolved issues to `issues_resolved.jsonl`.

## Components

### Crawler (`crawler.js`)
- Spiders the site starting from homepage
- Discovers internal links (excludes external, mailto, tel, hash links)
- Detects:
  - Console errors
  - Page errors
  - Broken images
  - Empty links
  - Missing alt attributes
- Logs issues to `issues.jsonl`

### QA Agent (`agent.js`)
- Reads unresolved issues
- Groups by type and URL path
- Diagnoses root cause (branding namespace, undefined variable, missing resource, etc.)
- Applies fixes (currently only branding namespace fixes)
- Runs Playwright tests after fixes
- Commits successful fixes with descriptive message
- Logs resolved issues

### Runner Scripts
- `run.js` – Full QA cycle (start server, crawl, diagnose, fix)
- `crawl-only.js` – Just crawl and log issues
- `quickcrawl.js` – Quick test with limited pages
- `main.js` – Original main script (deprecated)

## Usage

### One-time QA cycle
```bash
npm run dev &  # Start dev server in background
node qa/run.js
```

### Continuous operation (background)
```bash
# Run every 5 minutes (example)
while true; do node qa/run.js; sleep 300; done
```

### Manual inspection of issues
```bash
cat issues.jsonl | jq .  # Requires jq
```

## Fixes Implemented

1. **Branding namespace** (`FNA` → `BY`)
   - Searches HTML files for `FNA.` references
   - Replaces with `BY.` using `sed`
   - Verified with Playwright tests

2. **Placeholder for other root causes** (undefined variable, missing resource, etc.)
   - Detection logic ready
   - Fix implementations pending

## Extending the Agent

### Adding a new fix
1. Add root cause detection in `diagnoseRootCause()`
2. Implement fix method `fixNewCause(url, message)`
3. Add case in `fixIssue()`

### Adding new issue detection
Modify `collectIssues()` in `crawler.js` to detect new problem types.

## Test Accounts
Planned: Automatically create buyer/seller/admin test accounts via Supabase API and test authentication flows.

## Priority Order
1. Navigation issues
2. API errors
3. Database mismatches
4. Authentication failures
5. Network errors
6. Console errors
7. Broken links
8. Accessibility issues
9. UI issues

## Notes
- Minimal edits: Only changes necessary to fix root cause
- Preserves architecture
- Avoids breaking changes
- Batches same-root-cause fixes
- Commits with message: "Autonomous QA fix: <type> <url>"