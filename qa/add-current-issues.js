const fs = require('fs');
const path = require('path');

const ISSUES_PATH = path.join(__dirname, '..', 'issues.jsonl');

function logIssue(type, url, message, metadata = {}) {
  const issue = {
    id: `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    type,
    url,
    message,
    timestamp: new Date().toISOString(),
    metadata
  };
  fs.appendFileSync(ISSUES_PATH, JSON.stringify(issue) + '\n');
  console.log(`Logged issue: ${type} - ${message.substring(0, 80)}...`);
}

// Add the critical issues found from E2E testing
console.log('Adding current E2E testing issues...');

logIssue(
  'authentication_failure',
  'https://family-nest-auctions.vercel.app',
  'Buyer registration flow failing - registerUser() returns false in E2E tests',
  {
    test: 'e2e-flows.spec.js:110',
    impact: 'high',
    component: 'registration'
  }
);

logIssue(
  'authorization_failure',
  'https://family-nest-auctions.vercel.app/account-dashboard.html',
  'Account dashboard redirects to homepage with ?login=1 instead of showing dashboard',
  {
    test: 'e2e-flows.spec.js:189',
    impact: 'high',
    component: 'dashboard_access'
  }
);

logIssue(
  'navigation_failure',
  'https://family-nest-auctions.vercel.app',
  'Navigation link click timeout - auction-browse link may not exist or be clickable',
  {
    test: 'e2e-flows.spec.js:413',
    impact: 'medium',
    component: 'navigation'
  }
);

logIssue(
  'javascript_error',
  'https://family-nest-auctions.vercel.app/account-profile.html',
  'SUPABASE_URL redeclaration error on account-profile.html',
  {
    impact: 'medium',
    component: 'javascript_execution'
  }
);

logIssue(
  'javascript_error',
  'https://family-nest-auctions.vercel.app/messages.html',
  'SUPABASE_URL redeclaration error on messages.html',
  {
    impact: 'medium',
    component: 'javascript_execution'
  }
);

logIssue(
  'missing_feature',
  'https://family-nest-auctions.vercel.app',
  'Seller application links not found - "Become a Seller" feature may not be implemented',
  {
    test: 'e2e-flows.spec.js:206',
    impact: 'medium',
    component: 'seller_onboarding'
  }
);

console.log('Issues added. Total issues now logged.');