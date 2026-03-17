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
- Created complete Deals-Coupons-AI project from template
- Set up GitHub repository (nccarparts-ux/Deals-Coupons-AI)
- Deployed to Vercel (https://deals-coupons-ai.vercel.app)
- Created Supabase project with database schema (profiles, deals, coupons tables)
- Configured environment variables for DeepSeek and Supabase
- Updated Playwright tests for new project structure (40 tests passing)
- Created production test configuration

**Key Learnings:**
1. **Port Conflict Resolution**: When running multiple projects locally, change dev server port (3000 → 3001) to avoid conflicts with existing projects.
2. **Test Adaptation**: Update test expectations to match actual HTML structure when reusing test templates across different project types.
3. **Supabase Project Creation**: Use `npx supabase projects create` with organization ID to create cloud projects programmatically.
4. **Database Schema Design**: For deals/coupons platforms, use tables for profiles, deals, and coupons with appropriate RLS policies.
5. **Token Optimization**: To avoid API error 400 (request too large), use parallel agents, concise responses, and environment variable optimizations.

### Token Optimization Strategies
1. **Parallel Agent Execution**: For large-scale tasks (rebranding, file updates), launch multiple agents simultaneously to reduce overall token usage.
2. **Environment Configuration**: Set `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` and appropriate `ANTHROPIC_MAX_TOKENS` values.
3. **Concise Communication**: Keep responses focused, avoid unnecessary explanations, use bullet points instead of paragraphs.
4. **Specialized Tools**: Use Grep, Glob, Read tools instead of Bash commands for file operations to reduce output size.
5. **Memory Management**: Use `.ai_memory.json` and `.agent_memory.json` to store learnings across sessions, reducing need to re-explain.
6. **Template-Based Setup**: Create reusable project templates with placeholders to minimize repetitive code generation.

### 2026-03-17: Token Optimization System Implementation
**Accomplishments:**
- Created comprehensive token optimization system with scripts and documentation
- Implemented `skills/token-optimization.md` guide with practical strategies
- Created `scripts/token-monitor.js` for token usage estimation and recommendations
- Created `scripts/task-splitter.js` for splitting large tasks into parallel agent chunks
- Added environment variable presets (`.env.large-task`, `.env.quick-task`, `.env.qa-testing`)
- Updated `package.json` with optimization script commands
- Created `SKILLS_SUMMARY.md` for comprehensive tool overview
- Updated skills documentation to include token optimization

**Key Learnings:**
1. **Script-Based Optimization**: Create concrete scripts (`token-monitor.js`, `task-splitter.js`) that provide actionable recommendations rather than just documentation.
2. **Environment Presets**: Different task types (large refactoring, quick fixes, QA testing) need different token limits and timeouts.
3. **Exclusion Patterns**: Token estimation scripts must exclude `node_modules`, `test-results`, and `.git` directories to provide accurate file counts.
4. **Package.json Integration**: Add optimization commands to `package.json` for easy access (`npm run optimize:token-check`, `npm run optimize:split-task`).
5. **Comprehensive Documentation**: Combine strategies, scripts, and examples in skill files for easy reference.

**Token Optimization System Components:**
- **Monitoring**: `token-monitor.js` estimates tokens and recommends parallel execution
- **Splitting**: `task-splitter.js` groups files by type and generates agent prompts
- **Environment Presets**: Task-specific `.env` profiles with appropriate token limits
- **Documentation**: Complete guide in `skills/token-optimization.md`
- **Integration**: Scripts accessible via npm commands for workflow integration

**Usage Examples:**
```bash
# Check token usage for a task
npm run optimize:token-check -- "Update branding" "*.html"

# Split large task for parallel agents
npm run optimize:split-task -- --task "Fix JavaScript" --glob "*.js"

# Switch to large task profile
npm run optimize:large-task
```

---

**Optimized for:** Low token usage, parallel agent execution, efficient development workflows
**Tools:** Claude Code with DeepSeek model, Playwright tests, Supabase CLI, Vercel deployment, Autonomous QA system, Token optimization scripts
**Pattern:** Use multiple agents in parallel for large-scale tasks with token monitoring and task splitting