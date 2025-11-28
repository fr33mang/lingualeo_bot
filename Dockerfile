FROM python:3.14-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY lingualeo/ ./lingualeo/
COPY bot.py import_words.py ./

# Install dependencies
RUN uv sync --frozen

# Create directory for cookie cache with proper permissions
RUN mkdir -p /app/data && chmod 777 /app/data

# Set environment to production
ENV PYTHONUNBUFFERED=1

# Default to running the bot
CMD ["uv", "run", "python", "bot.py"]
