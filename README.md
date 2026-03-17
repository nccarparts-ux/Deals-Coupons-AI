# Deals-Coupons-AI - Development Environment Template

This template provides a complete development environment setup for Deals-Coupons-AI with the following tools:

- **Claude Code** with DeepSeek model integration
- **Playwright** for end-to-end testing
- **Supabase CLI** for local development
- **Vercel CLI** for deployment
- **Autonomous QA System** for automated issue detection and fixing
- **Skills Directory** with comprehensive cheat sheets
- **Memory Files** for project knowledge retention
- **Parallel Agent Optimization** for efficient large-scale changes

## Quick Setup

1. **Copy template files** to your project directory
2. **Run setup script** to configure placeholders
3. **Install dependencies** with npm
4. **Configure environment variables**
5. **Link your Supabase and Vercel projects**

## Detailed Setup Instructions

### 1. Copy Template Files
```bash
# Copy the entire project-template directory to your new project
cp -r path/to/project-template/* your-new-project/
cd your-new-project
```

### 2. Run Setup Script
```bash
# Run the interactive setup script
node setup.js
```
Or manually replace placeholders in these files:
- `package.json` - Replace `Deals-Coupons-AI`
- `.claude/settings.local.json` - Replace `{{PRODUCTION_DOMAIN}}` and `{{PRODUCTION_URL}}`
- `CLAUDE.md` - Update project-specific conventions
- `.env.template` - Fill in your API keys
- Skills files - Replace `Deals-Coupons-AI`
- Test files - Replace `Deals-Coupons-AI`
- QA files - Replace `{{PRODUCTION_URL}}`, `{{OLD_NAMESPACE}}`, `{{NEW_NAMESPACE}}`
- Supabase config - Replace `Deals-Coupons-AI`

### 3. Install Dependencies
```bash
npm install
npx playwright install
```

### 4. Configure Environment Variables
```bash
cp .env.template .env
# Edit .env with your actual API keys
```

### 5. Initialize Supabase
```bash
npx supabase init
# Link to your Supabase project (optional)
npx supabase link --project-ref your-project-ref
```

### 6. Set Up Vercel
```bash
vercel login
vercel link
```

### 7. Run Tests
```bash
npm run dev &  # Start dev server in background
npm test       # Run Playwright tests
```

## Development Workflow

### Daily Development
```bash
npm run dev          # Start local server
npm test             # Run tests
npm run test:ui      # Run tests with UI
npm run supabase:start  # Start local Supabase
```

### Autonomous QA System
The QA system automatically crawls your site, detects issues, and attempts to fix them:
```bash
npm run dev &
node qa/run.js
```

### Parallel Agent Pattern
For large-scale changes, use multiple Claude Code agents in parallel:
- Agent 1: Update HTML files
- Agent 2: Update JavaScript files
- Agent 3: Update test files
- Agent 4: Update configuration files
- Agent 5: Update SQL files and documentation

## Skill Files

The `skills/` directory contains comprehensive guides:
- `supabase-cli.md` - Supabase commands and workflows
- `playwright-testing.md` - Playwright testing guide
- `vercel-deployment.md` - Vercel deployment guide

## Memory System

- `CLAUDE.md` - Project memory bank with conventions and lessons learned
- `.ai_memory.json` - Tracks modified files and conversations
- `.agent_memory.json` - Test history and failure patterns

## Configuration Files

- `.claude/settings.local.json` - Claude Code permissions
- `playwright.config.js` - Playwright test configuration
- `supabase/config.toml` - Supabase local development config
- `package.json` - Scripts and dependencies

## Troubleshooting

### Common Issues
- **Supabase CLI not working**: Use `npx supabase` instead of global installation
- **Playwright browsers not installed**: Run `npx playwright install`
- **Vercel authentication**: Run `vercel login`
- **DeepSeek API errors**: Check `.env` configuration

### Getting Help
Refer to the skill files for detailed troubleshooting guides.

## Extending the Setup

### Adding New Tools
1. Add dependency to `package.json`
2. Create skill file in `skills/` directory
3. Update `CLAUDE.md` with new conventions
4. Add scripts to `package.json`

### Adding New Test Types
1. Add new test file in `tests/` directory
2. Update `playwright.config.js` if needed
3. Extend QA system in `qa/` directory

### Customizing Autonomous QA
1. Modify `qa/agent.js` to add new root cause detection
2. Update `qa/crawler.js` to detect new issue types
3. Add fix methods for new issue types

## Best Practices

- **Low Token Usage**: Write concise code and comments
- **Parallel Agents**: Use multiple agents for large-scale changes
- **Test First**: Write tests before implementing features
- **Memory Updates**: Add lessons learned to `CLAUDE.md`
- **Skill Maintenance**: Keep skill files updated with latest commands

## Project Structure
```
Deals-Coupons-AI/
├── .claude/                  # Claude Code settings
├── skills/                   # Tool skill files
├── tests/                    # Playwright tests
├── qa/                       # Autonomous QA system
├── supabase/                 # Supabase configuration
├── .env.template             # Environment template
├── CLAUDE.md                 # Project memory bank
├── package.json              # Dependencies and scripts
├── playwright.config.js      # Playwright config
└── README.md                 # This file
```

## Next Steps

1. Customize the template for your specific project
2. Add your application code (HTML, CSS, JavaScript)
3. Set up database schema with Supabase migrations
4. Configure CI/CD pipeline with GitHub Actions
5. Deploy to Vercel production

## Support

For issues with this template, refer to the original project at [GitHub Repository](https://github.com/your-repo).