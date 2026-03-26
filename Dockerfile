# Build image
docker build -t ethiotelecom/health-check:latest .

# Run container
docker run -d \
  --name health-check \
  --restart always \
  --env-file .env \
  -v /etc/ssh/keys:/run/secrets/ssh_keys:ro \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/logs:/app/logs \
  ethiotelecom/health-check:latest \
  python main.py --scheduler

# View logs
docker logs -f health-check

# Stop
docker stop health-check