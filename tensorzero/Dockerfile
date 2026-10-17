# TensorZero sidecar container
FROM tensorzero/gateway:latest

# Copy gateway routing and model configuration
COPY tensorzero.toml /app/config/tensorzero.toml

EXPOSE 3000

CMD ["--config-file", "/app/config/tensorzero.toml"]
