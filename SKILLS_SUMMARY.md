# Skills Summary

Comprehensive overview of all development tool skills and optimization strategies for the Deals-Coupons-AI project.

## 🛠️ Core Development Tools

### 1. **Supabase CLI** (`skills/supabase-cli.md`)
**Purpose**: Backend development with PostgreSQL database, authentication, and real-time features.

**Key Capabilities:**
- Local development environment setup
- Database migrations and seeding
- Authentication management (users, roles, policies)
- Storage bucket configuration
- Edge functions deployment
- Project linking and configuration

**Common Commands:**
```bash
npx supabase start          # Start local development
npx supabase status         # Check service status
npx supabase db push        # Push migrations to cloud
npx supabase gen types      # Generate TypeScript types
```

### 2. **Playwright Testing** (`skills/playwright-testing.md`)
**Purpose**: End-to-end testing for web applications across multiple browsers.

**Key Capabilities:**
- Cross-browser testing (Chromium, Firefox, WebKit)
- Mobile device emulation
- API testing
- Visual regression testing
- Test reporting and tracing
- CI/CD integration

**Common Commands:**
```bash
npm test                    # Run all tests
npm run test:ui            # Run with UI mode
npx playwright test --grep "homepage"  # Run specific tests
npx playwright show-report  # Show last test report
```

### 3. **Vercel Deployment** (`skills/vercel-deployment.md`)
**Purpose**: Static site deployment and serverless functions hosting.

**Key Capabilities:**
- Instant deployment from git
- Preview deployments for PRs
- Custom domain configuration
- Environment variables management
- Serverless functions
- Analytics and monitoring

**Common Commands:**
```bash
vercel login                # Authenticate with Vercel
vercel deploy               # Deploy to preview
vercel --prod               # Deploy to production
vercel alias set           # Set custom domain
vercel env add             # Add environment variable
```

### 4. **Token Optimization** (`skills/token-optimization.md`)
**Purpose**: Optimize Claude Code with DeepSeek API usage to prevent "API error 400" and maximize productivity.

**Key Capabilities:**
- Environment variable presets for different task sizes
- Parallel agent execution patterns
- Token usage estimation and monitoring
- Task splitting for large-scale changes
- Communication optimization techniques
- Troubleshooting common API errors

**Common Commands:**
```bash
node scripts/token-monitor.js "Task" "*.html"
node scripts/task-splitter.js "Large task" --glob "**/*.js"
cp .env.large-task .env     # Switch to large task profile
```

## 🔄 Workflow Integration

### New Project Setup
1. **Initialize Project**: Copy template files, update placeholders
2. **Backend Setup**: Run Supabase migrations, configure auth
3. **Testing Setup**: Install Playwright, write initial tests
4. **Deployment Setup**: Connect to Vercel, configure domains
5. **Optimization Setup**: Configure token optimization scripts

### Daily Development Workflow
1. **Task Analysis**: Use `token-monitor.js` to estimate complexity
2. **Environment Selection**: Choose appropriate `.env` profile
3. **Execution Strategy**: Decide on single vs parallel agents
4. **Development**: Implement changes with appropriate tools
5. **Testing**: Run Playwright tests locally
6. **Deployment**: Deploy to Vercel preview
7. **Verification**: Run production tests

### Large-Scale Refactoring Workflow
1. **Assessment**: Analyze scope with token monitor
2. **Planning**: Split task with `task-splitter.js`
3. **Parallel Execution**: Launch multiple agents simultaneously
4. **Integration**: Merge changes from all agents
5. **Testing**: Comprehensive test suite execution
6. **Deployment**: Staged deployment to production

## 🎯 Optimization Strategies

### Token Optimization
1. **Environment Presets**:
   - `.env.large-task`: 8192 tokens, 20min timeout (major refactoring)
   - `.env.quick-task`: 2048 tokens, 5min timeout (bug fixes)
   - `.env.qa-testing`: 3072 tokens, 15min timeout (QA automation)

2. **Parallel Agent Patterns**:
   - **File Type Split**: HTML, JS, tests, config agents in parallel
   - **Phase Split**: Research → Implementation → Verification phases
   - **Size Split**: Large groups divided by file count

3. **Communication Optimization**:
   - Concise prompts with bullet points
   - File paths with line numbers (`file.js:123`)
   - Reference existing solutions in `CLAUDE.md`
   - Use skill files as quick references

### Tool Integration
1. **Claude Code Integration**:
   - DeepSeek API configuration
   - Permission management in `.claude/settings.local.json`
   - Memory system with `.ai_memory.json` and `CLAUDE.md`

2. **Autonomous QA System**:
   - Production site crawling
   - Error detection and analysis
   - Automated fix application
   - Test verification

3. **Continuous Testing**:
   - Local test execution
   - Production testing with separate config
   - Cross-browser compatibility
   - Mobile responsiveness testing

## 📊 Performance Metrics

### Target Optimization Goals
- **API Error Reduction**: < 1% "request too large" errors
- **Task Completion Time**: 30-50% reduction with parallel agents
- **Token Usage Efficiency**: 20-40% reduction with optimization
- **Test Coverage**: > 80% of critical user flows
- **Deployment Time**: < 5 minutes for standard changes

### Monitoring Indicators
- **Token Usage**: Monitor with `token-monitor.js`
- **Test Pass Rate**: Track with Playwright reports
- **Deployment Success**: Monitor Vercel deployment logs
- **API Errors**: Watch for DeepSeek API error patterns
- **Agent Efficiency**: Measure time per agent vs task complexity

## 🆘 Troubleshooting Guide

### Common Issues and Solutions

1. **API Error 400: Request Too Large**
   - **Solution**: Split task with `task-splitter.js`
   - **Prevention**: Use `.env.large-task` for complex tasks

2. **Agent Timeout**
   - **Solution**: Increase `API_TIMEOUT_MS` in `.env`
   - **Prevention**: Break complex tasks into phases

3. **Test Failures in Production**
   - **Solution**: Use `playwright.config.production.js`
   - **Prevention**: Run production tests before deployment

4. **Database Connection Issues**
   - **Solution**: Check Supabase project status
   - **Prevention**: Use migration scripts for schema changes

5. **Deployment Failures**
   - **Solution**: Check Vercel build logs
   - **Prevention**: Test locally before deployment

## 📚 Learning Resources

### Internal Documentation
- `CLAUDE.md`: Project memory bank and learnings
- `.ai_memory.json`: Agent memory for repeated patterns
- Skills directory: Tool-specific guides
- Scripts directory: Automation and optimization tools

### External Resources
- **Supabase**: https://supabase.com/docs
- **Playwright**: https://playwright.dev/docs
- **Vercel**: https://vercel.com/docs
- **DeepSeek API**: https://platform.deepseek.com/api-docs
- **Claude Code**: https://claude.com/claude-code

## 🔄 Continuous Improvement

### Regular Updates
1. **Weekly**: Review and update skill files
2. **Monthly**: Test optimization strategies
3. **Per Project**: Apply learnings to new projects
4. **When Tools Update**: Update version references

### Knowledge Sharing
1. **Document Learnings**: Add to `CLAUDE.md` after each session
2. **Update Templates**: Improve project template with new patterns
3. **Share Strategies**: Apply successful patterns across projects
4. **Create Examples**: Add Deals-Coupons-AI specific examples

---

*Last Updated: 2026-03-17*
*This summary should be updated whenever new tools or optimization strategies are added to the project.*