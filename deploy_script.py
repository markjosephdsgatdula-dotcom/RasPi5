import paramiko
import os
import sys

def load_env(filepath):
    """Simple parser to read .env file without external dependencies."""
    env = {}
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env[key.strip()] = value.strip()
    return env

def transfer_directory(sftp, local_dir, remote_dir):
    """Recursively upload a directory using SFTP."""
    for root, dirs, files in os.walk(local_dir):
        # Skip hidden directories like .git
        if '.git' in root.split(os.sep):
            continue
            
        relative_path = os.path.relpath(root, local_dir)
        if relative_path == '.':
            current_remote_dir = remote_dir
        else:
            current_remote_dir = os.path.join(remote_dir, relative_path).replace('\\', '/')
            
        # Create directory on remote if it doesn't exist
        try:
            sftp.stat(current_remote_dir)
        except FileNotFoundError:
            sftp.mkdir(current_remote_dir)
            print(f"Created directory: {current_remote_dir}")
            
        # Upload files in the current directory
        for file in files:
            # Skip .env and local data/session_state files to avoid uploading sensitive/temporary data
            if file in ['.env', 'session_state.json'] or root.endswith('data') or 'data/' in root.replace('\\', '/'):
                continue
                
            local_file_path = os.path.join(root, file)
            remote_file_path = os.path.join(current_remote_dir, file).replace('\\', '/')
            print(f"Uploading {local_file_path} to {remote_file_path}")
            sftp.put(local_file_path, remote_file_path)

def main():
    # Dynamically resolve paths relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    
    # Load configuration from .env
    env = load_env(env_path)
    
    hostname = env.get('PI_HOST', '192.168.11.35')
    username = env.get('PI_USER', 'rinkamarkmaaku')
    password = env.get('PI_PASSWORD')
    
    if not password:
        print("[ERROR] PI_PASSWORD not found in .env file.")
        print("Please configure your .env file using .env.example as a template.")
        sys.exit(1)
        
    local_source_dir = script_dir
    remote_dest_dir = f'/home/{username}/weld_inspection_system'

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {hostname} as {username}...")
        ssh.connect(hostname, username=username, password=password, timeout=10)
        print("Connected successfully!")
        
        # 1. Start SFTP session and transfer files
        print("\nStarting SFTP transfer...")
        sftp = ssh.open_sftp()
        transfer_directory(sftp, local_source_dir, remote_dest_dir)
        sftp.close()
        print("Transfer complete.")
        
        # 2. Run the application
        print("\nExecuting main.py on the remote Pi...")
        commands = [
            "sudo -S apt install python3-pil.imagetk -y",
            "export DISPLAY=:0 && cd ~/weld_inspection_system && python main.py"
        ]
        
        for cmd in commands:
            print(f"Running: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
            
            if cmd.startswith("sudo"):
                stdin.write(password + "\n")
                stdin.flush()
                
            # Read output
            print(stdout.read().decode('utf-8'))
            
            exit_status = stdout.channel.recv_exit_status()
            print(f"Exit Status: {exit_status}\n")
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        ssh.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()
