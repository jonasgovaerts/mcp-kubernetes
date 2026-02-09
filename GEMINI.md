# Project Overview

This project is a Kubernetes agent based on FastMCP. It provides a comprehensive set of tools to inspect and manage a Kubernetes cluster. The agent exposes an HTTP endpoint that allows AI assistants to query cluster status, resources, logs, and more.

## Main Technologies

*   **Python 3.12**
*   **FastMCP:** A framework for building agents that can be controlled by AI assistants.
*   **Kubernetes Python Client:** For interacting with the Kubernetes API.
*   **ujson:** For fast JSON parsing.
*   **pytest:** For testing.

## Architecture

The project is structured as a single Python application in the `app` directory.

*   `kubernetes_mcp_server.py`: This is the main file that starts the FastMCP server. It defines the `KubernetesMCPServer` class, which contains the logic for querying the Kubernetes API. The tools exposed by the agent are also registered in this file.
*   `cni_inspector.py`: This module provides a specialized tool for inspecting the Whereabouts CNI for IP address management issues.
*   `k8s_client.py`: This seems to be a client for the server.

# Building and Running

## Installation

The project uses Pipenv for dependency management. To install the dependencies, run:

```bash
pipenv install
```

## Running the Server

To run the Kubernetes MCP server, execute the following command:

```bash
python app/kubernetes_mcp_server.py --host 0.0.0.0 --port 8000
```

The server will be available at `http://0.0.0.0:8000/mcp`.

## Testing

The project uses pytest for testing. To run the tests, execute the following command:

```bash
pytest app/
```

# Development Conventions

The code follows the PEP 8 style guide. The project uses `unittest.mock` for mocking in tests.
