# Tool Skills & Cheat Sheets

This directory contains comprehensive guides and cheat sheets for the development tools used in the Deals-Coupons-AI project.

## 📚 Available Skill Files

### 1. [Supabase CLI](supabase-cli.md)
Complete reference for Supabase CLI commands, local development setup, database migrations, authentication management, and troubleshooting.

**Key Sections:**
- Installation & Setup (global vs local)
- Database Management (migrations, seeding, reset)
- Authentication & Edge Functions
- Storage & Bucket Management
- Project Configuration & Linking
- Integration with Deals-Coupons-AI

### 2. [Playwright Testing](playwright-testing.md)
Comprehensive guide to end-to-end testing with Playwright, including test writing patterns, locator strategies, CI/CD integration, and debugging.

**Key Sections:**
- Installation & Configuration
- Writing Tests (basic to advanced)
- Page Object Model
- Running Tests (local & CI)
- API Testing
- Debugging & Reporting
- Deals-Coupons-AI Test Examples

### 3. [Vercel Deployment](vercel-deployment.md)
Complete deployment guide for Vercel, covering project setup, environment configuration, domain management, and CI/CD integration.

**Key Sections:**
- CLI Installation & Authentication
- Project Deployment (preview & production)
- Environment Variables Management
- Domain & Alias Configuration
- Serverless Functions
- Monitoring & Logs
- Deals-Coupons-AI Integration

## 🎯 How to Use These Skill Files

### For New Developers
1. Start with the **Supabase CLI** guide to set up local development
2. Review **Playwright Testing** to understand the test suite
3. Check **Vercel Deployment** for production deployment steps

### For Daily Development
- Use as quick reference for command syntax
- Copy-paste common workflows
- Troubleshoot common issues using the troubleshooting sections

### For Project Maintenance
- Update skill files when tool versions change
- Add new workflows as the project evolves
- Share with team members for consistent practices

## 🔄 Keeping Skills Updated

When tools are updated:

1. **Update Version References**: Check `package.json` and update version numbers in skill files
2. **Test Commands**: Verify that commands still work with new versions
3. **Add New Features**: Document new capabilities or changed behavior
4. **Update Examples**: Ensure Deals-Coupons-AI examples remain relevant

## 📖 Related Documentation

- **Project README**: `../README.md`
- **Skills Summary**: `../SKILLS_SUMMARY.md`
- **Environment Configuration**: `../.env`
- **Package Configuration**: `../package.json`
- **Playwright Configuration**: `../playwright.config.js`
- **Supabase Configuration**: `../supabase/config.toml`

## 🚀 Quick Start Commands

```bash
# Supabase local development
npx supabase start
npx supabase status

# Playwright testing
npm test
npm run test:ui

# Vercel deployment
vercel login
npm run vercel:deploy
```

## 🤝 Contributing

When adding new tooling to the project:

1. Create a new skill file in this directory
2. Follow the existing format (installation, commands, examples, troubleshooting)
3. Include Deals-Coupons-AI-specific examples
4. Update the main `SKILLS_SUMMARY.md` file
5. Test all commands before documenting

---

*These skill files are living documents. Update them as you discover new workflows or solutions to common problems.*