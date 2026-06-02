FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install pipenv to generate requirements.txt
RUN pip install pipenv

# Copy Pipfiles and generate requirements.txt
COPY app/Pipfile app/Pipfile.lock ./
RUN pipenv requirements > requirements.txt

# Install dependencies from the generated file
RUN pip install -r requirements.txt

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
