import pytest
from app.kubernetes_mcp_server import KubernetesMCPServer

def test_server_initialization():
    """
    Tests that the KubernetesMCPServer initializes without errors.
    Note: This is a basic test and does not connect to a real cluster.
    """
    server = KubernetesMCPServer(kubeconfig_path="/tmp/fake-kubeconfig")
    assert server is not None
    assert server.mcp.name == "kubernetes-mcp"

def test_placeholder():
    """A simple placeholder test that always passes."""
    assert True
