FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY app/requirements .

# Install dependencies
RUN pip install --no-cache-dir -r requirements

# Copy application code
COPY app/ .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Command to run the application
ENTRYPOINT ["python", "kubernetes_mcp_server.py"]

CMD []
