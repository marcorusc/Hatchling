FROM python:3.12-slim

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Create working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install pip requirements
RUN python -m pip install -r requirements.txt

# Install the package
RUN pip install -e /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
RUN adduser -u 5678 --disabled-password --gecos "" appuser

# Create __logs__ directory and set permissions
RUN mkdir -p /app/__logs__ && chown -R appuser:appuser /app && chmod -R 775 /app/__logs__

USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["python", "app.py"]
