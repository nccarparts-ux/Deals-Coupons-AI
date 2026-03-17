const { exec } = require('child_process');
const path = require('path');
const Crawler = require('./crawler');

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
  let server = null;
  try {
    server = await startDevServer();
    console.log('Server started, waiting 3 seconds...');
    await new Promise(r => setTimeout(r, 3000));

    const crawler = new Crawler('http://localhost:3000', path.join(__dirname, '..'));
    // Limit pages to 5 for quick test
    await crawler.crawl(5);

    console.log(`Visited: ${Array.from(crawler.visited).join('\n')}`);
    console.log(`Issues count: ${crawler.issues.length}`);
    crawler.issues.forEach(issue => console.log(`${issue.type}: ${issue.message}`));
  } catch (err) {
    console.error(err);
  } finally {
    if (server) {
      server.kill();
      console.log('Server killed');
    }
  }
}

main();