# Cloudflare Worker - GitHub Actions Trigger

This worker allows the website to trigger GitHub Actions without exposing the GitHub token.

## Setup Instructions

### Step 1: Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name it: "Tenders Site Trigger"
4. Select scopes: `repo` (Full control of private repositories)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again!)

### Step 2: Create Cloudflare Worker

1. Go to https://dash.cloudflare.com/
2. Create a free account if you don't have one
3. Go to "Workers & Pages" → "Create application" → "Create Worker"
4. Name it: `tenders-trigger`
5. Click "Deploy"

### Step 3: Add the Code

1. After deployment, click "Edit code"
2. Delete the default code
3. Copy the contents of `worker.js` and paste it
4. Click "Save and Deploy"

### Step 4: Add Environment Variable

1. Go to Worker settings → "Variables"
2. Click "Add variable"
3. Name: `GITHUB_TOKEN`
4. Value: Paste your GitHub token from Step 1
5. Click "Encrypt" (important for security!)
6. Click "Save and Deploy"

### Step 5: Get Your Worker URL

Your worker URL will be something like:
`https://tenders-trigger.<your-subdomain>.workers.dev`

### Step 6: Update the Website

Update the `WORKER_URL` in `app.js` with your worker URL.

## Testing

You can test the worker with curl:

```bash
curl -X POST https://tenders-trigger.<your-subdomain>.workers.dev
```

## Security Notes

- The GitHub token is stored encrypted in Cloudflare
- CORS is restricted to the website domain only
- The worker only accepts POST requests
- Rate limiting is handled by GitHub's API limits
