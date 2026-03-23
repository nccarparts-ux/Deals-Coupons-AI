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

## Claude Code Integration (ccd command)

This project includes batch files (`c.bat` and `ccd.bat`) to launch Claude Code with DeepSeek configuration:

```bash
# Windows Command Prompt or PowerShell (in project directory):
c          # Shortcut: launches Claude Code with DeepSeek config
ccd        # Same as above, shows configuration verification

# Git Bash or WSL:
./c.bat
./ccd.bat
```

The `ccd.bat` file:
1. Changes to the project directory
2. Loads environment variables from `.env`
3. Verifies DeepSeek configuration (Base URL and Model)
4. Launches Claude Code with proper authentication

**Requirements:**
- Claude Code installed globally (`npm install -g @anthropic-ai/claude-code`)
- Valid DeepSeek API key in `.env` file
- Windows environment (for batch files) or use WSL/Git Bash

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

## Social Expansion Setup

This section covers the Phase-9/12 social platform expansion — Facebook, Pinterest,
Twitter/X (expanded), TikTok (Pexels video), email digest (Buttondown), and a
GitHub Pages blog.

### New .env Variables

Add the following to your `.env` file:

```
# Facebook
FACEBOOK_PAGE_ID=your_page_id
FACEBOOK_ACCESS_TOKEN=your_token
FACEBOOK_TOKEN_ISSUED_AT=YYYY-MM-DD

# Pinterest
PINTEREST_ACCESS_TOKEN=your_token

# TikTok (Pexels for video backgrounds)
PEXELS_API_KEY=your_key

# Email Digest
BUTTONDOWN_API_KEY=your_key

# Blog
BLOG_BASE_URL=https://yourusername.github.io/deals
```

### How to Get Each API Token

**Twitter/X**
1. Go to [developers.twitter.com](https://developers.twitter.com) and sign in.
2. Create a new App (or use an existing one) under a Project.
3. Go to App Settings → Keys and Tokens.
4. Click "Generate" next to Access Token and Access Token Secret.

**Facebook**
1. Go to [developers.facebook.com](https://developers.facebook.com) and sign in.
2. Create an App (Business type) and add the "Pages" product.
3. Open Graph API Explorer → select your App and your Page.
4. Click "Generate Access Token" and exchange it for a long-lived Page Access Token
   (valid 60 days; re-generate before `FACEBOOK_TOKEN_ISSUED_AT` + 60 days).

**Pinterest**
1. Go to [developers.pinterest.com](https://developers.pinterest.com) → My Apps.
2. Connect your app and navigate to Access Tokens.
3. Click Generate Token with scopes: `boards:read`, `boards:write`, `pins:read`, `pins:write`.
4. Copy the token into `PINTEREST_ACCESS_TOKEN`.

**Pexels (TikTok video backgrounds)**
1. Go to [pexels.com/api](https://www.pexels.com/api/) and sign in.
2. Fill in the request form — approval is instant and free.
3. Copy your API key into `PEXELS_API_KEY` (200 requests/hour on the free plan).

**Buttondown (Email Digest)**
1. Create a free account at [buttondown.email](https://buttondown.email).
2. Go to Settings → API Keys.
3. Generate a new key and add it to `BUTTONDOWN_API_KEY`.
   (Free tier supports up to 100 subscribers.)

### GitHub Pages Blog Setup

1. Push your repository to GitHub (if not already done).
2. In GitHub: Settings → Pages → Source: branch `main`, folder `/deal_sniper_ai/growth_engine/blog`.
3. Set `BLOG_BASE_URL` in `.env` to your GitHub Pages URL
   (e.g. `https://yourusername.github.io/deals`).
4. After first publish, submit `{BLOG_BASE_URL}/sitemap.xml` in
   [Google Search Console](https://search.google.com/search-console) to accelerate indexing.

### How to Check Social Posting Status

- Open `http://127.0.0.1:8001/social` in your browser.
- The social dashboard shows:
  - Live post counts per platform
  - Next scheduled posts for each platform
  - Top deal in the current queue
  - TikTok video generation queue
  - Recent errors per platform
- The **Kill Switch** button on that page pauses all new platform tasks
  without stopping Telegram posting.

### Startup Commands

```bash
# Normal start (all platforms)
start_deal_sniper.bat

# Test mode (new platforms simulate only — Telegram still posts)
start_deal_sniper.bat --dry-run

# New platforms only (posting + growth Celery queues)
start_deal_sniper.bat --social-only

# Emergency stop for new platforms (Telegram unaffected)
start_deal_sniper.bat --kill-social
```

Or using Python directly:

```bash
python scripts/start_sniper.py all --dry-run
python scripts/start_sniper.py all --social-only
python scripts/start_sniper.py --kill-social
```

### Dry-Run Mode Details

When `--dry-run` is passed:
- Sets environment variable `DEAL_SNIPER_DRY_RUN=1`.
- Each new platform poster checks `deal_sniper_ai.posting_engine.dry_run.is_dry_run()`
  at the top of its `post()` method and returns
  `{'success': True, 'platform': '<name>', 'dry_run': True}` without hitting any API.
- Telegram posting is **not** affected and continues normally.
- The `run_with_dry_run_check()` wrapper in `scripts/start_sniper.py` can be used
  in tests or tasks when the poster file cannot be edited directly.