const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_ACCESS_TOKEN; // service role key

async function createTestAccounts() {
  console.log('Creating test accounts...');

  const accounts = [
    { email: 'buyer-test@example.com', password: 'test123456', fullName: 'Test Buyer', role: 'buyer' },
    { email: 'seller-test@example.com', password: 'test123456', fullName: 'Test Seller', role: 'seller' },
    { email: 'admin-test@example.com', password: 'test123456', fullName: 'Test Admin', role: 'admin' }
  ];

  for (const account of accounts) {
    try {
      await createUser(account);
      console.log(`Created ${account.role} account: ${account.email}`);
    } catch (error) {
      console.error(`Failed to create ${account.role} account:`, error.message);
    }
  }

  console.log('Test account creation complete.');
}

async function createUser({ email, password, fullName, role }) {
  // Use Supabase Auth admin API to create user
  const response = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
      'apikey': SUPABASE_SERVICE_KEY
    },
    body: JSON.stringify({
      email,
      password,
      email_confirm: true, // auto-confirm
      user_metadata: { full_name: fullName, role }
    })
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error: ${response.status} ${error}`);
  }

  const user = await response.json();
  console.log(`User ${email} created with ID: ${user.id}`);

  // Update profile based on role
  await updateProfile(user.id, { fullName, role });

  return user;
}

async function updateProfile(userId, { fullName, role }) {
  // Update profiles table via REST API
  const response = await fetch(`${SUPABASE_URL}/rest/v1/profiles`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
      'apikey': SUPABASE_SERVICE_KEY,
      'Prefer': 'resolution=merge-duplicates'
    },
    body: JSON.stringify({
      id: userId,
      full_name: fullName,
      email: `${role}-test@example.com`,
      is_seller: role === 'seller' || role === 'admin',
      is_admin: role === 'admin',
      updated_at: new Date().toISOString()
    })
  });

  if (!response.ok && response.status !== 409) { // 409 = already exists
    const error = await response.text();
    throw new Error(`Profile update failed: ${response.status} ${error}`);
  }

  // If seller, also create sellers table entry
  if (role === 'seller' || role === 'admin') {
    await createSeller(userId, fullName);
  }
}

async function createSeller(userId, fullName) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/sellers`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
      'apikey': SUPABASE_SERVICE_KEY,
      'Prefer': 'resolution=merge-duplicates'
    },
    body: JSON.stringify({
      user_id: userId,
      business_name: `${fullName}'s Business`,
      contact_name: fullName,
      contact_email: `${userId.substring(0, 8)}@example.com`,
      status: 'active',
      is_verified: true,
      created_at: new Date().toISOString()
    })
  });

  if (!response.ok && response.status !== 409) {
    const error = await response.text();
    console.warn(`Seller creation failed: ${response.status} ${error}`);
  }
}

// Run if called directly
if (require.main === module) {
  createTestAccounts().catch(console.error);
}

module.exports = { createTestAccounts };