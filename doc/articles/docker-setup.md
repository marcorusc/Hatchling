# Docker Setup Instructions

This document provides instructions on how to set up and run the project using Docker.

## Prerequisites

- Docker Desktop: [Install Docker Desktop](https://docs.docker.com/get-docker/)
- WSL2 (for Windows users)
- GPU Support (Optional):
  - NVIDIA GPUs: [NVIDIA Container Toolkit Installation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  - AMD GPUs: See instructions below

## Windows Setup with Docker Desktop

1. **Install Docker Desktop**:
   - Download and install Docker Desktop
   - Ensure Docker is configured to use WSL2

2. **Configure WSL Integration**:
   - In Docker Desktop, go to `Settings` > `Resources` > `WSL Integration`
   - Either enable integration with your default WSL distro or select a specific one
   - Click "Apply & Restart" if you make changes

3. **Setup GPU Support (Optional but recommended)**:
   - Connect to your WSL distro that Docker is integrated with
   - For NVIDIA GPU support, run the following commands:
     ```bash
     # Add NVIDIA repository keys
     curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
     
     # Add NVIDIA repository
     curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
     
     # Update package lists
     sudo apt-get update
     
     # Install NVIDIA container toolkit
     sudo apt-get install -y nvidia-container-toolkit
     
     # Configure Docker runtime
     sudo nvidia-ctk runtime configure --runtime=docker
     ```
   - (For AMD GPU support, nothing to do at this stage)
   - Close your WSL terminal
   - Restart Docker Desktop (click on the three vertical dots icon, then `Restart`)

4. **Pull Ollama Image**:
   - Open a terminal in Docker Desktop (using the `Terminal` button)
   - Run: `docker pull ollama/ollama`
   - If the Ollama image doesn't appear in the `Images` tab, try restarting Docker Desktop

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

To verify that GPU support is working correctly:
1. Go to the `Containers` tab in Docker Desktop
2. Click on your Ollama container
3. Check the logs - you should see a message indicating GPU detection, similar to:
```
msg="inference compute" id=GPU-a826c853-a49e-a55d-da4d-804bfe10cdcf library=cuda variant=v12 compute=8.6 driver=12.7 name="NVIDIA GeForce RTX 3070 Laptop GPU" total="8.0 GiB" available="7.0 GiB"
```

For more detailed instructions and options, refer to the [official Ollama Docker documentation](https://github.com/ollama/ollama/blob/main/docs/docker.md).

## Running Hatchling

1. **Clone the Repository**:
```bash
git clone <repository-url>
cd <repository-directory>
```

2. **Configure Environment**:
   - Navigate to the `docker` directory within the project
   - Modify the `.env` file if needed:
     - You may need to adjust `OLLAMA_HOST_API` to match where your Ollama container is hosted
     - You can change `DEFAULT_MODEL` to a specific LLM model (see [Ollama Models Library](https://ollama.com/search))
     - Choose a model appropriate for your hardware resources

3. **Start Ollama**:
   - Start the Ollama container via Docker Desktop (press the "play" button)

4. **Start Hatchling**:
```bash
# From the docker directory in your project
docker-compose run --rm hatchling
```

The `--rm` flag ensures the container is removed when you exit the application.

**Notes**:
- The first time you run this command, it will build the image (typically takes 15-30 seconds)
- If Hatchling successfully connects to Ollama, it will download the specified LLM model
- Model download times vary based on the model size

## Additional Resources

- [Ollama Models Library](https://ollama.com/library)
- [Docker Documentation](https://docs.docker.com/)