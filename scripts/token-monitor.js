#!/usr/bin/env node

/**
 * Token Monitor for Claude Code with DeepSeek
 *
 * Estimates token usage and recommends optimization strategies
 * Rough estimates: 1 token ≈ 4 characters for English text
 *
 * Usage:
 *   node token-monitor.js "Task description" file1.js file2.html
 *   node token-monitor.js --task "Large rebranding" --files "*.html"
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class TokenMonitor {
  constructor() {
    this.tokenPerChar = 0.25; // 1 token ≈ 4 characters
    this.fileMultiplier = 1.2; // Extra tokens for file operations
    this.parallelThreshold = 3000; // Tokens threshold for parallel recommendation
    this.fileThreshold = 10; // File count threshold for parallel recommendation
  }

  estimateTokens(text) {
    if (!text) return 0;
    const charCount = text.length;
    const tokenEstimate = Math.ceil(charCount * this.tokenPerChar);
    return tokenEstimate;
  }

  countFiles(filePatterns) {
    let totalFiles = 0;
    const files = [];

    filePatterns.forEach(pattern => {
      try {
        // Use find command, exclude node_modules and test directories
        const findCmd = `find . -name "${pattern}" -type f ! -path "./node_modules/*" ! -path "./test-results*" ! -path "./.git/*" | wc -l`;
        const result = execSync(findCmd, { encoding: 'utf8' }).trim();
        const count = parseInt(result, 10);
        totalFiles += count;

        // Get actual file list (excluding node_modules)
        const fileListCmd = `find . -name "${pattern}" -type f ! -path "./node_modules/*" ! -path "./test-results*" ! -path "./.git/*"`;
        const fileList = execSync(fileListCmd, { encoding: 'utf8' }).trim().split('\n');
        files.push(...fileList.filter(f => f));
      } catch (error) {
        console.log(`Pattern "${pattern}" not found or error: ${error.message}`);
      }
    });

    return { totalFiles, files: files.slice(0, 50) }; // Limit to first 50 files for display
  }

  analyzeTask(taskDescription, filePatterns = []) {
    const taskTokens = this.estimateTokens(taskDescription);
    const fileInfo = this.countFiles(filePatterns);
    const fileTokens = Math.ceil(fileInfo.totalFiles * 100 * this.fileMultiplier); // Rough estimate

    const totalTokens = taskTokens + fileTokens;

    console.log('='.repeat(60));
    console.log('📊 TOKEN USAGE ANALYSIS');
    console.log('='.repeat(60));
    console.log(`\nTask Description: ${taskDescription.substring(0, 100)}${taskDescription.length > 100 ? '...' : ''}`);
    console.log(`\n📈 Token Estimates:`);
    console.log(`  - Task description: ${taskTokens} tokens`);
    console.log(`  - File operations (${fileInfo.totalFiles} files): ${fileTokens} tokens`);
    console.log(`  - TOTAL ESTIMATED: ${totalTokens} tokens`);

    if (fileInfo.files.length > 0) {
      console.log(`\n📁 Sample Files (${Math.min(fileInfo.files.length, 5)} of ${fileInfo.files.length}):`);
      fileInfo.files.slice(0, 5).forEach(file => console.log(`  - ${file}`));
      if (fileInfo.files.length > 5) {
        console.log(`  - ... and ${fileInfo.files.length - 5} more`);
      }
    }

    console.log(`\n🎯 OPTIMIZATION RECOMMENDATIONS:`);

    if (totalTokens > this.parallelThreshold || fileInfo.totalFiles > this.fileThreshold) {
      console.log(`  ✅ USE PARALLEL AGENTS`);
      const agentCount = Math.max(2, Math.ceil(fileInfo.totalFiles / 5));
      console.log(`     Split into ${agentCount} agents (${Math.ceil(fileInfo.totalFiles / agentCount)} files each)`);

      if (filePatterns.length > 0) {
        console.log(`\n  🔧 Suggested split:`);
        const patternsByType = this.groupFilesByType(filePatterns);
        patternsByType.forEach(({ type, count }) => {
          console.log(`     - ${type} files: ${count} → 1 agent`);
        });
      }
    } else {
      console.log(`  ✅ SINGLE AGENT SUFFICIENT`);
      console.log(`     Task size is within optimal range`);
    }

    // Environment recommendations
    console.log(`\n  ⚙️ Environment Settings:`);
    if (totalTokens > 5000) {
      console.log(`     Use .env.large-task profile (ANTHROPIC_MAX_TOKENS=8192)`);
    } else if (totalTokens > 2000) {
      console.log(`     Use default .env (ANTHROPIC_MAX_TOKENS=4096)`);
    } else {
      console.log(`     Use .env.quick-task profile (ANTHROPIC_MAX_TOKENS=2048)`);
    }

    // Communication tips
    console.log(`\n  💡 Communication Tips:`);
    const tips = [];
    if (taskDescription.length > 500) tips.push('Shorten task description');
    if (fileInfo.totalFiles > 20) tips.push('Reference files by pattern instead of listing all');
    if (tips.length > 0) {
      tips.forEach(tip => console.log(`     - ${tip}`));
    } else {
      console.log(`     - Current task description is appropriately concise`);
    }

    console.log('\n' + '='.repeat(60));
  }

  groupFilesByType(filePatterns) {
    const types = {};

    filePatterns.forEach(pattern => {
      const ext = pattern.includes('.') ? pattern.split('.').pop().replace('*', '').toLowerCase() : 'unknown';
      const typeMap = {
        'html': 'HTML',
        'js': 'JavaScript',
        'css': 'CSS',
        'json': 'JSON',
        'md': 'Markdown',
        'sql': 'SQL',
        'spec': 'Test',
        'test': 'Test'
      };

      const typeName = typeMap[ext] || ext.toUpperCase();
      types[typeName] = (types[typeName] || 0) + 1;
    });

    return Object.entries(types).map(([type, count]) => ({ type, count }));
  }

  printOptimizationStrategies() {
    console.log('\n📚 COMMON OPTIMIZATION STRATEGIES:');
    console.log('1. Parallel Agent Execution:');
    console.log('   - Launch multiple Task agents simultaneously');
    console.log('   - Split by file type (HTML, JS, tests, config)');
    console.log('   - Use different model sizes (haiku for simple tasks)');

    console.log('\n2. Concise Communication:');
    console.log('   - Use bullet points instead of paragraphs');
    console.log('   - Include file paths with line numbers (file.js:123)');
    console.log('   - Skip unnecessary explanations');

    console.log('\n3. Efficient File Operations:');
    console.log('   - Use Glob and Grep tools instead of Bash');
    console.log('   - Read only necessary portions of files');
    console.log('   - Edit files with precise old_string matches');

    console.log('\n4. Memory System Usage:');
    console.log('   - Store learnings in CLAUDE.md');
    console.log('   - Reference previous solutions');
    console.log('   - Use skill files as quick references');
  }
}

// Command line interface
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    console.log(`
Token Monitor for Claude Code with DeepSeek

Usage:
  node token-monitor.js "Task description" [file patterns...]
  node token-monitor.js --task "Task description" --files "*.html" "*.js"

Examples:
  node token-monitor.js "Update all HTML files with new branding" "*.html"
  node token-monitor.js "Fix JavaScript errors" "*.js" "*.html"
  node token-monitor.js --help

Options:
  --help, -h     Show this help message
  --task         Task description (use quotes for multi-word)
  --files        File patterns (space-separated, use quotes)
    `);
    return;
  }

  const monitor = new TokenMonitor();

  // Parse arguments
  let taskDescription = '';
  const filePatterns = [];

  if (args[0] === '--task') {
    // Parse with --task and --files flags
    for (let i = 1; i < args.length; i++) {
      if (args[i] === '--files') {
        i++;
        while (i < args.length && !args[i].startsWith('--')) {
          filePatterns.push(args[i]);
          i++;
        }
        i--; // Adjust for loop increment
      } else if (!args[i].startsWith('--')) {
        taskDescription = args[i];
      }
    }
  } else {
    // Simple format: first arg is task, rest are file patterns
    taskDescription = args[0];
    for (let i = 1; i < args.length; i++) {
      filePatterns.push(args[i]);
    }
  }

  if (!taskDescription) {
    console.log('Error: Task description is required');
    console.log('Use: node token-monitor.js "Task description" [file patterns...]');
    process.exit(1);
  }

  monitor.analyzeTask(taskDescription, filePatterns);

  // Show additional strategies if requested or if task is large
  if (args.includes('--strategies') || taskDescription.length > 200) {
    monitor.printOptimizationStrategies();
  }
}

if (require.main === module) {
  main();
}

module.exports = TokenMonitor;