#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

const PLACEHOLDERS = {
  PROJECT_NAME: '{{PROJECT_NAME}}',
  PRODUCTION_URL: '{{PRODUCTION_URL}}',
  PRODUCTION_DOMAIN: '{{PRODUCTION_DOMAIN}}',
  OLD_NAMESPACE: '{{OLD_NAMESPACE}}',
  NEW_NAMESPACE: '{{NEW_NAMESPACE}}'
};

async function askQuestion(question, defaultValue = '') {
  return new Promise((resolve) => {
    rl.question(`${question} ${defaultValue ? `[${defaultValue}] ` : ''}`, (answer) => {
      resolve(answer.trim() || defaultValue);
    });
  });
}

function replacePlaceholders(content, replacements) {
  let newContent = content;
  for (const [placeholder, value] of Object.entries(replacements)) {
    const regex = new RegExp(placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
    newContent = newContent.replace(regex, value);
  }
  return newContent;
}

async function processFile(filePath, replacements) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    const newContent = replacePlaceholders(content, replacements);
    if (newContent !== content) {
      fs.writeFileSync(filePath, newContent, 'utf8');
      console.log(`  Updated: ${path.relative(process.cwd(), filePath)}`);
    }
  } catch (error) {
    console.error(`  Error processing ${filePath}:`, error.message);
  }
}

async function processDirectory(dirPath, replacements) {
  const files = fs.readdirSync(dirPath, { withFileTypes: true });
  for (const file of files) {
    const fullPath = path.join(dirPath, file.name);
    if (file.isDirectory()) {
      await processDirectory(fullPath, replacements);
    } else {
      // Only process certain file types
      if (file.name.endsWith('.js') || file.name.endsWith('.json') ||
          file.name.endsWith('.md') || file.name.endsWith('.toml') ||
          file.name === '.env.template' || file.name === 'package.json' ||
          file.name === 'CLAUDE.md') {
        await processFile(fullPath, replacements);
      }
    }
  }
}

async function main() {
  console.log('=== Project Setup Wizard ===');
  console.log('This script will replace placeholders in template files.\n');

  const projectName = await askQuestion('Project name:', 'my-project');
  const productionURL = await askQuestion('Production URL:', 'https://my-project.vercel.app');
  const productionDomain = await askQuestion('Production domain (for Claude permissions):', new URL(productionURL).hostname);
  const oldNamespace = await askQuestion('Old JavaScript namespace (e.g., FNA):', 'FNA');
  const newNamespace = await askQuestion('New JavaScript namespace (e.g., BY):', 'BY');

  console.log('\nSummary:');
  console.log(`  Project Name: ${projectName}`);
  console.log(`  Production URL: ${productionURL}`);
  console.log(`  Production Domain: ${productionDomain}`);
  console.log(`  Old Namespace: ${oldNamespace}`);
  console.log(`  New Namespace: ${newNamespace}`);

  const confirm = await askQuestion('\nProceed with replacements? (y/n):', 'y');
  if (confirm.toLowerCase() !== 'y') {
    console.log('Setup cancelled.');
    rl.close();
    return;
  }

  const replacements = {
    [PLACEHOLDERS.PROJECT_NAME]: projectName,
    [PLACEHOLDERS.PRODUCTION_URL]: productionURL,
    [PLACEHOLDERS.PRODUCTION_DOMAIN]: productionDomain,
    [PLACEHOLDERS.OLD_NAMESPACE]: oldNamespace,
    [PLACEHOLDERS.NEW_NAMESPACE]: newNamespace
  };

  console.log('\nProcessing files...');

  // Process current directory (where script is run)
  await processDirectory(process.cwd(), replacements);

  // Rename .env.template to .env
  const envTemplate = path.join(process.cwd(), '.env.template');
  const envFile = path.join(process.cwd(), '.env');
  if (fs.existsSync(envTemplate)) {
    fs.copyFileSync(envTemplate, envFile);
    console.log(`  Created: ${path.relative(process.cwd(), envFile)} from template`);
  }

  console.log('\nSetup complete!');
  console.log('\nNext steps:');
  console.log('1. Install dependencies: npm install');
  console.log('2. Install Playwright browsers: npx playwright install');
  console.log('3. Edit .env file with your API keys');
  console.log('4. Initialize Supabase: npx supabase init');
  console.log('5. Login to Vercel: vercel login');
  console.log('6. Run tests: npm run dev & npm test');

  rl.close();
}

if (require.main === module) {
  main().catch(error => {
    console.error('Setup failed:', error);
    rl.close();
    process.exit(1);
  });
}