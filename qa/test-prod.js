const Crawler = require('./crawler');
const path = require('path');

(async () => {
  try {
    const crawler = new Crawler('https://family-nest-auctions.vercel.app', path.join(__dirname, '..'));
    console.log('Testing crawler with production site...');
    // Crawl just 2 pages for quick test
    await crawler.crawl(2);
    console.log('Visited:', Array.from(crawler.visited));
    console.log('Issues found:', crawler.issues.length);
    crawler.issues.forEach(i => console.log(`${i.type}: ${i.message.substring(0, 100)}`));
  } catch (err) {
    console.error('Crawl failed:', err);
  }
})();