// api/unsubscribe.js -- Vercel serverless function
// Handles GET /api/unsubscribe?email=xxx

const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = (process.env.SUPABASE_URL || '').trim();
const SUPABASE_KEY = (process.env.SUPABASE_KEY || '').trim();

module.exports = async function handler(req, res) {
  const email = (req.query.email || '').trim().toLowerCase();

  if (!email) {
    return res.status(400).send(page('Error', '<p>No email provided.</p>'));
  }

  const db = createClient(SUPABASE_URL, SUPABASE_KEY);
  await db.from('subscribers').update({ unsubscribed: true }).eq('email', email);

  return res.status(200).send(page(
    'Unsubscribed',
    `<h2 style="color:#FF5E1A">You've been unsubscribed.</h2>
     <p style="color:#aaa">We've removed <b>${email}</b> from all deal alerts. Sorry to see you go.</p>
     <a href="/" style="display:inline-block;margin-top:20px;color:#FF5E1A">Back to deals &rarr;</a>`
  ));
};

function page(title, body) {
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${title}</title>
    <style>body{background:#111114;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .box{max-width:480px;padding:40px;text-align:center}</style></head>
    <body><div class="box">${body}</div></body></html>`;
}
