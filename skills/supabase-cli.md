# Supabase CLI Skills & Cheat Sheet

## Installation & Setup

### Local Project Setup
```bash
# Initialize Supabase in your project (first time)
npx supabase init

# Start local Supabase services (requires Docker)
npx supabase start

# Stop local services
npx supabase stop

# Check status of local services
npx supabase status
```

### Global Installation (Alternative)
Supabase CLI doesn't support global npm installation. Use package managers:
- **Windows**: Download from [Supabase CLI releases](https://github.com/supabase/cli/releases)
- **Mac/Linux**: Use Homebrew: `brew install supabase/tap/supabase`

## Database Management

### Local Development
```bash
# Push local schema to remote
npx supabase db push

# Pull remote schema to local
npx supabase db pull

# Reset local database (clean slate)
npx supabase db reset

# Create migration from changes
npx supabase migration new <migration_name>
```

### Migration Commands
```bash
# List all migrations
npx supabase migration list

# Apply all pending migrations
npx supabase migration up

# Repair migration history
npx supabase migration repair
```

## Authentication & Edge Functions

### Managing Auth
```bash
# List all auth users
npx supabase auth list

# Create auth user
npx supabase auth create-user --email user@example.com

# Update auth user
npx supabase auth update-user --id <user-id> --email new@example.com
```

### Edge Functions
```bash
# Create new edge function
npx supabase functions new <function-name>

# Deploy edge function
npx supabase functions deploy <function-name>

# Invoke edge function locally
npx supabase functions serve <function-name>

# List all edge functions
npx supabase functions list
```

## Storage

### Bucket Management
```bash
# Create storage bucket
npx supabase storage create <bucket-name>

# List storage buckets
npx supabase storage list

# Upload file to bucket
npx supabase storage upload <bucket-name> <file-path>
```

## Project Configuration

### Linking Projects
```bash
# Link to remote Supabase project
npx supabase link --project-ref <project-ref>

# Unlink from remote project
npx supabase unlink

# View current project config
npx supabase project info
```

### Environment Variables
```bash
# Set environment variable
npx supabase secrets set <KEY>=<VALUE>

# List all environment variables
npx supabase secrets list

# Unset environment variable
npx supabase secrets unset <KEY>
```

## Useful Scripts for Deals-Coupons-AI

### Database Setup
```bash
# Apply SQL script
npx supabase db execute --file create-test-seller.sql

# Seed database with sample data
npx supabase db seed
```

### Local Development Workflow
1. Start local services: `npx supabase start`
2. Apply migrations: `npx supabase db push`
3. Seed data: `npx supabase db seed`
4. Run tests: `npm test`
5. Stop services: `npx supabase stop`

## Troubleshooting

### Common Issues
- **"Docker not running"**: Install Docker Desktop and ensure it's running
- **"Port already in use"**: Change ports in `supabase/config.toml`
- **"Migration conflicts"**: Use `npx supabase db reset` to start fresh

### Debug Commands
```bash
# View logs
npx supabase logs

# Check service health
npx supabase health

# Generate types for TypeScript
npx supabase gen types typescript --local > types/supabase.ts
```

## Integration with Package.json
Add these scripts to your `package.json`:
```json
{
  "scripts": {
    "supabase:start": "supabase start",
    "supabase:stop": "supabase stop",
    "supabase:reset": "supabase db reset",
    "supabase:status": "supabase status",
    "supabase:push": "supabase db push",
    "supabase:pull": "supabase db pull",
    "supabase:types": "supabase gen types typescript --local > types/supabase.ts"
  }
}
```