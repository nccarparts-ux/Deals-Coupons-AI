# Token Optimization for Claude Code with DeepSeek

Comprehensive guide to optimizing token usage when working with Claude Code and DeepSeek API, preventing "API error 400 (request too large)" and maximizing productivity with parallel agents.

## 🎯 Why Token Optimization Matters

**DeepSeek API Limits:**
- Request size limits (varies by plan)
- Context window constraints
- Rate limiting on large requests
- Cost optimization for API usage

### API Plan Considerations
- **Free Tier**: Limited tokens per request (approx 4K-8K)
- **Paid Tiers**: Higher limits available (check DeepSeek platform for current limits)
- **Enterprise Plans**: Custom limits for large-scale usage
- **Token Budgeting**: Monitor usage and upgrade plan if consistently hitting limits

**Common Symptoms of Token Issues:**
- `API error 400: request too large`
- Slow response times
- Incomplete agent responses
- Timeout errors
- Increased API costs

## ⚙️ Environment Configuration

### Core Environment Variables (`.env`)

```bash
# DeepSeek Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key_here
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_AUTH_TOKEN=your_deepseek_api_key_here
ANTHROPIC_MODEL=deepseek-chat
ANTHROPIC_SMALL_FAST_MODEL=deepseek-chat

# Token Optimization Settings
API_TIMEOUT_MS=600000  # 10 minute timeout for large tasks
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1  # Reduce background traffic
ANTHROPIC_MAX_TOKENS=4096  # Limit maximum tokens per response
```

### Environment Variable Presets

Create different `.env` profiles for different task types:

**`.env.large-task` (for major refactoring/rebranding):**
```bash
ANTHROPIC_MAX_TOKENS=8192
API_TIMEOUT_MS=1200000  # 20 minutes
```

**`.env.quick-task` (for small fixes):**
```bash
ANTHROPIC_MAX_TOKENS=2048
API_TIMEOUT_MS=300000  # 5 minutes
```

**`.env.qa-testing` (for QA automation):**
```bash
ANTHROPIC_MAX_TOKENS=3072
API_TIMEOUT_MS=900000  # 15 minutes
```

## 🤖 Parallel Agent Execution Patterns

### Pattern 1: Large-Scale File Updates (Rebranding)

When updating many files simultaneously (e.g., rebranding FNA → BY):

```javascript
// Example: Launch 4 agents to update different file types in parallel
const agents = [
  { type: 'general-purpose', task: 'Update all HTML files with new branding' },
  { type: 'general-purpose', task: 'Update JavaScript files with namespace changes' },
  { type: 'general-purpose', task: 'Update test files with new selectors' },
  { type: 'general-purpose', task: 'Update configuration and documentation' }
];

// Each agent runs independently, reducing overall token usage
```

### Pattern 2: Multi-Phase Development Tasks

Break complex tasks into sequential phases with parallel execution within each phase:

**Phase 1: Research & Analysis**
- Agent 1: Explore codebase structure
- Agent 2: Analyze existing patterns

**Phase 2: Implementation**
- Agent 1: Update core functionality
- Agent 2: Update tests
- Agent 3: Update documentation

**Phase 3: Verification**
- Agent 1: Run test suite
- Agent 2: Deploy to staging
- Agent 3: Verify production

### Pattern 3: Autonomous QA System

The built-in QA system uses parallel execution:

1. **Crawler Agent**: Scans production site for issues
2. **Analysis Agent**: Analyzes collected data
3. **Fix Agent**: Applies fixes to identified issues
4. **Test Agent**: Verifies fixes work

## 📊 Token Usage Monitoring Scripts

### `scripts/token-monitor.js`

Create a script to estimate token usage:

```javascript
#!/usr/bin/env node

/**
 * Simple token estimator for Claude Code tasks
 * Rough estimates: 1 token ≈ 4 characters for English text
 */

function estimateTokens(text) {
  // Rough estimation
  const charCount = text.length;
  const tokenEstimate = Math.ceil(charCount / 4);

  // File count multiplier
  const fileMultiplier = 1.2; // Extra tokens for file operations

  return Math.ceil(tokenEstimate * fileMultiplier);
}

function recommendStrategy(taskDescription, filesToModify) {
  const taskTokens = estimateTokens(taskDescription);
  const fileCount = filesToModify.length;

  console.log(`Task Analysis:`);
  console.log(`- Task description: ${taskTokens} estimated tokens`);
  console.log(`- Files to modify: ${fileCount}`);

  if (taskTokens > 3000 || fileCount > 10) {
    console.log(`📊 RECOMMENDATION: Use parallel agents`);
    console.log(`   Split into ${Math.ceil(fileCount / 3)} agents`);
  } else {
    console.log(`📊 RECOMMENDATION: Single agent sufficient`);
  }
}
```

### `scripts/task-splitter.js`

Script to help split large tasks:

```javascript
#!/usr/bin/env node

/**
 * Helps split large tasks into manageable chunks
 */

const fs = require('fs');
const path = require('path');

class TaskSplitter {
  constructor(taskDescription, filePaths) {
    this.taskDescription = taskDescription;
    this.filePaths = filePaths;
  }

  splitByFileType() {
    const groups = {
      html: [],
      js: [],
      tests: [],
      config: [],
      docs: []
    };

    this.filePaths.forEach(filePath => {
      const ext = path.extname(filePath).toLowerCase();
      if (ext === '.html') groups.html.push(filePath);
      else if (ext === '.js') groups.js.push(filePath);
      else if (ext.includes('spec') || ext.includes('test')) groups.tests.push(filePath);
      else if (ext === '.json' || ext === '.toml' || ext === '.config') groups.config.push(filePath);
      else if (ext === '.md') groups.docs.push(filePath);
    });

    return Object.entries(groups)
      .filter(([_, files]) => files.length > 0)
      .map(([type, files]) => ({
        type,
        files,
        description: `${this.taskDescription} - ${type.toUpperCase()} files`
      }));
  }

  generateAgentPrompts() {
    const chunks = this.splitByFileType();

    return chunks.map((chunk, index) => ({
      agentNumber: index + 1,
      prompt: `Update the following ${chunk.files.length} ${chunk.type} files:\n` +
              chunk.files.map(f => `- ${f}`).join('\n') +
              `\n\nTask: ${chunk.description}`,
      estimatedFiles: chunk.files.length
    }));
  }
}
```

## 🛠️ Practical Optimization Techniques

### 1. Concise Communication
- Use bullet points instead of paragraphs
- Include file paths with line numbers (`file.js:123`)
- Skip unnecessary explanations
- Use code snippets only when essential

### 2. Efficient File Operations
- Use `Glob` and `Grep` tools instead of `Bash` commands
- Read only necessary portions of files with `offset` and `limit`
- Edit files with precise `old_string` to avoid unnecessary reads

### 3. Memory System Usage
- Store learnings in `CLAUDE.md` and `.ai_memory.json`
- Reference previous solutions instead of re-explaining
- Use skill files as quick references

### 4. Agent Selection Strategy
- Use `haiku` model for quick, straightforward tasks
- Use `sonnet` for moderate complexity
- Use `opus` only for complex architectural decisions
- Set appropriate `max_turns` for agents

## 🔧 Claude Code Settings Optimization

### `.claude/settings.local.json` Best Practices

```json
{
  "permissions": {
    "allow": [
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git push:*)",
      "WebFetch(domain:deals-coupons-ai.vercel.app)",
      "Bash(curl:*)",
      "Bash(git log --oneline -5)",
      "Bash(git pull:*)",
      "Bash(git merge:*)",
      "Bash(node:*)",
      "Bash(npm:*)",
      "Bash(supabase:*)",
      "Bash(vercel:*)",
      "Bash(npx playwright:*)"
    ]
  }
}
```

**Permission Optimization Tips:**
- Only include necessary permissions
- Group related permissions
- Use wildcards (`*`) judiciously
- Remove unused permissions regularly

## 🚀 Quick Reference Commands

### Token Estimation
```bash
# Estimate tokens in a file
node scripts/token-monitor.js "Task description" file1.js file2.html

# Split large task
node scripts/task-splitter.js "Large rebranding task" $(find . -name "*.html" -o -name "*.js")
```

### Environment Management
```bash
# Switch to large task profile
cp .env.large-task .env

# Switch to quick task profile
cp .env.quick-task .env

# Check current settings
grep "ANTHROPIC_MAX_TOKENS\|API_TIMEOUT_MS" .env
```

### Agent Launch Templates
```bash
# Single agent for small task
# Use: When < 5 files, simple changes

# Parallel agents for medium task (3-4 agents)
# Use: When 5-15 files, moderate complexity

# Phased parallel execution for large task
# Use: When > 15 files, complex refactoring
```

## 🧪 Testing Your Optimization

### Verification Script
Create `scripts/verify-optimization.js`:

```javascript
// Test that token optimization strategies work
// Run after major changes to ensure no API errors

const { execSync } = require('child_process');

function testSmallTask() {
  console.log('Testing small task optimization...');
  // Run a small Playwright test
  execSync('npm test -- --grep "homepage"', { stdio: 'inherit' });
}

function testParallelExecution() {
  console.log('Testing parallel execution pattern...');
  // Simulate parallel file updates
  // This would be implemented based on your specific patterns
}
```

## 📈 Monitoring & Adjustment

### Regular Checks
1. **Weekly**: Review `.claude/settings.local.json` permissions
2. **After Large Tasks**: Update `CLAUDE.md` with learnings
3. **When Errors Occur**: Add troubleshooting steps to this guide
4. **New Project Setup**: Apply these patterns from the beginning

### Signs You Need More Optimization
- Frequent "request too large" errors
- Tasks taking longer than expected
- High API costs
- Incomplete agent executions

## 🆘 Troubleshooting

### Error: "API error 400: request too large"
1. **Immediate fix**: Split task using `task-splitter.js`
2. **Check**: Current `ANTHROPIC_MAX_TOKENS` setting
3. **Reduce**: Task scope or file count
4. **Enable**: `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`

### Error: Agent timeout
1. **Increase**: `API_TIMEOUT_MS` in `.env`
2. **Simplify**: Task complexity
3. **Check**: Network connectivity

### Error: Incomplete responses
1. **Reduce**: `ANTHROPIC_MAX_TOKENS` to force concise responses
2. **Break**: Task into smaller subtasks
3. **Use**: More specific, focused prompts

## 📚 Related Resources

- **CLAUDE.md**: Project memory bank with optimization learnings
- **.ai_memory.json**: Agent memory for repeated patterns
- **Skills Directory**: Other tool guides
- **DeepSeek API Documentation**: Current limits and best practices

---

*Last Updated: 2026-03-17*
*Apply these patterns consistently across all projects for maximum efficiency.*