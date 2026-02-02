/**
 * Cloudflare Worker - GitHub Actions Trigger Proxy
 *
 * This worker allows the website to trigger GitHub Actions without exposing the token.
 *
 * Setup:
 * 1. Create a GitHub Personal Access Token with 'repo' scope
 * 2. In Cloudflare Workers, add environment variable: GITHUB_TOKEN = your_token
 * 3. Deploy this worker
 * 4. Update the website to call this worker's URL
 */

const GITHUB_REPO = 'mnigli/tenders-site';
const ALLOWED_ORIGIN = 'https://mnigli.github.io';

export default {
  async fetch(request, env) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      });
    }

    // Only allow POST requests
    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Method not allowed' }), {
        status: 405,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
        },
      });
    }

    // Check origin
    const origin = request.headers.get('Origin');
    if (origin && !origin.includes('mnigli.github.io') && !origin.includes('localhost')) {
      return new Response(JSON.stringify({ error: 'Forbidden' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Rate limiting - simple check (in production, use KV or Durable Objects)
    // For now, we trust the GitHub API rate limits

    try {
      // Trigger GitHub Actions via repository_dispatch
      const response = await fetch(
        `https://api.github.com/repos/${GITHUB_REPO}/dispatches`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'Cloudflare-Worker-Tenders-Trigger',
          },
          body: JSON.stringify({
            event_type: 'trigger-scrape',
          }),
        }
      );

      if (response.status === 204) {
        return new Response(JSON.stringify({
          success: true,
          message: 'Scrape triggered successfully! The data will update in about 2 minutes.'
        }), {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
          },
        });
      } else {
        const errorText = await response.text();
        console.error('GitHub API error:', response.status, errorText);
        return new Response(JSON.stringify({
          success: false,
          error: 'Failed to trigger scrape',
          details: response.status
        }), {
          status: 500,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
          },
        });
      }
    } catch (error) {
      console.error('Error:', error);
      return new Response(JSON.stringify({
        success: false,
        error: 'Internal server error'
      }), {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
        },
      });
    }
  },
};
