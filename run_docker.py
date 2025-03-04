#!/usr/bin/env python
"""
Simple script to build and run Archon Docker containers.
"""

import os
import subprocess
import platform
import time
import socket
from pathlib import Path

def run_command(command, cwd=None):
    """Run a command and print output in real-time."""
    print(f"Running: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False,  
        cwd=cwd
    )
    
    for line in process.stdout:
        try:
            decoded_line = line.decode('utf-8', errors='replace')
            print(decoded_line.strip())
        except Exception as e:
            print(f"Error processing output: {e}")
    
    process.wait()
    return process.returncode

def check_docker():
    """Check if Docker is installed and running."""
    try:
        subprocess.run(
            ["docker", "--version"], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        # Also check if Docker daemon is running
        subprocess.run(
            ["docker", "info"], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        return True
    except subprocess.SubprocessError:
        print("Error: Docker is not running. Please start Docker Desktop or Docker service.")
        return False
    except FileNotFoundError:
        print("Error: Docker is not installed or not in PATH")
        return False

def detect_windows_docker_environment():
    """Detect if running Docker Desktop or Docker Toolbox on Windows."""
    if platform.system() != "Windows":
        return "standard"
    
    try:
        # Check if using Docker Desktop (WSL2)
        result = subprocess.run(
            ["docker", "info"], 
            check=True, 
            capture_output=True, 
            text=True
        )
        if "wsl" in result.stdout.lower() or "microsoft" in result.stdout.lower():
            return "docker-desktop"
        
        # Check for Docker Toolbox (VirtualBox)
        if "virtualbox" in result.stdout.lower() or "docker machine" in result.stdout.lower():
            return "docker-toolbox"
            
        # Default to Docker Desktop as it's now more common
        return "docker-desktop"
    except:
        # If we can't determine, default to Docker Desktop
        return "docker-desktop"

def is_port_available(port):
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

def main():
    """Main function to build and run Archon containers."""
    # Check if Docker is available
    if not check_docker():
        return 1
    
    # Detect Docker environment on Windows
    docker_env = detect_windows_docker_environment()
    print(f"Detected Docker environment: {docker_env}")
    
    # Check if required ports are available
    required_ports = [8501, 8100]
    unavailable_ports = [port for port in required_ports if not is_port_available(port)]
    if unavailable_ports:
        print(f"Error: The following ports are already in use: {unavailable_ports}")
        print("Please stop the services using these ports or modify the port mappings.")
        return 1
    
    # Get the base directory
    base_dir = Path(__file__).parent.absolute()
    
    # Check for .env file
    env_file = base_dir / ".env"
    env_args = []
    if env_file.exists():
        print(f"Using environment file: {env_file}")
        env_args = ["--env-file", str(env_file)]
    else:
        print("No .env file found. Continuing without environment variables.")
    
    # Build the MCP container
    print("\n=== Building Archon MCP container ===")
    mcp_dir = base_dir / "mcp"
    if run_command(["docker", "build", "-t", "archon-mcp:latest", "."], cwd=mcp_dir) != 0:
        print("Error building MCP container")
        return 1
    
    # Build the main Archon container
    print("\n=== Building main Archon container ===")
    if run_command(["docker", "build", "-t", "archon:latest", "."], cwd=base_dir) != 0:
        print("Error building main Archon container")
        return 1
    
    # Check if the container is already running
    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "--filter", "name=archon-container"],
            check=True,
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            print("\n=== Stopping existing Archon container ===")
            run_command(["docker", "stop", "archon-container"])
            run_command(["docker", "rm", "archon-container"])
    except subprocess.SubprocessError:
        pass
    
    # Run the Archon container
    print("\n=== Starting Archon container ===")
    cmd = [
        "docker", "run", "-d",
        "--name", "archon-container",
        "-p", "8501:8501",
        "-p", "8100:8100",
    ]
    
    # Add host configuration based on Docker environment
    if docker_env == "docker-desktop":
        cmd.extend(["--add-host", "host.docker.internal:host-gateway"])
    elif docker_env == "docker-toolbox":
        # Docker Toolbox requires different approach for host access
        print("Note: For Docker Toolbox, you may need to use the VM's IP address instead of localhost")
    
    # Add environment variables if .env exists
    if env_args:
        cmd.extend(env_args)
    
    # Add image name
    cmd.append("archon:latest")
    
    if run_command(cmd) != 0:
        print("Error starting Archon container")
        return 1
    
    # Wait a moment for the container to start
    time.sleep(2)
    
    # Print success message
    print("\n=== Archon is now running! ===")
    
    # Show appropriate access URLs based on Docker environment
    if docker_env == "docker-toolbox":
        print("-> Using Docker Toolbox:")
        print("   To access the Streamlit UI, you need to use the Docker VM's IP address.")
        print("   Run 'docker-machine ip default' to get this IP, then access:")
        print("   http://<docker-machine-ip>:8501")
    else:
        print("-> Access the Streamlit UI at: http://localhost:8501")
    
    print("-> MCP container is ready to use - see the MCP tab in the UI.")
    print("\nTo stop Archon, run: docker stop archon-container && docker rm archon-container")
    
    return 0

if __name__ == "__main__":
    exit(main())
