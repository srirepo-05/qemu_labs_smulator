import requests
import logging
import random
import string

GUAC_URL = "http://localhost:8080/guacamole"
GUAC_USER = "guacadmin"
GUAC_PASS = "guacadmin"

# This token will be our "admin" token for the backend's session
AUTH_TOKEN = None

def get_auth_token():
    """Gets and caches an auth token from Guacamole."""
    global AUTH_TOKEN
    if AUTH_TOKEN:
        return AUTH_TOKEN

    try:
        response = requests.post(
            f"{GUAC_URL}/api/tokens",
            data={"username": GUAC_USER, "password": GUAC_PASS}
        )
        response.raise_for_status()
        AUTH_TOKEN = response.json()["authToken"]
        return AUTH_TOKEN
    except requests.RequestException as e:
        logging.error(f"Failed to get Guacamole auth token: {e}")
        return None

def get_all_connections():
    """Gets a dictionary of all Guacamole connections."""
    token = get_auth_token()
    if not token:
        return None
    import random
    import string
    try:
        response = requests.get(
            f"{GUAC_URL}/api/session/data/postgresql/connections?token={token}"
        )
        response.raise_for_status()
        return response.json() # This returns a DICT of {id: {data}}
    except requests.RequestException as e:
        logging.error(f"Failed to get all Guac connections: {e}")
        return None

def create_vnc_connection(node_name, vnc_port):
    """Creates a new VNC connection in Guacamole."""
    token = get_auth_token()
    if not token:
        return None

    connection_data = {
        "parentIdentifier": "ROOT", # Root connection group
        "name": node_name,
        "protocol": "vnc",
        "parameters": {
            "hostname": "host.docker.internal", 
            "port": str(vnc_port),
            "password": "" # Assuming no VNC password
        },
        "attributes": {}
    }

    try:
        response = requests.post(
            f"{GUAC_URL}/api/session/data/postgresql/connections?token={token}",
            json=connection_data
        )
        response.raise_for_status()
        conn_id = response.json()["identifier"]
        return conn_id
    except requests.RequestException as e:
        error_detail = e
        if e.response is not None:
            try:
                error_detail = e.response.json() # Try to get JSON error
            except requests.exceptions.JSONDecodeError:
                error_detail = e.response.text # Fallback to text
        
        logging.error(f"Failed to create Guac connection: {error_detail}")
        return None

def delete_vnc_connection(connection_id):
    """Deletes a VNC connection from Guacamole."""
    token = get_auth_token()
    if not token:
        return False

    try:
        response = requests.delete(
            f"{GUAC_URL}/api/session/data/postgresql/connections/{connection_id}?token={token}"
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        error_detail = e
        if e.response is not None:
            try:
                error_detail = e.response.json() # Try to get JSON error
            except requests.exceptions.JSONDecodeError:
                error_detail = e.response.text # Fallback to text
        
        logging.error(f"Failed to delete Guac connection: {error_detail}")
        return False

def delete_connection_by_name(node_name):
    """Finds and deletes a Guacamole connection by its name."""
    all_connections = get_all_connections()
    if not all_connections:
        logging.info(f"Could not check for ghost connection (API error).")
        return

    connection_id_to_delete = None
    for conn_id, conn_data in all_connections.items():
        if conn_data['name'] == node_name:
            connection_id_to_delete = conn_id
            break
    
    if connection_id_to_delete:
        logging.info(f"Deleting ghost connection '{node_name}' with ID {connection_id_to_delete}")
        delete_vnc_connection(connection_id_to_delete)
    else:
        logging.info(f"No ghost connection found for '{node_name}'.")

def get_temp_token(connection_id):
    """Gets a one-time use token for a specific connection."""
    # Generate a unique username for this session
    session_user = f"nodeuser_{connection_id}_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    session_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    # 1. Create the user in Guacamole
    admin_token = get_auth_token()
    if not admin_token:
        return None, None
    try:
        # Create user
        user_payload = {
            "username": session_user,
            "password": session_pass,
            "attributes": {}
        }
        resp = requests.post(f"{GUAC_URL}/api/session/data/postgresql/users?token={admin_token}", json=user_payload)
        resp.raise_for_status()
    except requests.RequestException as e:
        # If user exists, ignore error
        if e.response is not None and e.response.status_code == 409:
            pass
        else:
            logging.error(f"Failed to create Guacamole user: {e}")
            return None, None

    # 2. Grant connection permission to this user
    try:
        perm_payload = [
            {"op": "add", "path": f"/connectionPermissions/{connection_id}", "value": "READ"}
        ]
        resp = requests.patch(f"{GUAC_URL}/api/session/data/postgresql/users/{session_user}/permissions?token={admin_token}", json=perm_payload)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to grant connection permission: {e}")
        return None, None

    # 3. Get a token for this user, for this connection
    try:
        response = requests.post(
            f"{GUAC_URL}/api/tokens",
            data={
                "username": session_user,
                "password": session_pass,
                "connection": connection_id
            }
        )
        response.raise_for_status()
        return response.json()["authToken"], session_user
    except requests.RequestException as e:
        error_detail = e
        if e.response is not None:
            try:
                error_detail = e.response.json()
            except requests.exceptions.JSONDecodeError:
                error_detail = e.response.text
        logging.error(f"Failed to get temp token: {error_detail}")
        return None, None