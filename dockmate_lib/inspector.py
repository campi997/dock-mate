import subprocess
import json

def inspect_image(image_name):
    """Pull an image and inspect its metadata for ports, volumes, and envs."""
    # Pull silently
    subprocess.run(f"docker pull {image_name}", shell=True, capture_output=True)
    
    result = subprocess.run(f"docker inspect {image_name}", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return None
        
    try:
        data = json.loads(result.stdout)
        if not data:
            return None
            
        config = data[0].get("Config", {})
        
        # Parse exposed ports
        ports = []
        exposed = config.get("ExposedPorts", {})
        for port_proto in exposed.keys():
            port = port_proto.split("/")[0]
            ports.append(f"{port}:{port}")
            
        # Parse volumes
        volumes = []
        vols = config.get("Volumes", {})
        if vols:
            for v in vols.keys():
                host_dir = "./" + v.strip("/").split("/")[-1]
                volumes.append(f"{host_dir}:{v}")
                
        # Heuristics for undeclared host bind mounts
        img_lower = image_name.lower()
        if any(tool in img_lower for tool in ["yacht", "dockhand", "portainer", "watchtower", "dozzle", "dockge"]):
            volumes.append("/var/run/docker.sock:/var/run/docker.sock")
                
        return {
            "ports": ports,
            "volumes": volumes,
            "env": config.get("Env", [])
        }
    except Exception:
        return None
