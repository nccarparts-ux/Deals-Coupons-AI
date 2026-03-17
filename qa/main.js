const { exec } = require('child_process');
const path = require('path');
const Crawler = require('./crawler');
const QAAgent = require('./agent');

async function startDevServer() {
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
  const issues = await crawler.crawl(50);
  console.log(`Crawled ${crawler.visited.size} pages, found ${issues.length} issues`);
  return issues;
}

async function main() {
  console.log('=== Autonomous QA/Repair Agent ===');
  let server;
  try {
    server = await startDevServer();
    await new Promise(resolve => setTimeout(resolve, 3000));

    // Run crawler
    await runCrawler();

    // Run QA agent
    const agent = new QAAgent();
    await agent.runIteration();

    console.log('QA cycle complete.');
  } catch (error) {
    console.error('Error during QA cycle:', error);
  } finally {
    if (server) {
      server.kill();
      console.log('Dev server stopped.');
    }
  }
}

if (require.main === module) {
  main();
}