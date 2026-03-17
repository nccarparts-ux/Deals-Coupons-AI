const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

class Crawler {
  constructor(baseURL = 'https://deals-coupons-ai.vercel.app', outputDir = './qa') {
    this.baseURL = baseURL;
    this.visited = new Set();
    this.toVisit = [this.normalizeUrl(baseURL + '/')];
    this.issues = [];
    this.outputDir = outputDir;
    this.ensureOutputDir();
  }

  ensureOutputDir() {
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
    }
  }

  normalizeUrl(url) {
    // Remove hash and query parameters
    const u = new URL(url);
    u.hash = '';
    u.search = '';
    // Ensure trailing slash consistency? keep as is
    return u.toString();
  }

  async crawl(maxPages = 50) {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    while (this.toVisit.length > 0 && this.visited.size < maxPages) {
      const url = this.toVisit.shift();
      const normalized = this.normalizeUrl(url);
      if (this.visited.has(normalized)) continue;

      console.log(`Crawling: ${url}`);
      try {
        await page.goto(url, { waitUntil: 'networkidle' });
        this.visited.add(normalized);

        // Collect issues
        await this.collectIssues(page, url);

        // Extract links
        const links = await page.$$eval('a[href]', as => as.map(a => a.href));
        this.addLinks(links);

      } catch (error) {
        console.error(`Failed to crawl ${url}:`, error.message);
        this.logIssue('navigation', url, `Failed to load page: ${error.message}`);
      }
    }

    await browser.close();
    this.saveIssues();
    return this.issues;
  }

  addLinks(links) {
    const excluded = ['mailto:', 'tel:', 'cdn-cgi', 'cloudflare'];
    for (const link of links) {
      // Filter to same origin
      if (!link.startsWith(this.baseURL)) continue;
      // Exclude external patterns
      if (excluded.some(pattern => link.includes(pattern))) continue;
      // Normalize
      const normalized = this.normalizeUrl(link);
      if (this.visited.has(normalized) || this.toVisit.includes(normalized)) continue;
      this.toVisit.push(normalized);
    }
  }

  async collectIssues(page, url) {
    // Console errors
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Page errors
    const pageErrors = [];
    page.on('pageerror', error => {
      pageErrors.push(error.message);
    });

    // Wait a bit for errors to accumulate
    await page.waitForTimeout(1000);

    // Log errors
    consoleErrors.forEach(msg => this.logIssue('console', url, msg));
    pageErrors.forEach(msg => this.logIssue('javascript', url, msg));

    // Check for broken images
    const brokenImages = await page.$$eval('img', imgs =>
      imgs.filter(img => !img.complete || img.naturalWidth === 0).map(img => img.src)
    );
    brokenImages.forEach(src => this.logIssue('broken_image', url, `Broken image: ${src}`));

    // Check for empty links
    const emptyLinks = await page.$$eval('a[href=""]', as => as.length);
    if (emptyLinks > 0) {
      this.logIssue('accessibility', url, `${emptyLinks} empty link(s) found`);
    }

    // Check for missing alt attributes
    const missingAlt = await page.$$eval('img:not([alt])', imgs => imgs.length);
    if (missingAlt > 0) {
      this.logIssue('accessibility', url, `${missingAlt} image(s) missing alt attribute`);
    }
  }

  logIssue(type, url, message) {
    // Check if similar issue already logged
    const existing = this.loadExistingIssues();
    const duplicate = existing.some(issue =>
      issue.type === type && issue.url === url && issue.message === message
    );
    if (duplicate) return;

    const issue = {
      id: `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type,
      url,
      message,
      timestamp: new Date().toISOString()
    };
    this.issues.push(issue);
    // Append to issues.jsonl
    const logPath = path.join(this.outputDir, 'issues.jsonl');
    fs.appendFileSync(logPath, JSON.stringify(issue) + '\n');
  }

  loadExistingIssues() {
    const logPath = path.join(this.outputDir, 'issues.jsonl');
    try {
      const content = fs.readFileSync(logPath, 'utf8');
      const lines = content.trim().split('\n').filter(line => line);
      return lines.map(line => JSON.parse(line));
    } catch (e) {
      return [];
    }
  }

  saveIssues() {
    const issuesPath = path.join(this.outputDir, 'crawl_issues.json');
    fs.writeFileSync(issuesPath, JSON.stringify(this.issues, null, 2));
  }
}

module.exports = Crawler;