FROM python:3.8-slim

ADD LICENSE .
ADD README.md .
ADD bot_nanny bot_nanny
ADD requirements.txt .

# Install dependencies
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Run bot_nanny module
CMD ["python3", "-m", "bot_nanny", "--logpath", "/var/log", "--config", "/etc/bot_nanny/live.toml"]
