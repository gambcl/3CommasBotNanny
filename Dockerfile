FROM python:3.8-slim

WORKDIR /

COPY LICENSE .
COPY README.md .
COPY bot_nanny bot_nanny
COPY requirements.txt .

# Install dependencies

# hadolint ignore=DL3013
RUN python -m pip install --no-cache-dir --upgrade pip
# hadolint ignore=DL3059
RUN pip install --no-cache-dir -r requirements.txt

# Run bot_nanny module
CMD ["python3", "-m", "bot_nanny", "--logpath", "/var/log", "--config", "/etc/bot_nanny/live.toml"]
