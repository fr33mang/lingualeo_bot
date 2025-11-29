# LinguaLeo Bot

Utilities and bots for importing words into LinguaLeo vocabulary.

## Features

- **Telegram Bot**: Add Spanish words to your LinguaLeo dictionary via Telegram chat
- **Automatic Authentication**: Handles login and cookie caching automatically
- **Smart Translation Matching**: Automatically selects the best translation from LinguaLeo suggestions (80% similarity threshold)
- **Multiple Translations Support**: Add different translations to the same word
- **Custom Translations**: Add your own translations even if they're not in LinguaLeo's suggestions
- **Smart Duplicate Prevention**: Prevents duplicate word-translation pairs while allowing new translations for existing words

## Project Structure

```
.
├── bot.py                 # Telegram bot entry point
├── lingualeo/            # Reusable LinguaLeo client module
│   ├── __init__.py
│   └── client.py
├── .github/              # GitHub Actions workflows
│   └── workflows/
├── .pre-commit-config.yaml  # Pre-commit hooks configuration
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile            # Docker image definition
├── pyproject.toml        # Project dependencies (uv)
└── README.md             # This file
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
TELEGRAM_AUTHORIZED_USER_ID=your_telegram_user_id_here

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

**Single word (auto-select first translation):**
```
palabra
```

**Single word with translation hint:**
```
palabra — перевод
```
or
```
palabra - перевод
```

**Bulk import (multiple words, one per line):**
```
palabra1 — перевод1
palabra2 — перевод2
palabra3
```

#### Translation Logic

The bot intelligently handles different scenarios:

**1. New word without translation hint:**
- Uses the first translation from LinguaLeo's suggestions

**2. New word with translation hint:**
- Searches for matching translation in LinguaLeo's suggestions (80% similarity threshold)
- If found: uses the matching translation
- If not found: creates a custom translation with your hint

**3. Existing word without translation hint:**
- Reports that the word already exists and shows current translations

**4. Existing word with translation hint:**
- If the translation already exists: reports that the word-translation pair already exists
- If it's a new translation: adds the new translation to the existing word

**Examples:**

```
# First time adding "medico"
medico
→ Adds with first LinguaLeo suggestion (e.g., "доктор")

# Adding a different translation to "medico"
medico - врач
→ Adds "врач" as a new translation (if not already present)

# Trying to add same translation again
medico - доктор
→ Reports: "Слово 'medico' with translation 'доктор' already exists"

# Adding custom translation not in LinguaLeo's suggestions
palabra - мой перевод
→ Creates custom translation "мой перевод"
```

**Summary in bulk imports:**
- **Добавлено** (Added): Successfully added word-translation pairs
- **Уже есть** (Already exists): Word-translation pairs that were already in your dictionary
- **Ошибки** (Errors): Failed to add due to errors

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

2. **Word Existence Check**: Before adding a word, the bot queries the LinguaLeo API to check if the word already exists and retrieves any existing translations.

3. **Translation Selection**:
   - **With hint**: Searches for matching translation in LinguaLeo's suggestions using fuzzy matching (80% similarity threshold)
   - **Without hint**: Uses the first suggestion from LinguaLeo automatically
   - **Custom translations**: If your hint doesn't match any suggestion (< 80% similarity), creates a custom translation

4. **Duplicate Prevention**:
   - Prevents adding the same word-translation pair twice
   - Allows adding different translations to existing words
   - Shows existing translations when word already exists

5. **Word Addition**: Selected translations are added to your LinguaLeo dictionary via the API.

## Troubleshooting

### Bot not responding
- Check that `TELEGRAM_TOKEN` is set correctly in `.env`
- Verify the bot is running and not crashed (check logs)

### Authentication errors
- Ensure `LINGUALEO_EMAIL` and `LINGUALEO_PASSWORD` are correct
- Delete `lingualeo_cookies.json` to force a fresh login
- Check that your LinguaLeo account is active

### Cookie cache issues
- Ensure you have write permissions for the cookie cache file (`lingualeo_cookies.json`)
- Delete `lingualeo_cookies.json` to force a fresh login if authentication fails

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

### Running Tests

The project includes comprehensive test coverage:

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_client.py

# Run with coverage report
uv run pytest --cov=lingualeo --cov-report=html
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
