const { exec } = require('child_process');
const http = require('http');
const path = require('path');
const Crawler = require('./crawler');
const QAAgent = require('./agent');

async function waitForServer(url, maxRetries = 10, interval = 1000) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(url, (res) => {
          res.on('data', () => {});
          res.on('end', resolve);
        });
        req.on('error', reject);
        req.setTimeout(2000, () => {
          req.destroy();
          reject(new Error('Timeout'));
        });
      });
      console.log(`Server ready at ${url}`);
      return true;
    } catch (err) {
      if (i < maxRetries - 1) {
        await new Promise(r => setTimeout(r, interval));
      } else {
        console.error(`Server not ready after ${maxRetries} retries`);
        return false;
      }
    }
  }
}

async function startDevServer() {
  return new Promise((resolve, reject) => {
    console.log('Starting dev server...');
    const server = exec('npm run dev', { cwd: path.join(__dirname, '..') });
    server.stdout.on('data', data => {
      if (data.includes('Serving')) {
        resolve(server);
      }
    });
    server.stderr.on('data', data => {
      console.error(`server err: ${data}`);
    });
    server.on('error', reject);
    setTimeout(() => resolve(server), 5000);
  });
}

async function main() {
  console.log('=== Autonomous QA/Repair Agent ===');
  let server = null;
  try {
    server = await startDevServer();
    const serverReady = await waitForServer('http://localhost:3000', 15, 1000);
    if (!serverReady) throw new Error('Server failed to start');

    // Crawl to gather issues
    const crawler = new Crawler('http://localhost:3000', path.join(__dirname, '..'));
    await crawler.crawl(5);
    console.log(`Crawled ${crawler.visited.size} pages, logged ${crawler.issues.length} issues`);

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