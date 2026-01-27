# Use an official Python runtime as a parent image
FROM python:3.14-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY ./app/ /app/

# Install any needed packages specified in requirements
RUN pip install --no-cache-dir -r requirements

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV PYTHONPATH=/app

# Run kubernetes_mcp_server.py when the container launches
ENTRYPOINT ["/usr/bin/env", "python3", "kubernetes_mcp_server.py"]
# CMD allows passing additional arguments to the ENTRYPOINT
CMD []
