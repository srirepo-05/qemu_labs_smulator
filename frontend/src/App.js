import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './App.css';

// Configure axios to point to our backend
const api = axios.create({
  baseURL: 'http://localhost:8000',
});

function App() {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState({});

  // --- API Call Functions ---

  const fetchNodes = useCallback(async () => {
    try {
      const response = await api.get('/nodes');
      setNodes(response.data);
    } catch (error) {
      console.error('Failed to fetch nodes:', error);
    }
  }, []);

  // Fetch nodes on initial load
  useEffect(() => {
    fetchNodes();
  }, [fetchNodes]);

  const handleAction = async (nodeId, action) => {
    setLoading((prev) => ({ ...prev, [nodeId]: true }));
    try {
      await api.post(`/nodes/${nodeId}/${action}`);
      await fetchNodes(); 
    } catch (error) {
      console.error(`Failed to ${action} node ${nodeId}:`, error);
      alert(`Error: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading((prev) => ({ ...prev, [nodeId]: false }));
    }
  };

  const handleAddNode = async () => {
    setLoading((prev) => ({ ...prev, add: true }));
    try {
      await api.post('/nodes');
      await fetchNodes();
    } catch (error) {
      console.error('Failed to add node:', error);
      alert(`Error: ${error.response?.data?.detail || error.message}`);
    } finally {
      // This "finally" block guarantees this runs, even if there's an error
      setLoading((prev) => ({ ...prev, add: false }));
    }
  };

  const handleDeleteNode = async (nodeId, nodeName) => {
    // Show a confirmation dialog
    if (!window.confirm(`Are you sure you want to permanently delete ${nodeName}? This cannot be undone.`)) {
      return;
    }

    setLoading((prev) => ({ ...prev, [nodeId]: true }));
    try {
      await api.delete(`/nodes/${nodeId}`);
      // Refresh the list after the action
      await fetchNodes(); 
    } catch (error) {
      console.error(`Failed to delete node ${nodeId}:`, error);
      alert(`Error: ${error.response?.data?.detail || error.message}`);
    }
    // No need to setLoading(false) since the item will be gone
  };


  // --- Render ---

  return (
    <div className="container">
      <header>
        <h1>QEMU Network Lab</h1>
        <button
          className="btn btn-primary"
          onClick={handleAddNode}
          disabled={loading.add}
        >
          {loading.add ? 'Creating...' : 'Add Node'}
        </button>
      </header>
      <ul className="node-list">
        {nodes.length === 0 && <li className="node-item">No nodes found.</li>}
        
        {nodes.map((node) => (
          <NodeItem
            key={node.id}
            node={node}
            onAction={handleAction}
            onDelete={handleDeleteNode} // Pass the delete handler
            isLoading={!!loading[node.id] || !!loading.add} // Aware of global 'add' loading
          />
        ))}
      </ul>
    </div>
  );
}

// --- NodeItem Sub-Component ---

function NodeItem({ node, onAction, onDelete, isLoading }) {
  const isRunning = node.status === 'RUNNING';

  return (
    <li className="node-item">
      <div className="node-info">
        <span className="node-name">{node.name}</span>
        <span className={`status status-${node.status}`}>{node.status}</span>
      </div>
      <div className="node-actions">
        
        {/* --- THIS IS THE "OLD" <a> TAG BUTTON --- */}
        <a
          className={`btn btn-console ${!isRunning ? 'disabled' : ''}`}
          href={isRunning ? node.guacamole_url : undefined}
          target="_blank"
          rel="noopener noreferrer"
          role="button"
          onClick={(e) => !isRunning && e.preventDefault()} // Prevent click if disabled
          title={isRunning ? "Click to open console" : "Node must be running"}
        >
          Open
        </a>
        
        <button
          className="btn btn-run"
          onClick={() => onAction(node.id, 'run')}
          disabled={isLoading || isRunning}
        >
          Run
        </button>
        <button
          className="btn btn-stop"
          onClick={() => onAction(node.id, 'stop')}
          disabled={isLoading || !isRunning}
        >
          Stop
        </button>
        <button
          className="btn btn-wipe"
          onClick={() => onAction(node.id, 'wipe')}
          disabled={isLoading || isRunning} // Safety: Disable if running
        >
          Wipe
        </button>

        {/* --- NEW "DELETE" BUTTON --- */}
        <button
          className="btn btn-delete"
          onClick={() => onDelete(node.id, node.name)} // Pass node info
          disabled={isLoading || isRunning} // Safety: Disable if running
        >
          Delete
        </button>

      </div>
    </li>
  );
}

export default App;