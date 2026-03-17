const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const ISSUES_PATH = path.join(__dirname, '..', 'issues.jsonl');

async function runTests() {
  console.log('Running Playwright test suite...');

  return new Promise((resolve) => {
    const startTime = Date.now();
    const child = exec('npm test -- --reporter=line', {
      cwd: path.join(__dirname, '..'),
      maxBuffer: 10 * 1024 * 1024 // 10MB
    });

    let output = '';

    child.stdout.on('data', (data) => {
      output += data.toString();
      process.stdout.write(data);
    });

    child.stderr.on('data', (data) => {
      output += data.toString();
      process.stderr.write(data);
    });

    child.on('close', (code) => {
      const duration = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log(`\nTests completed in ${duration}s with exit code ${code}`);

      // Parse output for failures
      const failures = parseFailures(output);

      if (failures.length > 0) {
        console.log(`Found ${failures.length} test failures`);
        failures.forEach(f => logTestFailure(f));
      } else {
        console.log('All tests passed!');
      }

      resolve({ code, failures });
    });

    child.on('error', (error) => {
      console.error('Failed to run tests:', error);
      resolve({ code: 1, failures: [] });
    });
  });
}

function parseFailures(output) {
  const failures = [];
  const lines = output.split('\n');

  // Look for failure patterns
  // Example: "  1) [Mobile Chrome] › tests\console.spec.js:38:1 › login modal opens without errors"
  const failureRegex = /^\s*(\d+\))\s+\[([^\]]+)\]\s+›\s+(.+)$/;
  const errorRegex = /^\s*Error:/;

  let currentFailure = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const failureMatch = line.match(failureRegex);

    if (failureMatch) {
      if (currentFailure) {
        failures.push(currentFailure);
      }
      currentFailure = {
        project: failureMatch[2],
        test: failureMatch[3],
        errorLines: []
      };
    } else if (currentFailure && errorRegex.test(line)) {
      currentFailure.errorLines.push(line.trim());
      // Capture next few lines of error
      for (let j = i + 1; j < Math.min(i + 10, lines.length); j++) {
        if (lines[j].trim() === '' || lines[j].match(/^\s*at\s+/)) {
          currentFailure.errorLines.push(lines[j].trim());
        } else {
          break;
        }
      }
    }
  }

  if (currentFailure) {
    failures.push(currentFailure);
  }

  // Also look for summary line: "  X failed"
  const summaryMatch = output.match(/(\d+)\s+failed/);
  if (summaryMatch && failures.length === 0) {
    // Generic failure if parsing didn't catch specifics
    failures.push({
      project: 'unknown',
      test: 'Test suite',
      errorLines: [`${summaryMatch[1]} tests failed`]
    });
  }

  return failures;
}

function logTestFailure(failure) {
  const issue = {
    id: `test_failure_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    type: 'test_failure',
    url: 'https://family-nest-auctions.vercel.app/',
    message: `[${failure.project}] ${failure.test}: ${failure.errorLines.join(' ').substring(0, 200)}`,
    timestamp: new Date().toISOString(),
    metadata: failure
  };

  fs.appendFileSync(ISSUES_PATH, JSON.stringify(issue) + '\n');
  console.log(`Logged test failure: ${failure.test}`);
}

// Run if called directly
if (require.main === module) {
  runTests().then(({ code, failures }) => {
    process.exit(failures.length > 0 ? 1 : 0);
  });
}

module.exports = { runTests };