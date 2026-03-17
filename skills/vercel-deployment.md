# Vercel Deployment Skills & Cheat Sheet

## Installation & Authentication

### CLI Installation
```bash
# Install Vercel CLI globally
npm install -g vercel

# Check version
vercel --version

# Login to Vercel account
vercel login

# Logout
vercel logout

# Check authentication status
vercel whoami
```

## Project Deployment

### Basic Deployment
```bash
# Deploy current directory to Vercel
vercel

# Deploy to production (alias)
vercel --prod

# Deploy with specific project name
vercel --name my-project

# Preview deployment (default)
vercel --preview
```

### Environment & Configuration
```bash
# Link project to Vercel
vercel link

# Unlink project
vercel unlink

# Pull environment variables
vercel env pull

# List environment variables
vercel env ls

# Add environment variable
vercel env add VARIABLE_NAME
```

## Project Management

### Listing Projects
```bash
# List all projects
vercel projects

# List deployments for current project
vercel list

# View project information
vercel project
```

### Deployment Management
```bash
# List all deployments
vercel ls

# View specific deployment
vercel inspect [deployment-id]

# Remove deployment
vercel rm [deployment-id]

# Rollback to previous deployment
vercel rollback [deployment-id]
```

## Domains & Aliases

### Domain Management
```bash
# List domains
vercel domains

# Add domain
vercel domains add example.com

# Remove domain
vercel domains rm example.com

# Verify domain
vercel domains verify example.com
```

### Aliases
```bash
# Create alias for deployment
vercel alias set [deployment-url] [alias]

# List aliases
vercel alias ls

# Remove alias
vercel alias rm [alias]
```

## Serverless Functions

### Function Development
```bash
# Serve functions locally
vercel dev

# Build project locally
vercel build

# Inspite function logs
vercel logs [deployment-url] --function=api/my-function
```

### Environment Configuration
```bash
# Add environment variable for production
vercel env add VARIABLE_NAME production

# Add for preview environment
vercel env add VARIABLE_NAME preview

# Add for development environment
vercel env add VARIABLE_NAME development
```

## Integration with Deals-Coupons-AI

### Static Site Deployment
Since Deals-Coupons-AI is a static HTML site with Supabase backend:

1. **Configure `vercel.json`**:
```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=0, must-revalidate"
        }
      ]
    }
  ]
}
```

2. **Environment Variables**:
```bash
# Add Supabase environment variables
vercel env add SUPABASE_URL
vercel env add SUPABASE_KEY
```

### Deployment Workflow
```bash
# 1. Login to Vercel
vercel login

# 2. Link project (first time)
vercel link

# 3. Deploy to preview
vercel

# 4. Deploy to production
vercel --prod

# 5. Set up custom domain (optional)
vercel domains add yourdomain.com
```

### Package.json Scripts
Add these scripts to your `package.json`:
```json
{
  "scripts": {
    "vercel:deploy": "vercel",
    "vercel:prod": "vercel --prod",
    "vercel:dev": "vercel dev",
    "vercel:build": "vercel build",
    "vercel:logs": "vercel logs"
  }
}
```

## Advanced Configuration

### `vercel.json` Configuration
```json
{
  "version": 2,
  "builds": [
    {
      "src": "*.html",
      "use": "@vercel/static"
    },
    {
      "src": "api/**/*.js",
      "use": "@vercel/node"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "/api/$1"
    },
    {
      "src": "/(.*)",
      "dest": "/index.html"
    }
  ],
  "env": {
    "SUPABASE_URL": "@supabase_url",
    "SUPABASE_KEY": "@supabase_key"
  }
}
```

### Environment Variables Management
```bash
# Pull .env.local from Vercel
vercel env pull .env.local

# Push local environment to Vercel
vercel env push

# Import from .env file
vercel env pull .env

# Export to .env file
vercel env pull .env.production
```

## Monitoring & Logs

### Viewing Logs
```bash
# View logs for current project
vercel logs

# View logs for specific deployment
vercel logs [deployment-url]

# Follow logs in real-time
vercel logs --follow

# Filter logs by function
vercel logs --function=api/my-function
```

### Analytics & Monitoring
```bash
# View analytics
vercel analytics

# View bandwidth usage
vercel bandwidth

# Check deployment status
vercel status
```

## Troubleshooting

### Common Issues
- **"No existing credentials found"**: Run `vercel login`
- **"Project not found"**: Run `vercel link` to link project
- **"Environment variables missing"**: Use `vercel env pull` or set via dashboard
- **"Deployment failed"**: Check `vercel logs` for error details

### Debug Commands
```bash
# Debug with verbose output
vercel --debug

# Check network connectivity
vercel ping

# View CLI configuration
vercel config
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Deploy to Vercel
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npm run build
      - uses: amondnet/vercel-action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: ./
```

### Environment Secrets
```bash
# Set secrets for CI/CD
vercel secrets add my-secret-name "secret-value"

# List secrets
vercel secrets ls

# Remove secret
vercel secrets rm my-secret-name
```

## Best Practices

### Deployment Strategy
1. **Preview Deployments**: Always deploy to preview first with `vercel`
2. **Production Promotion**: Use `vercel --prod` after testing preview
3. **Rollback Plan**: Keep previous deployments for quick rollback
4. **Environment Separation**: Use different projects for staging/production

### Performance Optimization
1. **Static Assets**: Use `Cache-Control` headers for static files
2. **Serverless Functions**: Keep functions small and focused
3. **Edge Network**: Deploy close to users for faster response times
4. **Image Optimization**: Use Vercel's Image Optimization API

### Security
1. **Environment Variables**: Never commit secrets to git
2. **Access Control**: Use Vercel teams for collaboration
3. **Domain Security**: Enable HTTPS and security headers
4. **Function Security**: Validate inputs and sanitize outputs

## Migration from Other Hosts

### Moving from GitHub Pages
1. Install Vercel CLI: `npm install -g vercel`
2. Login: `vercel login`
3. Deploy: `vercel --prod`
4. Configure custom domain in Vercel dashboard
5. Update DNS records

### Moving from Netlify
1. Export environment variables from Netlify
2. Import to Vercel: `vercel env add`
3. Update build settings in `vercel.json`
4. Deploy: `vercel --prod`
5. Update DNS settings