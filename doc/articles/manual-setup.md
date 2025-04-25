# Manual Installation Guide

This document outlines the steps required to manually install and run the project without using Docker. Follow the instructions below to set up the Ollama environment and configure your Python environment to run the existing code.

## Prerequisites

Before you begin, ensure that you have the following installed on your system:

- Python 3.7 or higher
- pip (Python package installer)
- Git (for cloning the repository)

## Step 1: Install Ollama

To set up Ollama manually, follow these steps:

1. **Download Ollama**: Visit the [Ollama GitHub repository](https://github.com/ollama/ollama) and follow the instructions for your operating system.
2. **Pull a Model**: After installing Ollama, you can pull a model using the following command:
   ```
   ollama pull mistral-small3.1
   ```
3. **Run the Model**: Start the model at the default address and port using:
   ```
   ollama run mistral-small3.1
   ```
   By default, this will run the model at `http://localhost:11434`.

## Step 2: Set Up Python Environment

To run the existing code, you need to set up a Python environment:

1. **Clone the Repository**: Use Git to clone the project repository:
   ```
   git clone <repository-url>
   cd <repository-directory>
   ```
2. **Create a Virtual Environment** (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. **Install Required Packages**: Install the necessary Python packages using pip:
   ```
   pip install -r requirements.txt
   ```

## Step 3: Running the Code

Once you have set up the Ollama environment and your Python environment, you can run your code. Make sure that the Ollama model is running before executing your Python scripts.

## Additional Resources

- For Windows users, refer to the [Windows Installation Guide](https://github.com/ollama/ollama/blob/main/docs/windows.md) for more detailed instructions.
  - Note: Be aware of potential RAM issues when using Docker on Windows. Refer to this [GitHub thread](https://github.com/docker/for-win/issues/12944) for more information.
  
- For Linux users, check the [Linux Installation Guide](https://github.com/ollama/ollama/blob/main/docs/linux.md) for specific instructions.

## Conclusion

By following the steps outlined in this guide, you should be able to manually install and run the project without Docker. If you encounter any issues, please refer to the relevant documentation or seek help from the community.