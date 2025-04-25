# Docker Setup Instructions

This document provides instructions on how to set up and run the project using Docker.

## Prerequisites

- Docker: [Install Docker](https://docs.docker.com/get-docker/)
- GPU Support (Optional):
  - NVIDIA GPUs: [NVIDIA Container Toolkit Installation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  - AMD GPUs: No additional installation required

## Running Ollama with Docker

### Quick Start Commands

Choose the appropriate command based on your hardware:

* **CPU only**:
```bash
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

* **NVIDIA GPU support**:
```bash
docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

* **AMD GPU support**:
```bash
docker run -d --device /dev/kfd --device /dev/dri -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama:rocm
```

* **Run a model**:
```bash
docker exec -it ollama ollama run llama3.2
```

For more detailed instructions and options, refer to the [official Ollama Docker documentation](https://github.com/ollama/ollama/blob/main/docs/docker.md).

## Project Setup

1. **Clone the Repository**:
```bash
git clone <repository-url>
cd <repository-directory>
```

2. **Configure Environment**:
Create a `.env` file with:
```properties
OLLAMA_HOST_API=http://localhost:11434/api
DEFAULT_MODEL=mistral-small3.1
MCP_SERVER_PATH=mcp_utils/servers/arithmetic.py
NETWORK_MODE=host
LOG_LEVEL=INFO
LOG_FILE=__temp__/app.log
```

3. **Start Project Services**:
```bash
docker-compose up
```

## API Access

Once the container is running, you can access the Ollama API at:
```
http://localhost:11434/api
```

## Additional Resources

- [Ollama Models Library](https://ollama.com/library)
- [Docker Documentation](https://docs.docker.com/)