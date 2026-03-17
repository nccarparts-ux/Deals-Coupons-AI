const Crawler = require('./crawler');
const { exec } = require('child_process');
const path = require('path');

async function startServer() {
  return new Promise((resolve) => {
    const server = exec('npm run dev', { cwd: path.join(__dirname, '..') });
    server.stdout.on('data', data => {
      if (data.includes('Serving')) {
        resolve(server);
      }
    });
    setTimeout(() => resolve(server), 3000);
  });
}

(async () => {
  let server = null;
  try {
    console.log('Starting server...');
    server = await startServer();
    await new Promise(r => setTimeout(r, 2000));

    const crawler = new Crawler('http://localhost:3000', '.');
    console.log('Crawling up to 5 pages...');
    await crawler.crawl(5);

    console.log('Visited:', Array.from(crawler.visited));
    console.log('Issues:', crawler.issues.length);
    crawler.issues.forEach(i => console.log(`[${i.type}] ${i.message.substring(0, 80)}`));
  } catch (err) {
    console.error(err);
  } finally {
    if (server) {
      server.kill();
      console.log('Server killed');
    }
  }
})();