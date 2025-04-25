# Installation Guide

This document provides a comprehensive installation guide for setting up the project using both Docker and a manual Python environment. Follow the appropriate section based on your preference.

## Table of Contents
1. [Docker Installation](#docker-installation)
2. [Manual Installation](#manual-installation)

## Docker Installation

To set up the project using Docker, follow these steps:

1. **Prerequisites**:
   - Install Docker: [Docker Installation Guide](https://docs.docker.com/get-docker/)
   - For GPU support:
     - NVIDIA GPUs: [NVIDIA Container Toolkit Installation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
     - On Windows, Docker will likely use WSL2; make sure to follow the steps above to enable GPU support on the distro docker is using. You can see whether it's the defaul distro in Docker Desktop `Settings -> Resources -> Advanced` (settings is the little cog wheel icon on the top right of the GUI)

2. **Run Ollama Container**:
   Choose the appropriate command based on your hardware:

   * CPU only:
   ```bash
   docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
   ```

   * For NVIDIA GPU support:
   ```bash
   docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
   ```

   * For AMD GPU support:
   ```bash
   docker run -d --device /dev/kfd --device /dev/dri -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama:rocm
   ```

   For more details, refer to the [Ollama Docker documentation](https://github.com/ollama/ollama/blob/main/docs/docker.md).

4. **Hatchling Configuration**:
   Modify the variables as you prefer in the `root/docker/.env` file:
   ```
   OLLAMA_HOST_API=http://localhost:11434/api
   DEFAULT_MODEL=mistral-small3.1
   MCP_SERVER_PATH=mcp_utils/servers/arithmetic.py
   NETWORK_MODE=host
   LOG_LEVEL=INFO
   LOG_FILE=__temp__/app.log
   ```

5. **Accessing the Application**:
   Once the container is running, you can access the API at `http://localhost:11434/api`.

## Manual Installation

If you prefer not to use Docker, you can set up the project manually by following these steps:

1. **Install Ollama**:
   Download and install Ollama by following the instructions in the official documentation:
   - [Windows Installation Guide](https://github.com/ollama/ollama/blob/main/docs/windows.md)
   - [Linux Installation Guide](https://github.com/ollama/ollama/blob/main/docs/linux.md)

2. **Set Up the Python Environment**:
   Create a virtual environment and install the required dependencies. You can do this by running:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

3. **Pull the Model**:
   Use the Ollama CLI to pull the desired model:
   ```
   ollama pull mistral-small3.1
   ```

4. **Run the Model**:
   Start the model using the following command:
   ```
   ollama run mistral-small3.1 --host localhost --port 11434
   ```

## Conclusion

You can choose either the Docker or manual installation method based on your preference. For further details on running the code and available parameters, refer to the respective documentation files.