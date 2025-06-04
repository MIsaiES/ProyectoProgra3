
"""
Nextcloud Connection Program
A simple program to connect to Nextcloud and perform basic file operations
"""

import sys
from urllib.parse import urljoin
import requests
from requests.auth import HTTPBasicAuth
import os
import json
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP()

class NextcloudClient:
    def __init__(self, server_url, username, password):
        """
        Initialize Nextcloud client
        
        Args:
            server_url (str): Your Nextcloud server URL (e.g., 'https://cloud.example.com')
            username (str): Your Nextcloud username
            password (str): Your Nextcloud password or app password
        """
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.webdav_url = f"{self.server_url}/remote.php/dav/files/{username}/"
        self.auth = HTTPBasicAuth(username, password)
        
    def test_connection(self):
        """Test if the connection to Nextcloud is working"""
        try:
            response = requests.get(self.webdav_url, auth=self.auth, timeout=10)
            if response.status_code == 200:
                print("✅ Successfully connected to Nextcloud!")
                return True
            else:
                print(f"❌ Connection failed. Status code: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def list_files(self, path=""):
        """
        List files in a directory
        
        Args:
            path (str): Path to list (empty for root directory)
        """
        url = urljoin(self.webdav_url, path)
        
        # PROPFIND request to get directory listing
        headers = {
            'Depth': '1',
            'Content-Type': 'application/xml'
        }
        
        propfind_xml = '''<?xml version="1.0"?>
        <d:propfind xmlns:d="DAV:">
            <d:prop>
                <d:displayname/>
                <d:getcontentlength/>
                <d:getlastmodified/>
                <d:resourcetype/>
            </d:prop>
        </d:propfind>'''
        
        try:
            response = requests.request(
                'PROPFIND', url, 
                auth=self.auth, 
                headers=headers, 
                data=propfind_xml,
                timeout=30
            )
            
            if response.status_code == 207:  # Multi-Status
                print(f"📁 Contents of /{path}:")
                print("-" * 50)
                
                # Simple parsing - in production, use xml.etree.ElementTree
                lines = response.text.split('\n')
                for line in lines:
                    if '<d:displayname>' in line:
                        name = line.split('<d:displayname>')[1].split('</d:displayname>')[0]
                        if name and name != path.rstrip('/').split('/')[-1]:
                            print(f"  {name}")
                return True
            else:
                print(f"❌ Failed to list files. Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error listing files: {e}")
            return False
    
    def upload_file(self, local_path, remote_path):
        """
        Upload a file to Nextcloud
        
        Args:
            local_path (str): Path to local file
            remote_path (str): Remote path where file should be stored
        """
        if not os.path.exists(local_path):
            print(f"❌ Local file not found: {local_path}")
            return False
        
        url = urljoin(self.webdav_url, remote_path)
        
        try:
            with open(local_path, 'rb') as f:
                response = requests.put(url, auth=self.auth, data=f, timeout=60)
            
            if response.status_code in [201, 204]:  # Created or No Content
                print(f"✅ Successfully uploaded {local_path} to {remote_path}")
                return True
            else:
                print(f"❌ Upload failed. Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Upload error: {e}")
            return False
    
    def download_file(self, remote_path, local_path):
        """
        Download a file from Nextcloud
        
        Args:
            remote_path (str): Path to remote file
            local_path (str): Local path where file should be saved
        """
        url = urljoin(self.webdav_url, remote_path)
        
        try:
            response = requests.get(url, auth=self.auth, timeout=60)
            
            if response.status_code == 200:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"✅ Successfully downloaded {remote_path} to {local_path}")
                return True
            else:
                print(f"❌ Download failed. Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Download error: {e}")
            return False
    
    def create_folder(self, folder_path):
        """
        Create a folder in Nextcloud
        
        Args:
            folder_path (str): Path of the folder to create
        """
        url = urljoin(self.webdav_url, folder_path)
        
        try:
            response = requests.request('MKCOL', url, auth=self.auth, timeout=30)
            
            if response.status_code == 201:
                print(f"✅ Successfully created folder: {folder_path}")
                return True
            elif response.status_code == 405:
                print(f"ℹ️  Folder already exists: {folder_path}")
                return True
            else:
                print(f"❌ Failed to create folder. Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error creating folder: {e}")
            return False

def main():
    """Main function to demonstrate Nextcloud operations"""
    print("🌥️  Nextcloud Connection Program")
    print("=" * 40)
    
    
    SERVER_URL = "https://mdan.online"
    USERNAME = "Prueba"
    PASSWORD = "pruebaproyecto"
    
    
    # Initialize client
    client = NextcloudClient(SERVER_URL, USERNAME, PASSWORD)
    
    # Test connection
    if not client.test_connection():
        return
    
    print()
    
    # Demonstrate operations
    try:
        # List root directory
        print("1. Listing root directory:")
        client.list_files()
        print()
        
        # Create a test folder
        print("2. Creating a test folder:")
        client.create_folder("test_folder")
        print()
        
        # Create a test file and upload it
        print("3. Creating and uploading a test file:")
        test_file = "test_file.txt"
        with open(test_file, 'w') as f:
            f.write(f"Test file created at {datetime.now()}\n")
            f.write("This is a test upload to Nextcloud!\n")
        
        client.upload_file(test_file, "test_folder/uploaded_test.txt")
        
        # Clean up local test file
        os.remove(test_file)
        print()
        
        # List the test folder
        print("4. Listing test folder contents:")
        client.list_files("test_folder/")
        print()
        
        # Download the file we just uploaded
        print("5. Downloading the uploaded file:")
        client.download_file("test_folder/uploaded_test.txt", "downloads/downloaded_test.txt")
        # Display downloaded file content
        if os.path.exists("downloaded_test.txt"):
            print("\n📄 Downloaded file contents:")
            with open("downloaded_test.txt", 'r') as f:
                print(f.read())
            
            # Clean up
            os.remove("downloaded_test.txt")
        
    except KeyboardInterrupt:
        print("\n⏹️  Program interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
    mcp.run(transport='stdio')
    print('...', file=sys.stderr)