# LinguaLeo Bot

Utilities and bots for importing words into LinguaLeo vocabulary.

## Features

- **Telegram Bot**: Add Spanish words to your LinguaLeo dictionary via Telegram chat
- **Bulk Import Script**: Import words from JSON files
- **Automatic Authentication**: Handles login and cookie caching automatically
- **Smart Translation Matching**: Automatically selects the best translation from LinguaLeo suggestions
- **Duplicate Prevention**: Automatically checks if a word already exists before adding it, preventing duplicates

## Project Structure

```
.
├── bot.py                 # Telegram bot entry point
├── lingualeo/            # Reusable LinguaLeo client module
│   ├── __init__.py
│   └── client.py
├── data/
│   └── words/            # Sample word JSON files
├── examples/
│   └── lingualeo/        # Original API request examples
└── pyproject.toml        # Project dependencies (uv)
```

## Setup

### Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd lignualeo_scripts
```

2. Install dependencies:
```bash
uv sync
```

3. Configure environment variables:
```bash
cp env.example .env
# Edit .env with your credentials
```

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Required for Telegram bot
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Required for LinguaLeo authentication
LINGUALEO_EMAIL=your_email@example.com
LINGUALEO_PASSWORD=your_password_here

# Optional
# LINGUALEO_COOKIE_FILE=custom_cookies.json
# LINGUALEO_COOKIE=pre_existing_cookie_string
```

To get a Telegram bot token:
1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the instructions
3. Copy the token to your `.env` file

## Usage

### Running the Telegram Bot

The bot allows you to add words to LinguaLeo directly from Telegram:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the bot
python bot.py

# Or use uv directly
uv run python bot.py
```

#### Bot Commands

- `/start` - Get started and see usage instructions

#### Adding Words

**Single word:**
```
palabra
```

**Single word with translation:**
```
palabra — перевод
```

**Bulk import (multiple words, one per line):**
```
palabra1 — перевод1
palabra2 — перевод2
palabra3
```

The bot will:
- **Check if the word already exists** in your dictionary before adding it
- Automatically select the best translation if you provide a hint
- Use the first LinguaLeo suggestion if no translation is provided
- Process all words in bulk and provide a summary

**If a word already exists:**
- Single word: Bot responds with "Слово 'X' уже есть в словаре" (Word 'X' already exists in dictionary)
- Bulk import: Words that already exist are listed in a separate "Уже есть" (Already exists) section in the summary

## Docker Deployment

### Building the Image

```bash
docker build -t lignualeo-bot .
```

### Running with Docker

```bash
# Run the bot
docker run -d \
  --name lignualeo-bot \
  --env-file .env \
  -v $(pwd)/lingualeo_cookies.json:/app/lingualeo_cookies.json \
  lignualeo-bot

```

### Docker Compose (Optional)

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  bot:
    build: .
    container_name: lignualeo-bot
    env_file: .env
    volumes:
      - ./lingualeo_cookies.json:/app/lingualeo_cookies.json
    restart: unless-stopped
```

Run with:
```bash
docker-compose up -d
```

### Systemd Service (Production)

For production deployment on a VDS, you can use the provided systemd service file:

1. Copy the service file:
```bash
sudo cp lingualeo-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lingualeo-bot.service
```

2. The service automatically:
   - Pulls latest code from git
   - Rebuilds Docker containers
   - Restarts the bot

3. Manage the service:
```bash
sudo systemctl start lingualeo-bot.service
sudo systemctl stop lingualeo-bot.service
sudo systemctl restart lingualeo-bot.service
sudo systemctl status lingualeo-bot.service
```

### GitHub Actions Deployment

The repository includes a GitHub Actions workflow for one-click deployment to your VDS.

**Setup:**
1. Create an SSH key on your VDS for GitHub Actions
2. Add GitHub Secrets: `VDS_HOST`, `VDS_USER`, `VDS_SSH_KEY`, `VDS_SSH_PORT` (optional)
3. See `DEPLOYMENT.md` for detailed setup instructions

**Deploy:**
1. Go to **Actions** tab in GitHub
2. Select **"Deploy Bot to VDS"** workflow
3. Click **"Run workflow"** button
4. Select branch and deploy

The workflow will automatically pull the latest code and restart the bot on your VDS.

## How It Works

1. **Authentication**: The client automatically handles LinguaLeo login using your credentials. Cookies are cached in `lingualeo_cookies.json` and refreshed when they expire.

2. **Duplicate Check**: Before adding a word, the bot queries the LinguaLeo API to check if the word already exists in your dictionary. If found, the word is skipped to prevent duplicates.

3. **Translation Selection**:
   - If you provide a translation hint, the script finds the closest match from LinguaLeo's suggestions
   - If no hint is provided, it uses the first suggestion automatically

4. **Word Addition**: Selected translations are added to your LinguaLeo dictionary via the API.

## Troubleshooting

### Bot not responding
- Check that `TELEGRAM_TOKEN` is set correctly in `.env`
- Verify the bot is running and not crashed (check logs)

### Authentication errors
- Ensure `LINGUALEO_EMAIL` and `LINGUALEO_PASSWORD` are correct
- Delete `lingualeo_cookies.json` to force a fresh login
- Check that your LinguaLeo account is active

### Import script fails
- Verify the JSON file format is correct
- Check file path is correct (use absolute paths if needed)
- Ensure you have write permissions for the cookie cache file

## Development

### Project Setup

This project uses [uv](https://github.com/astral-sh/uv) for dependency management:

```bash
# Install dependencies
uv sync

# Run the bot
uv run python bot.py
```

### Adding Dependencies

```bash
# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
