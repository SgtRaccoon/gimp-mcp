#!/usr/bin/env python3
# GIMP MCP Server Script
# Provides an MCP interface to control GIMP via a socket connection.

from mcp.server.fastmcp import FastMCP, Context  # Adjust based on your MCP library
import socket
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GimpMCPServer")

class GimpConnection:
    def __init__(self, host='localhost', port=9877):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        if self.sock:
            return
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to GIMP at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise ConnectionError("Could not connect to GIMP. Ensure the MCP Server plugin is running.")

    def send_command(self, command_type, params=None):
        if not self.sock:
            self.connect()
        command = {"type": command_type, "params": params or {}}
        try:
            self.sock.sendall(json.dumps(command).encode('utf-8'))
            response = self.sock.recv(1024)
            self.sock = None
            return json.loads(response.decode('utf-8'))
        except Exception as e:
            logger.error(f"Communication error: {e}")
            self.sock = None
            raise Exception(f"Error communicating with GIMP: {e}")

# Global connection
_gimp_connection = None

def get_gimp_connection():
    global _gimp_connection
    if _gimp_connection is None:
        _gimp_connection = GimpConnection()
        _gimp_connection.connect()
    return _gimp_connection

# MCP server
mcp = FastMCP("GimpMCP", description="GIMP integration through MCP")

@mcp.tool()
def call_api(ctx: Context, api_path: str, args: list = [], kwargs: dict = {}) -> str:
    """Call any GIMP 3.0 API method dynamically.

    Parameters:
    - api_path: The path to the API method (e.g., "Gimp.Image.get_by_id"). Available methods are
     comprehensively documented at https://developer.gimp.org/api/3.0/libgimp/
    - args: List of positional arguments
    - kwargs: Dictionary of keyword arguments

    Returns:
    - JSON string of the result or error message
    """
    try:
        conn = get_gimp_connection()
        result = conn.send_command("call_api", {"api_path": api_path, "args": args, "kwargs": kwargs})
        if result["status"] == "success":
            return json.dumps(result["result"])
        else:
            return f"Error: {json.dumps(result["error"])}"
    except Exception as e:
        return f"Error: {e}"

# Specific tools for common operations
@mcp.tool()
def get_images(ctx: Context) -> str:
    """List all open images in GIMP.

    Returns:
    - JSON string of image IDs and names
    """
    return call_api(ctx, "Gimp.get_images")

@mcp.tool()
def get_image_info(ctx: Context, image_id: int) -> str:
    """Get information about a specific image.

    Parameters:
    - image_id: The ID of the image

    Returns:
    - JSON string of image details
    """
    image = call_api(ctx, "Gimp.Image.get_by_id", args=[image_id])
    if "Error" in image:
        return image
    image_obj = json.loads(image)
    info = {
        "width": call_api(ctx, "Gimp.Image.get_width", args=[image_obj["id"]]),
        "height": call_api(ctx, "Gimp.Image.get_height", args=[image_obj["id"]]),
        "layers": call_api(ctx, "Gimp.Image.get_layers", args=[image_obj["id"]])
    }
    return json.dumps(info)

@mcp.tool()
def apply_gaussian_blur(ctx: Context, image_id: int, radius: float = 5.0) -> str:
    """Apply Gaussian blur to an image.

    Parameters:
    - image_id: The ID of the image
    - radius: Blur radius

    Returns:
    - Success message or error
    """
    image = call_api(ctx, "Gimp.Image.get_by_id", args=[image_id])
    if "Error" in image:
        return image
    image_obj = json.loads(image)
    drawable = call_api(ctx, "Gimp.Image.get_active_layer", args=[image_obj["id"]])
    if "Error" in drawable:
        return drawable
    drawable_obj = json.loads(drawable)
    result = call_api(ctx, "Gimp.get_pdb.run_procedure", 
                     args=["plug-in-gauss", image_obj["id"], drawable_obj["id"], radius, radius, 0])
    if "Error" in result:
        return result
    call_api(ctx, "Gimp.displays_flush")
    return "Applied Gaussian blur successfully"

def main():
    mcp.run()

if __name__ == "__main__":
    main()