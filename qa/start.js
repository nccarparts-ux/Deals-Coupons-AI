const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const Crawler = require('./crawler');

const ISSUES_PATH = path.join(__dirname, '..', 'issues.jsonl');
const RESOLVED_PATH = path.join(__dirname, '..', 'issues_resolved.jsonl');

// Ensure logs exist
if (!fs.existsSync(ISSUES_PATH)) {
  fs.writeFileSync(ISSUES_PATH, '');
}
if (!fs.existsSync(RESOLVED_PATH)) {
  fs.writeFileSync(RESOLVED_PATH, '');
}

function startDevServer() {
  return new Promise((resolve, reject) => {
    console.log('Starting dev server...');
    const server = exec('npm run dev', { cwd: path.join(__dirname, '..') });
    server.stdout.on('data', data => {
      console.log(`server: ${data}`);
      if (data.includes('Serving')) {
        resolve(server);
      }
    });
    server.stderr.on('data', data => {
      console.error(`server err: ${data}`);
    });
    server.on('error', reject);
    setTimeout(() => resolve(server), 5000); // fallback
  });
}

async function runCrawler() {
  const crawler = new Crawler('http://localhost:3000', path.join(__dirname, '..'));
  const issues = await crawler.crawl(30);
  console.log(`Crawled ${crawler.visited.size} pages, found ${issues.length} issues`);
  return issues;
}

function readExistingIssues() {
  try {
    const content = fs.readFileSync(ISSUES_PATH, 'utf8');
    const lines = content.trim().split('\n').filter(line => line);
    return lines.map(line => JSON.parse(line));
  } catch (e) {
    return [];
  }
}

function groupIssues(issues) {
  const groups = {};
  issues.forEach(issue => {
    const key = `${issue.type}:${issue.url}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(issue);
  });
  return groups;
}

function diagnoseRootCause(issueGroup) {
  // Simple diagnosis based on type
  const first = issueGroup[0];
  if (first.type === 'console') {
    if (first.message.includes('FNA') || first.message.includes('BY')) {
      return 'branding_js_namespace';
    } else if (first.message.includes('undefined')) {
      return 'undefined_variable';
    } else if (first.message.includes('SyntaxError')) {
      return 'syntax_error';
    }
  } else if (first.type === 'navigation') {
    return 'page_load_failure';
  } else if (first.type === 'broken_image') {
    return 'missing_asset';
  } else if (first.type === 'javascript') {
    return 'runtime_error';
  }
  return 'unknown';
}

async function main() {
  console.log('=== Autonomous QA/Repair Agent ===');
  console.log('Starting dev server...');
  const server = await startDevServer();

  // Wait for server to be ready
  await new Promise(resolve => setTimeout(resolve, 3000));

  console.log('Running crawler...');
  const newIssues = await runCrawler();

  const existing = readExistingIssues();
  const allIssues = [...existing, ...newIssues];
  const uniqueIds = new Set();
  const deduped = allIssues.filter(issue => {
    const id = issue.id || `${issue.type}:${issue.url}:${issue.message}`;
    if (uniqueIds.has(id)) return false;
    uniqueIds.add(id);
    return true;
  });

  // Write back deduped
  fs.writeFileSync(ISSUES_PATH, deduped.map(issue => JSON.stringify(issue)).join('\n'));

  // Group issues
  const groups = groupIssues(deduped);
  console.log(`Found ${deduped.length} issues in ${Object.keys(groups).length} groups`);

  // For now, just log groups
  Object.entries(groups).forEach(([key, issues]) => {
    console.log(`\nGroup: ${key}`);
    issues.forEach(issue => console.log(`  - ${issue.message}`));
    const rootCause = diagnoseRootCause(issues);
    console.log(`  Root cause: ${rootCause}`);
  });

  console.log('\nQA initial scan complete. Issues logged to issues.jsonl');
  server.kill();
}

if (require.main === module) {
  main().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}