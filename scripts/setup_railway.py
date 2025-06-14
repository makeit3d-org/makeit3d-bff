#!/usr/bin/env python3
"""
Railway Setup Script for MakeIT3D BFF
Automates the creation of Railway project with all required services
"""

import subprocess
import sys
import os
import json
import time
from typing import Dict, List

class RailwaySetup:
    def __init__(self):
        self.project_name = "makeit3d-bff"
        self.services = {
            "main": "makeit3d-bff",
            "redis": "Redis",
            "worker_default": "celery-worker-default", 
            "worker_tripo": "celery-worker-tripo"
        }
        
    def run_command(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a shell command and return the result"""
        print(f"🔧 Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
            if result.stdout:
                print(f"✅ Output: {result.stdout.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            print(f"❌ Error: {e.stderr}")
            if check:
                raise
            return e
    
    def check_prerequisites(self):
        """Check if Railway CLI is installed and user is logged in"""
        print("🔍 Checking prerequisites...")
        
        # Check Railway CLI
        try:
            self.run_command(["railway", "--version"])
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Railway CLI not found. Install it with:")
            print("npm install -g @railway/cli")
            sys.exit(1)
        
        # Check if logged in
        try:
            self.run_command(["railway", "whoami"])
        except subprocess.CalledProcessError:
            print("❌ Please login to Railway first:")
            print("railway login")
            sys.exit(1)
    
    def load_environment_variables(self) -> Dict[str, str]:
        """Load environment variables from file"""
        env_file = "scripts/.env.railway.local"
        if not os.path.exists(env_file):
            print(f"❌ Environment file not found: {env_file}")
            print("Please copy scripts/env.railway.template to scripts/.env.railway.local and fill in your values")
            sys.exit(1)
        
        env_vars = {}
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
        
        return env_vars
    
    def create_project(self):
        """Create new Railway project"""
        print("📦 Creating Railway project...")
        self.run_command(["railway", "init", "--name", self.project_name])
        
        # Get project info
        result = self.run_command(["railway", "status", "--json"])
        project_info = json.loads(result.stdout)
        print(f"✅ Created project: {project_info['project']['id']}")
        return project_info
    
    def add_redis(self):
        """Add Redis service"""
        print("🔴 Adding Redis service...")
        self.run_command(["railway", "add", "--service", "redis"])
    
    def deploy_main_service(self):
        """Deploy main FastAPI service"""
        print("🐍 Deploying main FastAPI service...")
        self.run_command(["railway", "up"])
    
    def create_worker_service(self, service_name: str, start_command: str, env_vars: Dict[str, str]):
        """Create and configure a Celery worker service"""
        print(f"👷 Creating {service_name}...")
        
        # Create service
        self.run_command(["railway", "service", "create", service_name])
        self.run_command(["railway", "service", "use", service_name])
        
        # Set environment variables
        print(f"🔧 Setting environment variables for {service_name}...")
        for key, value in env_vars.items():
            self.run_command(["railway", "variables", "set", f"{key}={value}"])
        
        # Set start command
        print(f"⚙️ Setting start command for {service_name}...")
        self.run_command(["railway", "service", "settings", "--start-command", start_command])
        
        # Connect to GitHub repo
        if env_vars.get("GITHUB_REPO"):
            self.run_command(["railway", "service", "connect", "--repo", env_vars["GITHUB_REPO"]])
        
        # Deploy
        print(f"🚀 Deploying {service_name}...")
        self.run_command(["railway", "up"])
    
    def setup_main_service_variables(self, env_vars: Dict[str, str]):
        """Set environment variables for main service"""
        print("🔧 Configuring main FastAPI service...")
        self.run_command(["railway", "service", "use", self.services["main"]])
        
        for key, value in env_vars.items():
            if key != "GITHUB_REPO":  # Skip non-env vars
                self.run_command(["railway", "variables", "set", f"{key}={value}"])
    
    def generate_domain(self):
        """Generate domain for main service"""
        print("🌐 Generating domain...")
        self.run_command(["railway", "service", "use", self.services["main"]])
        self.run_command(["railway", "domain", "generate"])
    
    def run_setup(self):
        """Run the complete setup process"""
        print("🚀 Starting MakeIT3D BFF Railway setup...")
        
        # Check prerequisites
        self.check_prerequisites()
        
        # Load environment variables
        env_vars = self.load_environment_variables()
        
        # Create project
        self.create_project()
        
        # Add Redis
        self.add_redis()
        
        # Deploy main service
        self.deploy_main_service()
        
        # Wait for main service to be ready
        print("⏳ Waiting for main service to initialize...")
        time.sleep(10)
        
        # Create default worker
        self.create_worker_service(
            self.services["worker_default"],
            "celery -A celery_worker worker -Q default -l info --concurrency=2",
            env_vars
        )
        
        # Create Tripo worker
        self.create_worker_service(
            self.services["worker_tripo"],
            "celery -A celery_worker worker -Q tripo_other,tripo_refine -l info --concurrency=1",
            env_vars
        )
        
        # Configure main service variables
        self.setup_main_service_variables(env_vars)
        
        # Generate domain
        self.generate_domain()
        
        print("✅ Railway deployment complete!")
        print("\n📋 Services created:")
        print("  - makeit3d-bff (FastAPI main service)")
        print("  - Redis (message broker & backend)")
        print("  - celery-worker-default (image generation tasks)")
        print("  - celery-worker-tripo (3D model tasks)")
        print("\n🔗 Check your Railway dashboard: https://railway.app/dashboard")
        print("🚀 Your API will be available at the generated domain")

if __name__ == "__main__":
    setup = RailwaySetup()
    setup.run_setup() 