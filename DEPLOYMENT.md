# Deployment Guide

## GitHub Actions Deployment Setup

### 1. Create SSH Key for GitHub Actions

On your VDS, create a dedicated SSH key for GitHub Actions:

```bash
# On your VDS
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions_deploy
```

Add the public key to authorized_keys:

```bash
cat ~/.ssh/github_actions_deploy.pub >> ~/.ssh/authorized_keys
```

### 2. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:

- **`VDS_HOST`**: Your VDS IP address or domain (e.g., `123.45.67.89` or `vds.example.com`)
- **`VDS_USER`**: SSH username (e.g., `gordon` or `root`)
- **`VDS_SSH_KEY`**: The **private** key content from `~/.ssh/github_actions_deploy` (the entire content including `-----BEGIN` and `-----END` lines)
- **`VDS_SSH_PORT`**: SSH port (optional, defaults to 22 if not set)

### 3. Setup Systemd Service on VDS

Copy the service file to systemd:

```bash
sudo cp lingualeo-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lingualeo-bot.service
```

### 4. Deploy

1. Go to your GitHub repository
2. Click on "Actions" tab
3. Select "Deploy Bot to VDS" workflow
4. Click "Run workflow" button
5. Select the branch (usually `main` or `master`)
6. Click "Run workflow"

The workflow will:
- Pull latest code from GitHub
- Restart the systemd service (which rebuilds and recreates containers)

## Security Best Practices

1. **Use a dedicated SSH key** - Don't use your personal SSH key
2. **Restrict SSH key permissions** - The key should only have access to the bot directory
3. **Use SSH key with passphrase** (optional but recommended)
4. **Limit sudo access** - Configure sudoers to allow only the specific command needed
5. **Use firewall rules** - Only allow SSH from trusted IPs if possible

## Alternative: Using SSH Config with Limited Permissions

For better security, you can create a restricted user or use `command=` restrictions in `~/.ssh/authorized_keys`:

```
command="cd /home/gordon/coding/lingualeo_bot && git pull && sudo systemctl restart lingualeo-bot.service" ssh-ed25519 AAAA... github-actions
```

## Troubleshooting

- Check GitHub Actions logs if deployment fails
- Verify SSH key has correct permissions: `chmod 600 ~/.ssh/github_actions_deploy`
- Test SSH connection manually: `ssh -i ~/.ssh/github_actions_deploy user@host`
- Check systemd logs: `sudo journalctl -u lingualeo-bot.service -f`

