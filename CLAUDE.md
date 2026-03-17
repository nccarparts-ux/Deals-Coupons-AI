# Project Memory Bank

## 🎯 Project Conventions
- Use TypeScript with strict mode
- Follow functional programming patterns
- Write tests before implementation

## 🐛 Known Issues & Fixes
- TS2304 error: Missing import - always check import statements
- Authentication timeout: Caused by expired tokens, refresh before API calls
- Navigation not working: Caused by undefined JavaScript functions, missing event handlers, or syntax errors - ensure functions are globally defined and use multiple fallback mechanisms

## 📝 Lessons Learned
- Always read files before modifying them
- Use absolute imports (@/components) not relative paths
- Commit frequently with conventional commit format
- Remove debug console.log statements before deploying to production
- Ensure JavaScript functions are defined globally before inline onclick handlers execute
- Use JSON.stringify() for safer string escaping in JavaScript-generated HTML
- Implement multiple fallback navigation mechanisms (event delegation + data attributes + manual switching)
- Clean up external script dependencies causing 404 errors

## 🔄 Session History
<!-- Add new learnings here after each session -->

### 2026-03-17: Project Initialization
**Accomplishments:**
-

**Key Learnings:**
1.

---

**Optimized for:** Low token usage, parallel agent execution, efficient development workflows
**Tools:** Claude Code with DeepSeek model, Playwright tests, Supabase CLI, Vercel deployment, Autonomous QA system
**Pattern:** Use multiple agents in parallel for large-scale tasks (HTML updates, JavaScript fixes, test updates, config updates)