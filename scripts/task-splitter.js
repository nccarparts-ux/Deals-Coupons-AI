#!/usr/bin/env node

/**
 * Task Splitter for Claude Code
 *
 * Splits large tasks into manageable chunks for parallel agent execution
 * Groups files by type and generates agent prompts
 *
 * Usage:
 *   node task-splitter.js "Task description" file1.js file2.html file3.js
 *   node task-splitter.js --task "Large task" --glob "*.html" "*.js"
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class TaskSplitter {
  constructor(taskDescription, filePaths = []) {
    this.taskDescription = taskDescription;
    this.filePaths = filePaths;
    this.maxFilesPerAgent = 8; // Optimal files per agent
  }

  /**
   * Find files matching glob patterns
   */
  findFiles(patterns) {
    const files = new Set();

    patterns.forEach(pattern => {
      try {
        // Use find command for cross-platform compatibility
        // Exclude node_modules, test-results, and .git directories
        const command = pattern.includes('**')
          ? `find . -type f -path "${pattern.replace(/\*\*/g, '*')}" ! -path "./node_modules/*" ! -path "./test-results*" ! -path "./.git/*"`
          : `find . -name "${pattern}" -type f ! -path "./node_modules/*" ! -path "./test-results*" ! -path "./.git/*"`;

        const result = execSync(command, { encoding: 'utf8', stdio: 'pipe' }).trim();
        if (result) {
          result.split('\n').forEach(file => {
            if (file && file.trim()) {
              files.add(file.trim());
            }
          });
        }
      } catch (error) {
        // Pattern might not match any files
        console.log(`Pattern "${pattern}" matched 0 files`);
      }
    });

    return Array.from(files);
  }

  /**
   * Group files by type for optimal agent specialization
   */
  groupFilesByType(filePaths) {
    const groups = {
      html: { files: [], description: 'HTML files' },
      javascript: { files: [], description: 'JavaScript files' },
      css: { files: [], description: 'CSS files' },
      tests: { files: [], description: 'Test files' },
      config: { files: [], description: 'Configuration files' },
      database: { files: [], description: 'Database files' },
      docs: { files: [], description: 'Documentation files' },
      other: { files: [], description: 'Other files' }
    };

    filePaths.forEach(filePath => {
      const ext = path.extname(filePath).toLowerCase();
      const filename = path.basename(filePath).toLowerCase();

      if (ext === '.html' || ext === '.htm') {
        groups.html.files.push(filePath);
      } else if (ext === '.js' || ext === '.jsx' || ext === '.ts' || ext === '.tsx') {
        if (filename.includes('test') || filename.includes('spec') || filename.includes('.spec.') || filename.includes('.test.')) {
          groups.tests.files.push(filePath);
        } else {
          groups.javascript.files.push(filePath);
        }
      } else if (ext === '.css' || ext === '.scss' || ext === '.less') {
        groups.css.files.push(filePath);
      } else if (ext === '.json' || ext === '.toml' || ext === '.yaml' || ext === '.yml' || ext === '.config' || ext === '.env') {
        groups.config.files.push(filePath);
      } else if (ext === '.sql' || ext === '.db' || filename.includes('migration')) {
        groups.database.files.push(filePath);
      } else if (ext === '.md' || ext === '.txt' || ext === '.rst') {
        groups.docs.files.push(filePath);
      } else {
        groups.other.files.push(filePath);
      }
    });

    // Remove empty groups
    const result = {};
    Object.entries(groups).forEach(([key, value]) => {
      if (value.files.length > 0) {
        result[key] = value;
      }
    });

    return result;
  }

  /**
   * Split large groups into smaller chunks
   */
  splitLargeGroups(groups) {
    const chunks = [];

    Object.entries(groups).forEach(([type, group]) => {
      const files = group.files;
      const description = group.description;

      if (files.length <= this.maxFilesPerAgent) {
        // Group fits in one agent
        chunks.push({
          type,
          description: `${this.taskDescription} - ${description}`,
          files,
          agentCount: 1
        });
      } else {
        // Split group into multiple agents
        const numAgents = Math.ceil(files.length / this.maxFilesPerAgent);
        for (let i = 0; i < numAgents; i++) {
          const start = i * this.maxFilesPerAgent;
          const end = start + this.maxFilesPerAgent;
          const chunkFiles = files.slice(start, end);

          chunks.push({
            type: `${type}-${i + 1}`,
            description: `${this.taskDescription} - ${description} (part ${i + 1}/${numAgents})`,
            files: chunkFiles,
            agentCount: numAgents,
            part: i + 1,
            totalParts: numAgents
          });
        }
      }
    });

    return chunks;
  }

  /**
   * Generate Claude Code agent prompts
   */
  generatePrompts(chunks) {
    return chunks.map((chunk, index) => {
      const agentNumber = index + 1;
      const fileList = chunk.files.map(f => `  - ${f}`).join('\n');

      return {
        agentNumber,
        chunk,
        prompt: `${chunk.description}

Files to modify:
${fileList}

Instructions:
1. Read each file to understand current structure
2. Apply the necessary changes for: "${this.taskDescription}"
3. Test your changes if possible
4. Document any issues or questions

Total files: ${chunk.files.length}
File types: ${chunk.type.replace(/-\\d+$/, '')}
${chunk.part ? `Part ${chunk.part} of ${chunk.totalParts}` : ''}`
      };
    });
  }

  /**
   * Generate execution script for parallel agents
   */
  generateExecutionScript(prompts) {
    let script = `#!/bin/bash

# Parallel Agent Execution Script
# Generated by Task Splitter
# Task: "${this.taskDescription}"
# Total agents: ${prompts.length}
# Total files: ${this.filePaths.length}

echo "Starting parallel execution of ${prompts.length} agents..."
echo "Task: ${this.taskDescription}"
echo

`;

    prompts.forEach((prompt, index) => {
      const agentNum = index + 1;
      const promptFile = `agent-${agentNum}-prompt.txt`;

      script += `# Agent ${agentNum}: ${prompt.chunk.description}
echo "Starting Agent ${agentNum}..."
cat > ${promptFile} << 'AGENT_PROMPT'
${prompt.prompt}
AGENT_PROMPT

# In a real scenario, you would launch Claude Code with this prompt
# Example: claude --prompt-file ${promptFile} --model haiku &
echo "Agent ${agentNum} prompt saved to ${promptFile}"
echo

`;
    });

    script += `echo "All agent prompts generated."
echo "To execute in parallel, run each agent in a separate terminal."
echo "Or use: for file in agent-*-prompt.txt; do claude --prompt-file \\"\\$file\\" & done"
echo
echo "Monitor progress with: ps aux | grep claude"
echo "Check results in generated files"`;

    return script;
  }

  /**
   * Print analysis and recommendations
   */
  printAnalysis(chunks, prompts) {
    console.log('='.repeat(70));
    console.log('🤖 TASK SPLITTER ANALYSIS');
    console.log('='.repeat(70));
    console.log(`\nTask: ${this.taskDescription}`);
    console.log(`Total files: ${this.filePaths.length}`);
    console.log(`Recommended agents: ${chunks.length}`);

    console.log('\n📊 AGENT BREAKDOWN:');
    chunks.forEach((chunk, index) => {
      const prompt = prompts[index];
      console.log(`\nAgent ${index + 1}: ${chunk.description}`);
      console.log(`  Files: ${chunk.files.length} (${chunk.type})`);
      if (chunk.part) {
        console.log(`  Part: ${chunk.part}/${chunk.totalParts}`);
      }
      console.log(`  Sample: ${chunk.files.slice(0, 3).map(f => path.basename(f)).join(', ')}${chunk.files.length > 3 ? '...' : ''}`);
    });

    console.log('\n🎯 OPTIMIZATION RECOMMENDATIONS:');
    if (chunks.length === 1) {
      console.log('  - Single agent execution is optimal');
      console.log('  - Use default .env settings');
    } else if (chunks.length <= 3) {
      console.log('  - Small parallel execution (2-3 agents)');
      console.log('  - Use .env.large-task profile for complex changes');
      console.log('  - Launch agents simultaneously');
    } else {
      console.log('  - Large parallel execution (4+ agents)');
      console.log('  - Consider phased approach:');
      console.log('    Phase 1: HTML/CSS agents');
      console.log('    Phase 2: JavaScript agents');
      console.log('    Phase 3: Test/verification agents');
    }

    console.log('\n🚀 EXECUTION STRATEGY:');
    console.log('1. Review agent prompts above');
    console.log('2. Adjust file groupings if needed');
    console.log('3. Generate execution script: node task-splitter.js --generate-script');
    console.log('4. Launch agents in parallel terminals');
    console.log('5. Monitor progress and merge results');

    console.log('\n' + '='.repeat(70));
  }

  /**
   * Main analysis function
   */
  analyze() {
    console.log(`Analyzing task: ${this.taskDescription}`);
    console.log(`Files to process: ${this.filePaths.length}`);

    if (this.filePaths.length === 0) {
      console.log('No files specified. Use --glob patterns to find files.');
      return { chunks: [], prompts: [] };
    }

    const groups = this.groupFilesByType(this.filePaths);
    const chunks = this.splitLargeGroups(groups);
    const prompts = this.generatePrompts(chunks);

    this.printAnalysis(chunks, prompts);

    return { chunks, prompts };
  }
}

// Command line interface
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    console.log(`
Task Splitter for Claude Code - Parallel Agent Optimization

Usage:
  node task-splitter.js "Task description" [file patterns...]
  node task-splitter.js --task "Task description" --glob "*.html" "*.js"
  node task-splitter.js --generate-script --task "Task" --glob "*.html"

Examples:
  node task-splitter.js "Update branding" "*.html" "*.js"
  node task-splitter.js --task "Fix all JavaScript errors" --glob "*.js"
  node task-splitter.js --help

Options:
  --help, -h           Show this help message
  --task              Task description (required)
  --glob              File patterns (space-separated)
  --generate-script   Generate bash script for parallel execution
  --max-files         Max files per agent (default: 8)
    `);
    return;
  }

  // Parse arguments
  let taskDescription = '';
  const globPatterns = [];
  let generateScript = false;
  let maxFiles = 8;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--task' && i + 1 < args.length) {
      taskDescription = args[++i];
    } else if (args[i] === '--glob') {
      i++;
      while (i < args.length && !args[i].startsWith('--')) {
        globPatterns.push(args[i]);
        i++;
      }
      i--; // Adjust for loop increment
    } else if (args[i] === '--generate-script') {
      generateScript = true;
    } else if (args[i] === '--max-files' && i + 1 < args.length) {
      maxFiles = parseInt(args[++i], 10);
    } else if (!args[i].startsWith('--') && !taskDescription) {
      // First non-flag argument is task description
      taskDescription = args[i];
    } else if (!args[i].startsWith('--')) {
      // Subsequent non-flag arguments are glob patterns
      globPatterns.push(args[i]);
    }
  }

  if (!taskDescription) {
    console.log('Error: Task description is required');
    console.log('Use: node task-splitter.js "Task description" [file patterns...]');
    process.exit(1);
  }

  // Find files matching patterns
  const splitter = new TaskSplitter(taskDescription);
  splitter.maxFilesPerAgent = maxFiles;

  const filePaths = globPatterns.length > 0
    ? splitter.findFiles(globPatterns)
    : args.filter(arg => !arg.startsWith('--') && arg !== taskDescription);

  if (filePaths.length === 0 && globPatterns.length === 0) {
    console.log('Error: No files specified. Use --glob patterns or list files.');
    process.exit(1);
  }

  splitter.filePaths = filePaths;

  // Perform analysis
  const { chunks, prompts } = splitter.analyze();

  // Generate execution script if requested
  if (generateScript) {
    const script = splitter.generateExecutionScript(prompts);
    const scriptFile = 'parallel-execution.sh';
    fs.writeFileSync(scriptFile, script, 'utf8');
    console.log(`\n📜 Execution script saved to: ${scriptFile}`);
    console.log(`Make it executable: chmod +x ${scriptFile}`);
    console.log(`Run it: ./${scriptFile}`);
  }

  // Save prompts to files
  if (prompts.length > 0) {
    console.log(`\n💾 Saving agent prompts to files...`);
    prompts.forEach(prompt => {
      const filename = `agent-${prompt.agentNumber}-prompt.txt`;
      fs.writeFileSync(filename, prompt.prompt, 'utf8');
      console.log(`  ${filename} (${prompt.chunk.files.length} files)`);
    });
    console.log(`\n✅ All prompts saved. Launch agents with these prompts.`);
  }
}

if (require.main === module) {
  main();
}

module.exports = TaskSplitter;