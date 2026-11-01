import os
import re
import json
import urllib.request
import urllib.error
from . import ui

def fetch_url(url, headers=None):
    if headers is None:
        headers = {'User-Agent': 'DockMate-Fetcher'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except Exception:
        return None

def get_github_repo_from_dockerhub(docker_image):
    """Try to find the source GitHub repository from Docker Hub metadata."""
    if not docker_image or '/' not in docker_image:
        return None
    
    # Ignore ghcr.io images for the Docker Hub check, parse directly instead
    if docker_image.startswith('ghcr.io/'):
        parts = docker_image.replace('ghcr.io/', '').split('/')
        if len(parts) >= 2:
            repo = f"{parts[0]}/{parts[1].split(':')[0]}"
            return repo
        return None
        
    namespace, name = docker_image.split('/', 1)
    name = name.split(':')[0]
    
    url = f"https://hub.docker.com/v2/repositories/{namespace}/{name}/"
    data_str = fetch_url(url)
    if not data_str:
        return None
    
    try:
        data = json.loads(data_str)
        # Check source_url or similar fields, or maybe full_description
        # Actually Docker Hub API returns a 'source' field if linked to Github, or sometimes nothing.
        # Wait, if not present in the standard API response, maybe search the description?
        pass
    except Exception:
        pass
        
    # We can also check https://hub.docker.com/api/build/v1/source/?image=namespace/name
    # Or just extract from full_description if github.com is mentioned
    return None

def extract_github_repo_from_text(text):
    if not text:
        return None
    match = re.search(r'github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)', text)
    if match:
        repo = match.group(1).rstrip('.git').rstrip('/')
        return repo
    return None

def generate_compose(container_name, docker_image=None):
    """
    Fetch a docker-compose.yml file deterministically from GitHub.
    Replaces the old LLM-based logic.
    """
    ui.info(f"Finding official compose configuration for '{container_name}'...")
    
    github_repo = None
    
    # 1. Check ghcr.io
    if docker_image and docker_image.startswith('ghcr.io/'):
        parts = docker_image.replace('ghcr.io/', '').split('/')
        if len(parts) >= 2:
            github_repo = f"{parts[0]}/{parts[1].split(':')[0]}"
    
    # 2. Check Docker Hub for github links
    if not github_repo and docker_image and '/' in docker_image:
        namespace, name = docker_image.split('/', 1)
        name = name.split(':')[0]
        url = f"https://hub.docker.com/v2/repositories/{namespace}/{name}/"
        data_str = fetch_url(url)
        if data_str:
            try:
                data = json.loads(data_str)
                # First check if there's an explicit github link
                full_desc = data.get('full_description', '') or ''
                desc = data.get('description', '') or ''
                github_repo = extract_github_repo_from_text(full_desc)
                if not github_repo:
                    github_repo = extract_github_repo_from_text(desc)
            except Exception:
                pass

    # 3. GitHub search API fallback
    if not github_repo:
        search_url = f"https://api.github.com/search/repositories?q={container_name}&per_page=1"
        data_str = fetch_url(search_url)
        if data_str:
            try:
                data = json.loads(data_str)
                if data.get('items') and len(data['items']) > 0:
                    github_repo = data['items'][0]['full_name']
            except Exception:
                pass

    if not github_repo:
        return None
        
    ui.info(f"Target GitHub repository identified: {github_repo}")

    # 4. Fetch known compose file paths directly
    raw_base = f"https://raw.githubusercontent.com/{github_repo}/HEAD"
    paths_to_try = [
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yaml",
        "docker/docker-compose.yml",
        "docker/docker-compose.yaml",
        "deploy/docker-compose.yml",
        "deploy/docker-compose.yaml"
    ]
    
    for path in paths_to_try:
        url = f"{raw_base}/{path}"
        content = fetch_url(url)
        if content and 'services:' in content:
            ui.success(f"Found compose file at {path}")
            return content

    # 5. Fallback: Fetch README and regex out a fenced code block containing services:
    readme_url = f"{raw_base}/README.md"
    readme_content = fetch_url(readme_url)
    if readme_content:
        # Regex to find yaml code blocks containing services:
        matches = re.findall(r'```(?:yaml|yml)?\s*\n(.*?services:.*?)```', readme_content, re.DOTALL)
        if matches:
            for match in matches:
                # Basic validation
                if 'services:' in match:
                    ui.success("Extracted compose configuration from README.md")
                    return match.strip()

    return None
