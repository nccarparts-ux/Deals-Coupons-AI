const path = require('path');
const Crawler = require('./crawler');
const QAAgent = require('./agent');

async function main() {
  console.log('=== Autonomous QA/Repair Agent (Production) ===');

  try {
    // Use default crawler with production URL
    const crawler = new Crawler('https://family-nest-auctions.vercel.app', path.join(__dirname, '..'));
    console.log(`Starting crawl of production site: ${crawler.baseURL}`);

    await crawler.crawl(30);
    console.log(`Crawled ${crawler.visited.size} pages, logged ${crawler.issues.length} issues`);

    // Run QA agent to diagnose and fix
    const agent = new QAAgent();
    await agent.runIteration();

    console.log('Production QA cycle complete.');
  } catch (error) {
    console.error('Error during production QA cycle:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}