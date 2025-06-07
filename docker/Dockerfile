FROM python:3.12-slim

# Install git and gosu (for safe user switching)
RUN apt-get update && apt-get install -y git gosu && rm -rf /var/lib/apt/lists/*

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Copy the current directory contents into the container at /app
COPY . /app

# Copy the entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set working directory
WORKDIR /app

# Install the package
RUN pip install -e .

# Use the entrypoint script (runs as root initially to handle permissions)
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["hatchling"]
