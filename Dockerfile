# Build the React app, then ship it inside the Python image that serves the API.
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY run.py .
COPY --from=web /web/dist frontend/dist

ENV CRMS_ENV=production
RUN useradd --system crms && mkdir data && chown crms data
USER crms

# the proxy flags make the sign-in lockout see the visitor's address instead of the host's proxy
CMD ["sh", "-c", "uvicorn run:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
