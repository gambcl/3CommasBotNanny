FROM python:3.8-slim

WORKDIR /

COPY LICENSE .
COPY README.md .
COPY botnanny botnanny
COPY requirements.txt .

# Install dependencies

# hadolint ignore=DL3013
RUN python -m pip install --no-cache-dir --upgrade pip
# hadolint ignore=DL3059
RUN pip install --no-cache-dir -r requirements.txt

# Run botnanny module
CMD ["python3", "-m", "botnanny", "--logpath", "/var/log", "--config", "/etc/botnanny/live.toml"]
