const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const { Task } = require('@anthropic-ai/claude-code');

const ISSUES_PATH = path.join(__dirname, '..', 'issues.jsonl');
const RESOLVED_PATH = path.join(__dirname, '..', 'issues_resolved.jsonl');

class Coordinator {
  constructor() {
    this.iteration = 0;
    this.running = false;
    this.agentTasks = new Map(); // taskId -> agent type
  }

  async start() {
    console.log('=== Autonomous QA Coordinator Starting ===');
    this.running = true;
    await this.runLoop();
  }

  stop() {
    console.log('Stopping coordinator...');
    this.running = false;
    // Stop all running agents
    for (const [taskId] of this.agentTasks) {
      // Could send stop signal
    }
  }

  async runLoop() {
    while (this.running) {
      this.iteration++;
      console.log(`\n=== Iteration ${this.iteration} ===`);
      try {
        await this.runIteration();
      } catch (error) {
        console.error(`Iteration ${this.iteration} failed:`, error);
      }
      // Wait before next iteration
      await this.sleep(60000); // 1 minute
    }
  }

  async runIteration() {
    // Phase 1: Crawl (QA role)
    console.log('Phase 1: Crawling for issues...');
    await this.runCrawler();

    // Phase 2: Diagnose and fix (FIX role)
    console.log('Phase 2: Diagnosing and fixing...');
    await this.runFixAgent();

    // Phase 3: Test (TEST role)
    console.log('Phase 3: Running tests...');
    await this.runTestAgent();

    // Phase 4: DB validation (DB role)
    console.log('Phase 4: Validating database...');
    await this.runDBAgent();

    // Phase 5: Deploy (DEPLOY role)
    console.log('Phase 5: Deploying fixes...');
    await this.runDeployAgent();

    console.log(`Iteration ${this.iteration} complete.`);
  }

  async runCrawler() {
    // Use Task tool to run crawler agent in background
    const taskId = `crawler_${Date.now()}`;
    console.log(`Launching crawler agent (${taskId})...`);
    // For now, run crawler directly
    const Crawler = require('./crawler');
    const crawler = new Crawler('https://family-nest-auctions.vercel.app', path.join(__dirname, '..'));
    await crawler.crawl(30);
    console.log(`Crawler visited ${crawler.visited.size} pages, found ${crawler.issues.length} issues`);
  }

  async runFixAgent() {
    // Use Task tool to run fix agent
    console.log('Running fix agent...');
    const QAAgent = require('./agent');
    const agent = new QAAgent();
    await agent.runIteration();
  }

  async runTestAgent() {
    // Run Playwright tests and log failures as issues
    console.log('Running test agent...');
    try {
      // Check if local server is available
      const serverAvailable = await this.checkLocalServer();
      if (!serverAvailable) {
        console.log('Local server not available, skipping tests.');
        return;
      }

      // Run tests and capture output
      const output = await this.execPromise('npm test 2>&1');
      // Parse test results for failures
      await this.parseTestResults(output);
    } catch (error) {
      console.error('Test agent error:', error.message);
      // Log test failure as issue
      this.logIssue('test_failure', 'https://family-nest-auctions.vercel.app', `Test suite failed: ${error.message}`);
    }
  }

  async runDBAgent() {
    // Validate Supabase schema matches frontend
    console.log('Running DB agent...');
    // Check for demo data in production UI
    // Validate tables exist
    // Check RLS policies
    // This could be implemented later
  }

  async runDeployAgent() {
    // Commit changes and deploy to production
    console.log('Running deploy agent...');
    // Check for uncommitted changes
    const status = await this.execPromise('git status --porcelain');
    if (status.trim()) {
      console.log('Found uncommitted changes, committing...');
      await this.execPromise('git add .');
      await this.execPromise('git commit -m "Autonomous QA fixes: iteration ' + this.iteration + '"');
      // Push to remote
      await this.execPromise('git push');
      // Deploy to Vercel
      await this.execPromise('npx vercel --prod');
    } else {
      console.log('No changes to deploy.');
    }
  }

  async checkLocalServer() {
    try {
      const http = require('http');
      return new Promise((resolve) => {
        const req = http.get('http://localhost:3000', (res) => {
          resolve(res.statusCode === 200);
        });
        req.on('error', () => resolve(false));
        req.setTimeout(2000, () => {
          req.destroy();
          resolve(false);
        });
      });
    } catch {
      return false;
    }
  }

  async parseTestResults(output) {
    // Simple parsing for Playwright test output
    if (output.includes('failed')) {
      const lines = output.split('\n');
      const failLine = lines.find(line => line.includes('failed') && line.includes('passed'));
      if (failLine) {
        this.logIssue('test_failure', 'https://family-nest-auctions.vercel.app', `Test failures: ${failLine.trim()}`);
      }
    }
  }

  logIssue(type, url, message) {
    const issue = {
      id: `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type,
      url,
      message,
      timestamp: new Date().toISOString()
    };
    fs.appendFileSync(ISSUES_PATH, JSON.stringify(issue) + '\n');
    console.log(`Logged issue: ${type} - ${message.substring(0, 80)}...`);
  }

  execPromise(command) {
    return new Promise((resolve, reject) => {
      exec(command, { cwd: path.join(__dirname, '..') }, (error, stdout, stderr) => {
        if (error) {
          reject(new Error(`Command failed: ${error.message}\n${stderr}`));
        } else {
          resolve(stdout + stderr);
        }
      });
    });
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Run if called directly
if (require.main === module) {
  const coordinator = new Coordinator();
  coordinator.start().catch(console.error);

  // Handle graceful shutdown
  process.on('SIGINT', () => {
    console.log('\nReceived SIGINT, shutting down...');
    coordinator.stop();
    process.exit(0);
  });
}

module.exports = Coordinator;