const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const { promisify } = require('util');

const execPromise = promisify(exec);
const ISSUES_PATH = path.join(__dirname, '..', 'issues.jsonl');

// Import testers
const FunctionalTester = require('./functional-test');
const { runTests } = require('./test-runner');

async function logIssue(type, url, message, metadata = {}) {
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
  return issue;
}

async function runFunctionalTests() {
  console.log('=== Running Functional Tests on Production ===');
  const tester = new FunctionalTester();

  try {
    const results = await tester.runFullSuite();
    console.log(`Functional tests completed. Critical flows: ${results.criticalFlows.length} issues`);
    if (results.registration) {
      console.log(`Registration: ${results.registration.success ? 'SUCCESS' : 'FAILED'}`);
    }
    return results;
  } catch (error) {
    console.error('Functional tests failed:', error);
    await logIssue('system_error', 'https://family-nest-auctions.vercel.app',
      `Functional tests failed: ${error.message}`);
    return null;
  }
}

async function runE2ETests() {
  console.log('=== Running E2E Tests on Production ===');

  try {
    // Run e2e-flows.spec.js with production config
    const { stdout, stderr } = await execPromise(
      'npx playwright test tests/e2e-flows.spec.js --config=playwright.config.production.js --project=chromium',
      { cwd: path.join(__dirname, '..') }
    );

    console.log('E2E tests completed.');

    // Parse output for failures
    if (stderr || stdout.includes('failed')) {
      const failureMatch = stdout.match(/(\d+) failed/);
      const failureCount = failureMatch ? parseInt(failureMatch[1]) : 0;

      if (failureCount > 0) {
        await logIssue('e2e_test_failure', 'https://family-nest-auctions.vercel.app',
          `${failureCount} E2E tests failed. Check test-results/ directory for details.`,
          { failureCount, output: stdout.substring(0, 500) });
      }
    }

    return { stdout, stderr };
  } catch (error) {
    console.error('E2E tests failed:', error.message);
    await logIssue('system_error', 'https://family-nest-auctions.vercel.app',
      `E2E tests execution failed: ${error.message}`);
    return null;
  }
}

async function debugRegistrationIssue() {
  console.log('=== Debugging Registration Issue ===');

  // This would involve more detailed testing of the registration flow
  // For now, just log that we need to investigate
  await logIssue('investigation_needed', 'https://family-nest-auctions.vercel.app',
    'Registration flow needs debugging: check modal interactions, Supabase auth, and form submission');

  return true;
}

async function main() {
  console.log('=== RESUMING QA TESTING FROM PAUSED STATE ===');
  console.log('Timestamp:', new Date().toISOString());
  console.log('Production URL: https://family-nest-auctions.vercel.app');
  console.log('Loading status from qa/testing-status.json...');

  try {
    const status = JSON.parse(fs.readFileSync(
      path.join(__dirname, 'testing-status.json'), 'utf8'));
    console.log(`Last status: ${status.last_action}`);
    console.log(`Critical issues to investigate: ${status.critical_issues_found.length}`);

    // Show next steps
    console.log('\n=== NEXT STEPS ===');
    status.next_steps_when_resuming.forEach((step, i) => {
      console.log(`${i + 1}. ${step}`);
    });

  } catch (error) {
    console.log('Could not load status file, starting fresh...');
  }

  console.log('\n=== STARTING TESTING ===');

  // 1. Run functional tests
  await runFunctionalTests();

  // 2. Run E2E tests
  await runE2ETests();

  // 3. Debug specific issues
  await debugRegistrationIssue();

  console.log('\n=== TESTING COMPLETE ===');
  console.log('Check issues.jsonl for logged issues.');
  console.log('Next: Use qa/agent.js to analyze and fix issues.');
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { runFunctionalTests, runE2ETests, debugRegistrationIssue };