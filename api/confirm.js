// api/confirm.js -- Vercel serverless function
// Handles GET /api/confirm?token=xxx  (email confirmation link)

const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_KEY;
const RESEND_KEY   = process.env.RESEND_API_KEY;
const FROM_EMAIL   = process.env.FROM_EMAIL || 'onboarding@resend.dev';
const FROM_NAME    = process.env.FROM_NAME  || 'Coupons, Deals & Steals';
const SITE_URL     = (process.env.SITE_URL  || 'https://deals-coupons-ai.vercel.app').replace(/\/$/, '');
const TG_LINK      = process.env.TELEGRAM_INVITE_LINK || 'https://t.me/Coupons_Deals_Steals';
const FB_LINK      = process.env.FACEBOOK_GROUP_LINK  || '';

function supabase() {
  return createClient(SUPABASE_URL, SUPABASE_KEY);
}

function decodeToken(token) {
  try { return Buffer.from(token, 'base64url').toString('utf8'); } catch { return null; }
}

async function sendWelcome(email, firstName) {
  if (!RESEND_KEY) return;
  const name = firstName || 'there';

  // Pull top 3 deals for welcome email
  const db = supabase();
  const { data: deals } = await db
    .from('deals')
    .select('title,price,discount_pct,amazon_url,image_url')
    .eq('website_published', true)
    .order('discount_pct', { ascending: false })
    .limit(3);

  const dealsHtml = (deals || []).map(d => `
    <tr>
      <td style="padding:8px"><img src="${d.image_url||''}" width="56" height="56" style="object-fit:cover;border-radius:4px"></td>
      <td style="padding:8px;color:#fff"><b>${(d.title||'').slice(0,60)}</b><br>
        <span style="color:#FF5E1A">$${d.price || '?'} &mdash; ${d.discount_pct || 0}% off</span></td>
      <td style="padding:8px">
        <a href="${d.amazon_url||'#'}" style="background:#FF5E1A;color:#fff;padding:6px 14px;text-decoration:none;border-radius:3px;font-size:13px;white-space:nowrap">See Deal</a>
      </td>
    </tr>`).join('');

  const fbRow = FB_LINK ? `<a href="${FB_LINK}" style="display:inline-block;margin-left:10px;background:#1877F2;color:#fff;font-weight:700;padding:10px 22px;border-radius:4px;text-decoration:none">Join Facebook Group</a>` : '';

  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${RESEND_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: `${FROM_NAME} <${FROM_EMAIL}>`,
      to: [email],
      subject: `Welcome, ${name}! Your deal alerts are on.`,
      html: `
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto;background:#111114;color:#fff;padding:32px;border-radius:8px">
          <h2 style="color:#FF5E1A;margin:0 0 8px">You're in!</h2>
          <p style="color:#ccc">Hi ${name}, welcome to ${FROM_NAME}. You'll now get daily alerts on the biggest Amazon deals.</p>

          ${dealsHtml ? `
          <h3 style="color:#fff;margin:28px 0 12px">Today's top deals</h3>
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#1a1a1f;border-radius:6px">
            ${dealsHtml}
          </table>
          <p style="margin:16px 0"><a href="${SITE_URL}/top-deals" style="color:#FF5E1A">See all deals &rarr;</a></p>
          ` : ''}

          <h3 style="color:#fff;margin:28px 0 12px">Join our communities</h3>
          <p style="color:#aaa;font-size:14px">Get instant alerts and connect with other deal hunters.</p>
          <a href="${TG_LINK}" style="display:inline-block;background:#229ED9;color:#fff;font-weight:700;padding:10px 22px;border-radius:4px;text-decoration:none">Join Telegram</a>
          ${fbRow}

          <p style="color:#444;font-size:12px;margin-top:32px">
            <a href="${SITE_URL}/api/unsubscribe?email=${encodeURIComponent(email)}" style="color:#555">Unsubscribe</a>
          </p>
        </div>
      `,
    }),
  });
}

module.exports = async function handler(req, res) {
  const token = req.query.token || '';
  if (!token) {
    return res.status(400).send('<p>Invalid confirmation link.</p>');
  }

  const email = decodeToken(token);
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).send('<p>Invalid confirmation link.</p>');
  }

  const db = supabase();
  const { data: sub } = await db
    .from('subscribers')
    .select('id, first_name, confirmed')
    .eq('email', email)
    .maybeSingle();

  if (!sub) {
    return res.redirect(302, `${SITE_URL}/?confirmed=notfound`);
  }

  if (!sub.confirmed) {
    await db.from('subscribers')
      .update({ confirmed: true, confirmed_at: new Date().toISOString() })
      .eq('id', sub.id);

    // Send welcome email async (don't block redirect)
    sendWelcome(email, sub.first_name).catch(console.error);
  }

  // Redirect to welcome page
  return res.redirect(302, `${SITE_URL}/welcome`);
};
