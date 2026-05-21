# TLS certificates for nginx

Place files here before `docker compose up`:

- `fullchain.pem` — certificate (+ chain)
- `privkey.pem` — private key

## Self-signed (local dev only)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout privkey.pem -out fullchain.pem \
  -subj "/CN=localhost"
```

Production: use Let's Encrypt or your CA.
