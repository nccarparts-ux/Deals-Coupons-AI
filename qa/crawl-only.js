const { exec } = require('child_process');
const path = require('path');
const Crawler = require('./crawler');

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

async function main() {
  console.log('=== QA Crawl Only ===');
  let server;
  try {
    server = await startDevServer();
    await new Promise(resolve => setTimeout(resolve, 3000));

    const crawler = new Crawler('http://localhost:3000', path.join(__dirname, '..'));
    await crawler.crawl(100);

    console.log(`Crawled ${crawler.visited.size} pages, logged ${crawler.issues.length} issues`);
  } catch (error) {
    console.error('Crawl failed:', error);
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