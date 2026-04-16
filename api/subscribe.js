// api/subscribe.js -- Vercel serverless function
// Handles POST /api/subscribe from all website forms

const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL  = process.env.SUPABASE_URL;
const SUPABASE_KEY  = process.env.SUPABASE_KEY;
const RESEND_KEY    = process.env.RESEND_API_KEY;
const FROM_EMAIL    = process.env.FROM_EMAIL  || 'onboarding@resend.dev';
const FROM_NAME     = process.env.FROM_NAME   || 'Coupons, Deals & Steals';
const SITE_URL      = (process.env.SITE_URL   || 'https://deals-coupons-ai.vercel.app').replace(/\/$/, '');

function supabase() {
  return createClient(SUPABASE_URL, SUPABASE_KEY);
}

function makeReferralCode() {
  return Math.random().toString(36).slice(2, 10).toUpperCase();
}

// Simple reversible token — base64url of email
function makeToken(email) {
  return Buffer.from(email).toString('base64url');
}

async function sendConfirmation(email, firstName, token) {
  if (!RESEND_KEY) return;
  const confirmUrl = `${SITE_URL}/api/confirm?token=${token}`;
  const name = firstName || 'there';
  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${RESEND_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: `${FROM_NAME} <${FROM_EMAIL}>`,
      to: [email],
      subject: 'Confirm your email to get free Amazon deals',
      html: `
        <div style="font-family:sans-serif;max-width:520px;margin:0 auto;background:#111114;color:#fff;padding:32px;border-radius:8px">
          <h2 style="font-family:sans-serif;color:#FF5E1A;margin:0 0 16px">One click to confirm</h2>
          <p style="color:#ccc">Hi ${name},</p>
          <p style="color:#ccc">Click the button below to confirm your email and start getting free Amazon deal alerts.</p>
          <a href="${confirmUrl}" style="display:inline-block;margin:24px 0;background:#FF5E1A;color:#fff;font-weight:700;padding:14px 28px;border-radius:4px;text-decoration:none;font-size:16px">
            Confirm My Email &rarr;
          </a>
          <p style="color:#555;font-size:13px">If you didn't sign up, ignore this email.</p>
          <p style="color:#555;font-size:12px;margin-top:24px">
            <a href="${SITE_URL}/api/unsubscribe?email=${encodeURIComponent(email)}" style="color:#555">Unsubscribe</a>
          </p>
        </div>
      `,
    }),
  });
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch { body = {}; }
  }

  const email = (body.email || '').trim().toLowerCase();
  const firstName = (body.first_name || '').trim().slice(0, 50);
  const source = (body.source || 'web').slice(0, 30);

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Invalid email' });
  }

  const db = supabase();

  // Check if already subscribed
  const { data: existing } = await db
    .from('subscribers')
    .select('id, confirmed, unsubscribed')
    .eq('email', email)
    .maybeSingle();

  if (existing) {
    if (existing.unsubscribed) {
      // Re-subscribe
      await db.from('subscribers').update({ unsubscribed: false }).eq('id', existing.id);
    }
    if (!existing.confirmed) {
      // Resend confirmation
      await sendConfirmation(email, firstName, makeToken(email));
    }
    return res.status(200).json({ ok: true, status: 'existing' });
  }

  // New subscriber
  const referralCode = makeReferralCode();
  const { error } = await db.from('subscribers').insert({
    email,
    first_name: firstName || null,
    source,
    referral_code: referralCode,
    confirmed: false,
    joined_at: new Date().toISOString(),
    unsubscribed: false,
  });

  if (error) {
    console.error('Supabase insert error:', error);
    return res.status(500).json({ error: 'Database error' });
  }

  await sendConfirmation(email, firstName, makeToken(email));

  return res.status(200).json({ ok: true, status: 'created' });
};
