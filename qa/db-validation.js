const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_KEY;

const ISSUES_PATH = path.join(__dirname, '..', 'issues.jsonl');

async function validateDatabase() {
  console.log('Validating Supabase database...');

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    logIssue('db_validation', 'https://family-nest-auctions.vercel.app/', 'Missing Supabase credentials in .env');
    return false;
  }

  const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

  try {
    // Test connection by fetching from profiles table
    const { data: profiles, error } = await supabase
      .from('profiles')
      .select('count')
      .limit(1);

    if (error) {
      logIssue('db_validation', 'https://family-nest-auctions.vercel.app/', `Profiles table query failed: ${error.message}`);
      return false;
    }

    console.log('✓ Database connection successful');

    // Check for required tables
    const tables = ['profiles', 'sellers', 'items', 'bids', 'watchlist'];
    for (const table of tables) {
      const { error: tableError } = await supabase
        .from(table)
        .select('*')
        .limit(1);

      if (tableError && tableError.code === '42P01') { // table does not exist
        logIssue('db_validation', 'https://family-nest-auctions.vercel.app/', `Table ${table} does not exist`);
      } else if (tableError) {
        // Other error (maybe RLS)
        console.log(`Table ${table} accessible: ${!tableError}`);
      } else {
        console.log(`✓ Table ${table} exists`);
      }
    }

    // Check for demo data (seed reviews)
    const { data: reviews } = await supabase
      .from('reviews')
      .select('*')
      .limit(5);

    if (reviews && reviews.length > 0) {
      console.log(`Found ${reviews.length} reviews in database`);
      // Check if reviews are seeded (example: seller_id = 00000000-0000-0000-0000-000000000001)
      const seeded = reviews.filter(r => r.seller_id === '00000000-0000-0000-0000-000000000001');
      if (seeded.length > 0) {
        logIssue('db_validation', 'https://family-nest-auctions.vercel.app/', `Found ${seeded.length} seeded demo reviews in production database`);
      }
    }

    console.log('Database validation complete');
    return true;
  } catch (error) {
    logIssue('db_validation', 'https://family-nest-auctions.vercel.app/', `Database validation error: ${error.message}`);
    return false;
  }
}

function logIssue(type, url, message) {
  const issue = {
    id: `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    type,
    url,
    message,
    timestamp: new Date().toISOString()
  };
  fs.appendFileSync(ISSUES_PATH, JSON.stringify(issue) + '\n');
  console.log(`Logged DB issue: ${message}`);
}

// Run if called directly
if (require.main === module) {
  validateDatabase().catch(console.error);
}

module.exports = { validateDatabase };