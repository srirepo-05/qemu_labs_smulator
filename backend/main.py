import subprocess
import os
import psutil
import socket
import logging # <-- Make sure logging is imported
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

import database as db
import guacamole_api as guac
from database import Node, NodeStatus

# --- Configuration ---
BASE_IMAGE_PATH = os.path.abspath("../images/base.qcow2")
OVERLAYS_DIR = os.path.abspath("../overlays")
VNC_PORT_START = 5900

# --- FastAPI App ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    db.create_db_and_tables()
    if not os.path.exists(OVERLAYS_DIR):
        os.makedirs(OVERLAYS_DIR)
    print(f"Base image path: {BASE_IMAGE_PATH}")
    print(f"Overlays directory: {OVERLAYS_DIR}")


# --- Utility Functions ---
def find_free_port(start_port):
    """Finds an available VNC port (5900 + display_num)."""
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port # Port is free
        port += 1
        if port > start_port + 100: # Max 100 nodes
            raise Exception("No free VNC ports found.")

def create_overlay(node_name):
    overlay_path = os.path.join(OVERLAYS_DIR, f"{node_name}.qcow2")
    cmd = [
        'qemu-img.exe', 'create',
        '-f', 'qcow2',         # Format of the new file
        '-F', 'qcow2',         # Format of the backing file
        '-b', BASE_IMAGE_PATH, # The backing file
        overlay_path           # The new file
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return overlay_path
    except subprocess.CalledProcessError as e:
        print(f"Failed to create overlay: {e.stderr.decode()}")
        return None

def check_process_status(db_session: Session):
    """Clean up nodes whose processes have died unexpectedly."""
    nodes = db_session.query(Node).filter(Node.status == NodeStatus.RUNNING).all()
    for node in nodes:
        if not psutil.pid_exists(node.qemu_pid):
            print(f"Process for node {node.name} (PID {node.qemu_pid}) is gone. Cleaning up.")
            if node.guac_connection_id: # Check if it exists
                guac.delete_vnc_connection(node.guac_connection_id)
            node.status = NodeStatus.STOPPED
            node.qemu_pid = None
            node.vnc_port = None
            node.guac_connection_id = None
    db_session.commit()


# --- API Endpoints ---
@app.get("/nodes")
def list_nodes(db_session: Session = Depends(db.get_db)):
    check_process_status(db_session) # Important!
    nodes = db_session.query(Node).all()

    # --- THIS IS THE OLD, BUGGY VERSION ---
    node_list = []
    for node in nodes:
        url = None
        if node.status == NodeStatus.RUNNING:
            temp_token, session_user = guac.get_temp_token(node.guac_connection_id)
            if temp_token:
                # 'c' is for 'connection', 'postgresql' is the data source name
                url = f"http://localhost:8080/guacamole/#/client/c%2Fpostgresql/{node.guac_connection_id}?token={temp_token}"

        node_list.append({
            "id": node.id,
            "name": node.name,
            "status": node.status.value,
            "guacamole_url": url # The URL is generated here
        })
    return node_list
    # --- END OF OLD, BUGGY VERSION ---

@app.post("/nodes")
def create_node(db_session: Session = Depends(db.get_db)):
    # Find the next available node ID
    last_node = db_session.query(Node).order_by(Node.id.desc()).first()
    new_id = (last_node.id + 1) if last_node else 1
    node_name = f"node-{new_id}"

    overlay_path = create_overlay(node_name)
    if not overlay_path:
        raise HTTPException(status_code=500, detail="Failed to create QEMU overlay.")

    new_node = Node(
        id=new_id,
        name=node_name,
        status=NodeStatus.STOPPED,
        overlay_path=overlay_path
    )
    db_session.add(new_node)
    db_session.commit()
    db_session.refresh(new_node)
    return new_node


@app.post("/nodes/{node_id}/run")
def run_node(node_id: int, db_session: Session = Depends(db.get_db)):
    node = db_session.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    if node.status == NodeStatus.RUNNING:
        return node

    # --- Includes the "ghost" fix ---
    logging.info(f"Attempting to clean up any ghost connection for {node.name}")
    guac.delete_connection_by_name(node.name)
    # --- End of fix ---
    
    # 1. Find free VNC port
    vnc_port = find_free_port(VNC_PORT_START)
    vnc_display_num = vnc_port - VNC_PORT_START # e.g., 0, 1, 2

    # 2. Create Guacamole connection *first*
    conn_id = guac.create_vnc_connection(node.name, vnc_port)
    if not conn_id:
        raise HTTPException(status_code=500, detail="Failed to create Guacamole connection.")

    # 3. Start QEMU process
    qemu_cmd = [
        'qemu-system-x86_64.exe',
        '-m', '512M',                 # 512MB RAM
        '-hda', node.overlay_path,    # Use the overlay disk
        '-vnc', f'0.0.0.0:{vnc_display_num}', # Listen on all interfaces
        '-nographic',                 # Run headless (this is what spams the console)
        '-net', 'nic',                # Add a network card
        '-net', 'user'                # Use simple user-mode networking
    ]

    try:
        # Use Popen to start in the background
        process = subprocess.Popen(qemu_cmd)
    except Exception as e:
        guac.delete_vnc_connection(conn_id) # Rollback
        raise HTTPException(status_code=500, detail=f"Failed to start QEMU: {e}")

    # 4. Update database
    node.status = NodeStatus.RUNNING
    node.qemu_pid = process.pid
    node.vnc_port = vnc_port
    node.guac_connection_id = conn_id
    db_session.commit()

    return node

@app.post("/nodes/{node_id}/stop")
def stop_node(node_id: int, db_session: Session = Depends(db.get_db)):
    node = db_session.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    if node.status == NodeStatus.STOPPED:
        return node

    # 1. Kill the process
    try:
        proc = psutil.Process(node.qemu_pid)
        proc.terminate() # or proc.kill()
    except psutil.NoSuchProcess:
        print(f"Process {node.qemu_pid} already dead.")
    except Exception as e:
        print(f"Error stopping process: {e}")

    # 2. Delete Guacamole connection
    if node.guac_connection_id:
        guac.delete_vnc_connection(node.guac_connection_id)

    # 3. Update database
    node.status = NodeStatus.STOPPED
    node.qemu_pid = None
    node.vnc_port = None
    node.guac_connection_id = None
    db_session.commit()

    return node

@app.post("/nodes/{node_id}/wipe")
def wipe_node(node_id: int, db_session: Session = Depends(db.get_db)):
    node = db_session.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=4.4, detail="Node not found.")

    # 1. Stop it if it's running
    if node.status == NodeStatus.RUNNING:
        stop_node(node_id, db_session)

    # 2. Delete and re-create overlay
    try:
        os.remove(node.overlay_path)
    except OSError as e:
        print(f"Could not delete overlay (may not exist): {e}")

    new_overlay_path = create_overlay(node.name)
    if not new_overlay_path:
        raise HTTPException(status_code=500, detail="Failed to re-create overlay.")

    node.overlay_path = new_overlay_path # Path should be the same
    db_session.commit()

    return node

@app.delete("/nodes/{node_id}")
def delete_node(node_id: int, db_session: Session = Depends(db.get_db)):
    node = db_session.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")

    # 1. Stop it if it's running (this also deletes the guac connection)
    if node.status == NodeStatus.RUNNING:
        try:
            # Manually kill process
            proc = psutil.Process(node.qemu_pid)
            proc.terminate()
        except psutil.NoSuchProcess:
            pass # Process already dead
        
        # Manually delete guac connection
        if node.guac_connection_id:
            guac.delete_vnc_connection(node.guac_connection_id)

    # 2. Delete the overlay file
    try:
        if os.path.exists(node.overlay_path):
            os.remove(node.overlay_path)
        else:
            print(f"Warning: Overlay file not found, but proceeding with delete: {node.overlay_path}")
    except OSError as e:
        print(f"Error deleting overlay file, but proceeding with delete: {e}")

    # 3. Delete from database
    db_session.delete(node)
    db_session.commit()
    
    return {"detail": "Node deleted successfully"}