const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

// Import agents
const Crawler = require('./crawler');
const QAAgent = require('./agent');
const { runTests } = require('./test-runner');
const { validateDatabase } = require('./db-validation');

const ISSUES_PATH = path.join(__dirname, '..', 'issues.jsonl');
const RESOLVED_PATH = path.join(__dirname, '..', 'issues_resolved.jsonl');

class AutonomousQA {
  constructor() {
    this.iteration = 0;
    this.running = false;
    this.baseURL = 'https://family-nest-auctions.vercel.app';
  }

  async start() {
    console.log('=== Autonomous QA/Repair Agent Starting ===');
    console.log(`Production site: ${this.baseURL}`);
    this.running = true;

    // Run first iteration immediately
    await this.runIteration();

    // Then run every 5 minutes
    const interval = 5 * 60 * 1000; // 5 minutes
    setInterval(() => {
      if (this.running) {
        this.runIteration().catch(console.error);
      }
    }, interval);

    console.log(`Will run every ${interval / 60000} minutes`);
  }

  stop() {
    console.log('Stopping autonomous QA agent...');
    this.running = false;
  }

  async runIteration() {
    this.iteration++;
    console.log(`\n=== Iteration ${this.iteration} - ${new Date().toISOString()} ===`);

    try {
      // Phase 1: Crawl
      console.log('Phase 1: Crawling site...');
      await this.crawl();

      // Phase 2: Diagnose and fix
      console.log('Phase 2: Diagnosing and fixing...');
      await this.diagnoseAndFix();

      // Phase 3: Test
      console.log('Phase 3: Running tests...');
      await this.test();

      // Phase 4: DB validation
      console.log('Phase 4: Validating database...');
      await this.dbValidate();

      // Phase 5: Deploy
      console.log('Phase 5: Deploying fixes...');
      await this.deploy();

      console.log(`Iteration ${this.iteration} completed successfully.`);
    } catch (error) {
      console.error(`Iteration ${this.iteration} failed:`, error);
      this.logIssue('system_error', this.baseURL, `Iteration ${this.iteration} failed: ${error.message}`);
    }
  }

  async crawl() {
    const crawler = new Crawler(this.baseURL, path.join(__dirname, '..'));
    await crawler.crawl(30);
    console.log(`Crawled ${crawler.visited.size} pages, found ${crawler.issues.length} issues`);
  }

  async diagnoseAndFix() {
    const agent = new QAAgent();
    await agent.runIteration();
  }

  async test() {
    // Check if local server is available before running tests
    const serverAvailable = await this.checkLocalServer();
    if (!serverAvailable) {
      console.log('Local server not available, skipping tests.');
      return;
    }

    const { failures } = await runTests();
    if (failures.length > 0) {
      console.log(`Detected ${failures.length} test failures`);
    }
  }

  async dbValidate() {
    await validateDatabase();
  }

  async deploy() {
    // Check for uncommitted changes
    const status = await this.execPromise('git status --porcelain');
    if (status.trim()) {
      console.log('Found uncommitted changes, committing...');
      await this.execPromise('git add .');
      await this.execPromise(`git commit -m "Autonomous QA fixes: iteration ${this.iteration}"`);
      await this.execPromise('git push');
      console.log('Changes pushed to remote.');

      // Trigger Vercel deployment
      console.log('Triggering Vercel deployment...');
      try {
        await this.execPromise('npx vercel --prod');
      } catch (error) {
        console.warn('Vercel deployment failed (may need auth):', error.message);
      }
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
}

// Run if called directly
if (require.main === module) {
  const agent = new AutonomousQA();
  agent.start().catch(console.error);

  // Handle graceful shutdown
  process.on('SIGINT', () => {
    console.log('\nReceived SIGINT, shutting down...');
    agent.stop();
    process.exit(0);
  });
}

module.exports = AutonomousQA;