import React, { useState, useEffect } from 'react';
import { 
  Upload, Database, AlertTriangle, ShieldCheck, CheckCircle, 
  XCircle, Filter, Edit3, Lock, Unlock, Users, ChevronRight, 
  Terminal, RefreshCw, BarChart2, FileText, ArrowRight, Download
} from 'lucide-react';

let apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
if (apiBase && !apiBase.endsWith('/api') && !apiBase.endsWith('/api/')) {
  apiBase = `${apiBase.endsWith('/') ? apiBase.slice(0, -1) : apiBase}/api`;
}
const API_BASE = apiBase;

export default function App() {
  const [clients, setClients] = useState([]);
  const [selectedClient, setSelectedClient] = useState('');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [currentUserRole, setCurrentUserRole] = useState('analyst'); // analyst, auditor
  
  // Data records & lists
  const [records, setRecords] = useState([]);
  const [factors, setFactors] = useState([]);
  const [locations, setLocations] = useState([]);
  
  // Filtering & Selection
  const [scopeFilter, setScopeFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [bulkSelection, setBulkSelection] = useState([]);
  
  // Modals & Action States
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [showLockModal, setShowLockModal] = useState(false);
  const [overrideForm, setOverrideForm] = useState({
    activity_value: '',
    date_start: '',
    date_end: '',
    comment: ''
  });
  const [lockForm, setLockForm] = useState({
    date_start: '2026-04-01',
    date_end: '2026-06-30'
  });
  const [rejectionComment, setRejectionComment] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);

  // Ingestion Output states
  const [sapFile, setSapFile] = useState(null);
  const [utilityFile, setUtilityFile] = useState(null);
  const [sapMessage, setSapMessage] = useState('');
  const [utilityMessage, setUtilityMessage] = useState('');
  const [terminalLogs, setTerminalLogs] = useState([]);
  const [terminalRunning, setTerminalRunning] = useState(false);
  const [backendError, setBackendError] = useState(null);

  // 1. Initial Load: Fetch Clients & Emission Factors
  useEffect(() => {
    fetchClients();
    fetchFactors();
  }, []);

  // 2. Load records whenever client changes
  useEffect(() => {
    if (selectedClient) {
      fetchRecords();
      fetchLocations();
    }
  }, [selectedClient, scopeFilter, categoryFilter, statusFilter]);

  const fetchClients = async () => {
    try {
      const res = await fetch(`${API_BASE}/clients/`);
      if (res.ok) {
        const data = await res.json();
        setClients(data);
        if (data.length > 0) {
          setSelectedClient(data[0].id);
        }
      } else {
        setBackendError('Could not contact backend API. Make sure Django server is running on http://localhost:8000');
      }
    } catch (err) {
      setBackendError('Backend connection error. Make sure Django server is running on http://localhost:8000');
    }
  };

  const fetchFactors = async () => {
    try {
      const res = await fetch(`${API_BASE}/factors/`);
      if (res.ok) {
        const data = await res.json();
        setFactors(data);
      }
    } catch (err) {}
  };

  const fetchLocations = async () => {
    try {
      const res = await fetch(`${API_BASE}/locations/?client=${selectedClient}`);
      if (res.ok) {
        const data = await res.json();
        setLocations(data);
      }
    } catch (err) {}
  };

  const fetchRecords = async () => {
    try {
      let url = `${API_BASE}/records/?client=${selectedClient}`;
      if (scopeFilter) url += `&scope=${scopeFilter}`;
      if (categoryFilter) url += `&category=${categoryFilter}`;
      if (statusFilter) url += `&status=${statusFilter}`;

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setRecords(data);
        setBackendError(null);
      }
    } catch (err) {
      setBackendError('Backend connection error. Make sure Django server is running on http://localhost:8000');
    }
  };

  // Re-fetch helper
  const refreshAll = () => {
    fetchRecords();
    fetchLocations();
    fetchFactors();
    setBulkSelection([]);
    if (selectedRecord) {
      // Re-fetch selected record details
      const updated = records.find(r => r.id === selectedRecord.id);
      if (updated) setSelectedRecord(updated);
    }
  };

  // 3. File Upload Handlers
  const handleSapUpload = async (e) => {
    e.preventDefault();
    if (!sapFile) return;

    const formData = new FormData();
    formData.append('client_id', selectedClient);
    formData.append('file', sapFile);

    setSapMessage('Uploading and parsing SAP export...');
    try {
      const res = await fetch(`${API_BASE}/ingest/sap/`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        setSapMessage(`Success: ${data.message}`);
        setSapFile(null);
        refreshAll();
      } else {
        setSapMessage(`Error: ${data.error}`);
      }
    } catch (err) {
      setSapMessage('Error uploading file. Backend offline.');
    }
  };

  const handleUtilityUpload = async (e) => {
    e.preventDefault();
    if (!utilityFile) return;

    const formData = new FormData();
    formData.append('client_id', selectedClient);
    formData.append('file', utilityFile);

    setUtilityMessage('Uploading and processing utility CSV...');
    try {
      const res = await fetch(`${API_BASE}/ingest/utility/`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        setUtilityMessage(`Success: ${data.message}`);
        setUtilityFile(null);
        refreshAll();
      } else {
        setUtilityMessage(`Error: ${data.error}`);
      }
    } catch (err) {
      setUtilityMessage('Error uploading file. Backend offline.');
    }
  };

  // 4. API Simulated Pull animation
  const handleTravelPull = async () => {
    if (terminalRunning) return;
    setTerminalRunning(true);
    setTerminalLogs([]);

    const logMessages = [
      { text: '> Initializing Navan / Concur travel platform API client...', status: 'info' },
      { text: '> Requesting OAuth authentication token (scopes: travel.read, expenses.read)...', status: 'info' },
      { text: '> Auth success. Token granted (expires in 3599s).', status: 'success' },
      { text: '> Fetching bookings for current reporting period (2026-Q2)...', status: 'info' },
      { text: '> Pulled 6 travel bookings from API server.', status: 'success' },
      { text: '> Injecting records into Breathe ESG Normalization pipeline...', status: 'warning' },
      { text: '> Resolving flights JFK -> LHR coordinates. Distance: 5569.2 km.', status: 'info' },
      { text: '> Applied Scope 3 Category Flights (Business Long-haul factor 0.29 kg/pkm). Emissions: 1.615 tCO2e.', status: 'success' },
      { text: '> Resolving hotel stay location (DE). Emissions: 0.061 tCO2e.', status: 'success' },
      { text: '> Flagged Booking CONC-82199: Anomaly [Zero or negative room nights: -2].', status: 'error' },
      { text: '> Completed travel data processing: 6 ingested, 1 flagged anomaly.', status: 'success' }
    ];

    for (let i = 0; i < logMessages.length; i++) {
      await new Promise(r => setTimeout(r, 600));
      setTerminalLogs(prev => [...prev, logMessages[i]]);
    }

    try {
      const res = await fetch(`${API_BASE}/ingest/travel/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: selectedClient })
      });
      if (res.ok) {
        refreshAll();
      }
    } catch (err) {}
    
    setTerminalRunning(false);
  };

  // 5. Audit Actions: Approve, Reject, Override, Lock
  const handleApprove = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/records/${id}/approve/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ acting_user: currentUserRole })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedRecord(updated);
        refreshAll();
      }
    } catch (err) {}
  };

  const handleReject = async (id) => {
    if (!rejectionComment.strip) {
      alert('Rejection comment is required.');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/records/${id}/reject/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ acting_user: currentUserRole, comment: rejectionComment })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedRecord(updated);
        setShowRejectInput(false);
        setRejectionComment('');
        refreshAll();
      } else {
        const data = await res.json();
        alert(data.error);
      }
    } catch (err) {}
  };

  const handleOverrideSubmit = async (e) => {
    e.preventDefault();
    if (!overrideForm.comment) {
      alert('Override justification comment is required.');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/records/${selectedRecord.id}/edit_record/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          acting_user: currentUserRole,
          activity_value: overrideForm.activity_value,
          date_start: overrideForm.date_start,
          date_end: overrideForm.date_end,
          comment: overrideForm.comment
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedRecord(updated);
        setShowOverrideModal(false);
        setOverrideForm({ activity_value: '', date_start: '', date_end: '', comment: '' });
        refreshAll();
      } else {
        const data = await res.json();
        alert(data.error);
      }
    } catch (err) {}
  };

  const handleLockSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/records/lock_period/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: selectedClient,
          acting_user: currentUserRole,
          date_start: lockForm.date_start,
          date_end: lockForm.date_end
        })
      });
      if (res.ok) {
        const data = await res.json();
        alert(data.message);
        setShowLockModal(false);
        refreshAll();
      }
    } catch (err) {}
  };

  // Bulk operations
  const handleBulkApprove = async () => {
    if (bulkSelection.length === 0) return;
    try {
      const res = await fetch(`${API_BASE}/records/bulk_approve/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_ids: bulkSelection, acting_user: currentUserRole })
      });
      if (res.ok) {
        refreshAll();
      }
    } catch (err) {}
  };

  const handleBulkReject = async () => {
    if (bulkSelection.length === 0) return;
    const comment = prompt('Enter comment for bulk rejection:');
    if (!comment) return;
    try {
      const res = await fetch(`${API_BASE}/records/bulk_reject/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_ids: bulkSelection, acting_user: currentUserRole, comment })
      });
      if (res.ok) {
        refreshAll();
      }
    } catch (err) {}
  };

  const toggleSelectAll = () => {
    if (bulkSelection.length === records.length) {
      setBulkSelection([]);
    } else {
      setBulkSelection(records.filter(r => !r.is_locked).map(r => r.id));
    }
  };

  const toggleSelectRecord = (id) => {
    if (bulkSelection.includes(id)) {
      setBulkSelection(prev => prev.filter(x => x !== id));
    } else {
      setBulkSelection(prev => [...prev, id]);
    }
  };

  // Summary Metrics calculations
  const totalCarbon = records
    .filter(r => r.status === 'APPROVED')
    .reduce((sum, r) => sum + parseFloat(r.co2e_emissions_t), 0);
    
  const pendingCount = records.filter(r => r.status === 'PENDING').length;
  const flaggedCount = records.filter(r => r.status === 'FLAGGED').length;

  return (
    <div className="app-container">
      {/* Sidebar navigation */}
      <aside className="sidebar glass-panel">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '32px' }}>
          <ShieldCheck size={28} className="text-emerald" style={{ color: '#10b981' }} />
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Breathe ESG</h3>
            <span style={{ fontSize: '0.7rem', color: '#94a3b8', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Audit Engine v1.0</span>
          </div>
        </div>

        <div style={{ marginBottom: '24px' }}>
          <label style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '8px' }}>Workspace Client</label>
          <select value={selectedClient} onChange={(e) => setSelectedClient(e.target.value)} style={{ width: '100%' }}>
            {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>

        <div style={{ marginBottom: '32px' }}>
          <label style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '8px' }}>Role Settings</label>
          <div style={{ display: 'flex', background: 'rgba(0,0,0,0.2)', padding: '4px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <button 
              className={`btn ${currentUserRole === 'analyst' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, padding: '6px 12px', fontSize: '0.8rem', border: 'none' }}
              onClick={() => { setCurrentUserRole('analyst'); setBulkSelection([]); }}
            >
              Analyst
            </button>
            <button 
              className={`btn ${currentUserRole === 'auditor' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, padding: '6px 12px', fontSize: '0.8rem', border: 'none' }}
              onClick={() => { setCurrentUserRole('auditor'); setBulkSelection([]); }}
            >
              Auditor
            </button>
          </div>
        </div>

        <nav style={{ flexGrow: 1 }}>
          <a href="#" className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>
            <Database size={18} />
            <span>Records Workbench</span>
          </a>
          <a href="#" className={`nav-item ${activeTab === 'ingest' ? 'active' : ''}`} onClick={() => setActiveTab('ingest')}>
            <Upload size={18} />
            <span>Data Ingestion</span>
          </a>
          <a href="#" className={`nav-item ${activeTab === 'factors' ? 'active' : ''}`} onClick={() => setActiveTab('factors')}>
            <FileText size={18} />
            <span>Emission Factors</span>
          </a>
        </nav>

        <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '16px', display: 'flex', gap: '8px', flexDirection: 'column' }}>
          {currentUserRole === 'auditor' && (
            <button className="btn btn-primary" onClick={() => setShowLockModal(true)} style={{ width: '100%', padding: '10px' }}>
              <Lock size={16} /> Sign-off Period
            </button>
          )}
          <button className="btn btn-secondary" onClick={refreshAll} style={{ width: '100%', padding: '10px' }}>
            <RefreshCw size={14} /> Sync Workspace
          </button>
        </div>
      </aside>

      {/* Main Viewport */}
      <main className="main-content">
        {backendError && (
          <div className="glass-panel" style={{ padding: '16px', marginBottom: '24px', display: 'flex', gap: '12px', borderLeft: '4px solid #ef4444', alignItems: 'center', background: 'rgba(239, 68, 68, 0.05)' }}>
            <AlertTriangle color="#ef4444" />
            <div>
              <p style={{ fontWeight: 600 }}>Backend Connection Error</p>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>{backendError}</p>
            </div>
          </div>
        )}

        {/* Tab 1: Analyst records review workbench */}
        {activeTab === 'dashboard' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px' }}>
              <div>
                <h1 style={{ fontSize: '2.2rem', fontWeight: 800 }}>Audit Review Workbench</h1>
                <p style={{ color: '#94a3b8', marginTop: '4px' }}>Review, edit, and approve incoming ESG activity entries before finalizing audit logs.</p>
              </div>
            </div>

            {/* Metrics cards grid */}
            <div className="grid-cols-3" style={{ marginBottom: '40px' }}>
              <div className="glass-panel" style={{ padding: '24px', display: 'flex', gap: '20px', alignItems: 'center' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(16,185,129,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <ShieldCheck size={24} style={{ color: '#10b981' }} />
                </div>
                <div>
                  <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Auditable Carbon</span>
                  <h2 style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '4px' }}>{totalCarbon.toFixed(3)} <span style={{ fontSize: '1rem', fontWeight: 500, color: '#94a3b8' }}>tCO₂e</span></h2>
                </div>
              </div>

              <div className="glass-panel" style={{ padding: '24px', display: 'flex', gap: '20px', alignItems: 'center' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(59,130,246,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Database size={24} style={{ color: '#3b82f6' }} />
                </div>
                <div>
                  <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Pending Approvals</span>
                  <h2 style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '4px' }}>{pendingCount} <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#60a5fa' }}>entries</span></h2>
                </div>
              </div>

              <div className="glass-panel" style={{ padding: '24px', display: 'flex', gap: '20px', alignItems: 'center' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(245,158,11,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <AlertTriangle size={24} style={{ color: '#f59e0b' }} />
                </div>
                <div>
                  <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Flagged Anomalies</span>
                  <h2 style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '4px' }}>{flaggedCount} <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#fbbf24' }}>flagged</span></h2>
                </div>
              </div>
            </div>

            {/* Filter toolbar */}
            <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
              <div style={{ display: 'flex', gap: '16px', flexGrow: 1 }}>
                <div style={{ flex: 1, maxWidth: '200px' }}>
                  <label style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Scope</label>
                  <select value={scopeFilter} onChange={(e) => setScopeFilter(e.target.value)}>
                    <option value="">All Scopes</option>
                    <option value="1">Scope 1 (Direct)</option>
                    <option value="2">Scope 2 (Indirect)</option>
                    <option value="3">Scope 3 (Travel)</option>
                  </select>
                </div>
                <div style={{ flex: 1, maxWidth: '200px' }}>
                  <label style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Category</label>
                  <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
                    <option value="">All Categories</option>
                    <option value="Fuel">Fuel (Procurement)</option>
                    <option value="Electricity">Electricity (Utility)</option>
                    <option value="Flights">Flights</option>
                    <option value="Hotels">Hotels</option>
                    <option value="Ground Transport">Ground Transport</option>
                  </select>
                </div>
                <div style={{ flex: 1, maxWidth: '200px' }}>
                  <label style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Status</label>
                  <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="">All Statuses</option>
                    <option value="PENDING">Pending Approval</option>
                    <option value="FLAGGED">Flagged (Suspicious)</option>
                    <option value="APPROVED">Approved</option>
                    <option value="REJECTED">Rejected</option>
                  </select>
                </div>
              </div>

              {/* Bulk Actions (Only visible for Analysts) */}
              {currentUserRole === 'analyst' && bulkSelection.length > 0 && (
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center', background: 'rgba(255,255,255,0.03)', padding: '6px 16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>{bulkSelection.length} selected</span>
                  <button className="btn btn-primary" onClick={handleBulkApprove} style={{ padding: '6px 12px', fontSize: '0.8rem' }}><CheckCircle size={14} /> Approve</button>
                  <button className="btn btn-danger" onClick={handleBulkReject} style={{ padding: '6px 12px', fontSize: '0.8rem' }}><XCircle size={14} /> Reject</button>
                </div>
              )}
            </div>

            {/* Records Table */}
            <div className="glass-panel" style={{ padding: '8px' }}>
              <div className="table-container" style={{ border: 'none', marginTop: 0 }}>
                <table>
                  <thead>
                    <tr>
                      {currentUserRole === 'analyst' && (
                        <th style={{ width: '48px', textAlign: 'center' }}>
                          <input type="checkbox" checked={bulkSelection.length > 0 && bulkSelection.length === records.filter(r => !r.is_locked).length} onChange={toggleSelectAll} style={{ width: '16px', height: '16px' }} />
                        </th>
                      )}
                      <th>Activity Date</th>
                      <th>Category</th>
                      <th>Description</th>
                      <th>Normalized Value</th>
                      <th>Calculated Carbon</th>
                      <th>Location</th>
                      <th>Status</th>
                      <th>Lock</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.length === 0 ? (
                      <tr>
                        <td colSpan={currentUserRole === 'analyst' ? 9 : 8} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
                          No activity records found. Head to the <strong>Data Ingestion</strong> tab to import data.
                        </td>
                      </tr>
                    ) : (
                      records.map(record => {
                        const statusBadge = 
                          record.status === 'APPROVED' ? <span className="badge badge-approved"><CheckCircle size={12} /> Approved</span> :
                          record.status === 'REJECTED' ? <span className="badge badge-rejected"><XCircle size={12} /> Rejected</span> :
                          record.status === 'FLAGGED' ? <span className="badge badge-flagged"><AlertTriangle size={12} /> Flagged</span> :
                          <span className="badge badge-pending"><Database size={12} /> Pending</span>;
                          
                        return (
                          <tr key={record.id} onClick={() => setSelectedRecord(record)} style={{ cursor: 'pointer' }}>
                            {currentUserRole === 'analyst' && (
                              <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                                <input 
                                  type="checkbox" 
                                  disabled={record.is_locked}
                                  checked={bulkSelection.includes(record.id)} 
                                  onChange={() => toggleSelectRecord(record.id)} 
                                  style={{ width: '16px', height: '16px', opacity: record.is_locked ? 0.3 : 1 }}
                                />
                              </td>
                            )}
                            <td>{record.date_start}</td>
                            <td>
                              <span style={{ fontSize: '0.75rem', padding: '2px 6px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', display: 'block', width: 'fit-content', fontWeight: 600, color: '#94a3b8' }}>
                                Scope {record.scope}
                              </span>
                              <span style={{ display: 'block', marginTop: '4px', fontWeight: 500 }}>{record.category}</span>
                            </td>
                            <td>{record.description}</td>
                            <td style={{ fontFamily: 'var(--font-mono)' }}>{parseFloat(record.activity_value).toLocaleString()} {record.activity_unit}</td>
                            <td style={{ fontWeight: 700, color: record.status === 'APPROVED' ? '#34d399' : '#e2e8f0', fontFamily: 'var(--font-mono)' }}>
                              {parseFloat(record.co2e_emissions_t).toFixed(4)} tCO₂e
                            </td>
                            <td>{record.location}</td>
                            <td>{statusBadge}</td>
                            <td>
                              {record.is_locked ? (
                                <Lock size={16} style={{ color: '#fbbf24' }} />
                              ) : (
                                <Unlock size={16} style={{ color: '#64748b', opacity: 0.3 }} />
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Ingestion Console */}
        {activeTab === 'ingest' && (
          <div>
            <div style={{ marginBottom: '32px' }}>
              <h1 style={{ fontSize: '2.2rem', fontWeight: 800 }}>Data Ingestion Workbench</h1>
              <p style={{ color: '#94a3b8', marginTop: '4px' }}>Load raw files or execute live REST API fetches to parse, validate, and compute carbon values.</p>
            </div>

            <div className="grid-cols-2" style={{ marginBottom: '32px' }}>
              {/* Uploader Left */}
              <div className="glass-panel" style={{ padding: '32px' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}><Database size={20} className="text-emerald" style={{ color: '#10b981' }} /> File Ingestion Console</h3>
                <p style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '24px' }}>Submit SAP procurement tables or Utility portals energy CSV files. The parsing engine automatically handles plant maps, units conversion, calendar-month pro-rating, and flags anomalous records.</p>
                
                {/* SAP Upload */}
                <form onSubmit={handleSapUpload} style={{ marginBottom: '24px', paddingBottom: '24px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block', marginBottom: '8px' }}>SAP Procurement File Export</label>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <input type="file" accept=".csv" onChange={(e) => setSapFile(e.target.files[0])} style={{ flexGrow: 1 }} />
                    <button type="submit" className="btn btn-primary" disabled={!sapFile}><Upload size={16} /> Load SAP</button>
                  </div>
                  {sapMessage && <p style={{ fontSize: '0.8rem', marginTop: '8px', color: sapMessage.startsWith('Error') ? '#f87171' : '#34d399' }}>{sapMessage}</p>}
                </form>

                {/* Utility Upload */}
                <form onSubmit={handleUtilityUpload} style={{ marginBottom: '16px' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block', marginBottom: '8px' }}>Utility Facility Portal Export</label>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <input type="file" accept=".csv" onChange={(e) => setUtilityFile(e.target.files[0])} style={{ flexGrow: 1 }} />
                    <button type="submit" className="btn btn-primary" disabled={!utilityFile}><Upload size={16} /> Load Utility</button>
                  </div>
                  {utilityMessage && <p style={{ fontSize: '0.8rem', marginTop: '8px', color: utilityMessage.startsWith('Error') ? '#f87171' : '#34d399' }}>{utilityMessage}</p>}
                </form>

                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '8px', marginTop: '24px', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}><Download size={14} /> Download Sample Files</h4>
                  <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '12px' }}>Test the parsing engine using realistic client data containing both valid rows and validation errors.</p>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <a href="/sap_procurement_export.csv" download className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.75rem' }}>SAP CSV Export</a>
                    <a href="/utility_portal_export.csv" download className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.75rem' }}>Utility CSV Export</a>
                  </div>
                </div>
              </div>

              {/* API Pull Right */}
              <div className="glass-panel" style={{ padding: '32px', display: 'flex', flexDirection: 'column' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}><Terminal size={20} style={{ color: '#38bdf8' }} /> simulated travel api pull</h3>
                <p style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '24px' }}>Click to pull simulated corporate bookings from travel endpoints (Concur / Navan API). Airport pairs coordinates are calculated dynamically using the Haversine formula.</p>
                
                <button 
                  className="btn btn-secondary" 
                  onClick={handleTravelPull} 
                  disabled={terminalRunning}
                  style={{ alignSelf: 'flex-start', marginBottom: '20px', borderColor: '#38bdf8', color: '#38bdf8' }}
                >
                  {terminalRunning ? <RefreshCw size={16} className="animate-spin" /> : <Terminal size={16} />}
                  Execute API Ingestion Pull
                </button>

                <div className="terminal-console" style={{ flexGrow: 1 }}>
                  {terminalLogs.length === 0 ? (
                    <span style={{ color: '#475569' }}>Terminal ready. Click pull to fetch travel logs...</span>
                  ) : (
                    terminalLogs.map((log, idx) => {
                      let cls = "terminal-line";
                      if (log.status === 'success') cls += " terminal-success";
                      if (log.status === 'error') cls += " terminal-error";
                      if (log.status === 'warning') cls += " terminal-warning";
                      return (
                        <div key={idx} className={cls}>
                          {log.text}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Emission Factors reference */}
        {activeTab === 'factors' && (
          <div>
            <div style={{ marginBottom: '32px' }}>
              <h1 style={{ fontSize: '2.2rem', fontWeight: 800 }}>Carbon Intensity Factors</h1>
              <p style={{ color: '#94a3b8', marginTop: '4px' }}>Active coefficients used for Scope 1, 2, and 3 conversions. Seeded from EPA, IEA, and DEFRA 2026 guidelines.</p>
            </div>

            <div className="glass-panel" style={{ padding: '8px' }}>
              <div className="table-container" style={{ border: 'none', marginTop: 0 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Scope / Category</th>
                      <th>Subcategory</th>
                      <th>Coefficient Value</th>
                      <th>Unit Denominator</th>
                      <th>Geographic Location</th>
                      <th>Standard Source</th>
                      <th>Calendar Year</th>
                    </tr>
                  </thead>
                  <tbody>
                    {factors.length === 0 ? (
                      <tr>
                        <td colSpan={7} style={{ textAlign: 'center', padding: '40px' }}>Loading factors database...</td>
                      </tr>
                    ) : (
                      factors.map(f => (
                        <tr key={f.id}>
                          <td>
                            <span style={{ fontSize: '0.75rem', padding: '2px 6px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', fontWeight: 600, color: '#94a3b8' }}>
                              {f.category === 'Fuel' ? 'Scope 1' : f.category === 'Electricity' ? 'Scope 2' : 'Scope 3'}
                            </span>
                            <span style={{ display: 'block', marginTop: '4px', fontWeight: 600, color: '#f1f5f9' }}>{f.category}</span>
                          </td>
                          <td style={{ fontWeight: 500 }}>{f.subcategory}</td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#10b981' }}>{f.value}</td>
                          <td>kg CO₂e / {f.unit.split('/')[-1] || f.unit}</td>
                          <td>{f.location}</td>
                          <td style={{ color: '#94a3b8' }}>{f.source_reference}</td>
                          <td>{f.year}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Slide-out Records Detail Drawer */}
      {selectedRecord && (
        <div className="overlay" onClick={() => { setSelectedRecord(null); setShowRejectInput(false); }}>
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
              <div>
                <h3 style={{ fontSize: '1.25rem' }}>Record #{selectedRecord.id}</h3>
                <span style={{ color: '#64748b', fontSize: '0.85rem' }}>Ingested {new Date(selectedRecord.created_at).toLocaleString()}</span>
              </div>
              <button className="btn btn-secondary" onClick={() => { setSelectedRecord(null); setShowRejectInput(false); }} style={{ padding: '6px 12px' }}>Close</button>
            </div>

            {selectedRecord.status === 'FLAGGED' && (
              <div className="glass-panel" style={{ padding: '16px', background: 'rgba(245, 158, 11, 0.05)', borderLeft: '4px solid #f59e0b', marginBottom: '24px' }}>
                <span style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: '#fbbf24', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Anomaly Warning</span>
                <p style={{ fontSize: '0.85rem', color: '#fef08a', whiteSpace: 'pre-wrap' }}>{selectedRecord.flag_reason}</p>
              </div>
            )}

            {selectedRecord.is_locked && (
              <div className="glass-panel" style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.05)', borderLeft: '4px solid #10b981', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={16} style={{ color: '#10b981' }} />
                <div>
                  <span style={{ fontSize: '0.8rem', color: '#34d399', fontWeight: 600, display: 'block' }}>Locked for Audit</span>
                  <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>This record was finalized and cannot be modified.</span>
                </div>
              </div>
            )}

            {/* Calculations Breakdown */}
            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', marginBottom: '24px' }}>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '8px' }}>Carbon Accounting Recipe</span>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ fontSize: '0.9rem', color: '#94a3b8' }}>{selectedRecord.category} Scope {selectedRecord.scope}</span>
                <span style={{ fontSize: '1.4rem', fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)' }}>{parseFloat(selectedRecord.co2e_emissions_t).toFixed(4)} tCO₂e</span>
              </div>
              
              <div style={{ marginTop: '16px', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '12px', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ color: '#94a3b8' }}>Activity Value:</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{parseFloat(selectedRecord.activity_value).toLocaleString()} {selectedRecord.activity_unit}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ color: '#94a3b8' }}>Geographic Region:</span>
                  <span>{selectedRecord.location}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Activity Duration:</span>
                  <span>{selectedRecord.date_start} to {selectedRecord.date_end}</span>
                </div>
              </div>
            </div>

            {/* Action buttons (Analysts only) */}
            {currentUserRole === 'analyst' && !selectedRecord.is_locked && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '32px' }}>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <button className="btn btn-primary" onClick={() => handleApprove(selectedRecord.id)} style={{ flex: 1 }}><CheckCircle size={16} /> Approve Entry</button>
                  <button className="btn btn-danger" onClick={() => setShowRejectInput(!showRejectInput)} style={{ flex: 1 }}><XCircle size={16} /> Reject Entry</button>
                </div>
                
                {showRejectInput && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', background: 'rgba(255,255,255,0.02)', padding: '12px', borderRadius: '8px' }}>
                    <input 
                      type="text" 
                      placeholder="Mandatory rejection comment..." 
                      value={rejectionComment} 
                      onChange={(e) => setRejectionComment(e.target.value)} 
                    />
                    <button className="btn btn-danger" onClick={() => handleReject(selectedRecord.id)} style={{ width: 'fit-content', padding: '6px 12px', alignSelf: 'flex-end', fontSize: '0.8rem' }}>Submit Rejection</button>
                  </div>
                )}

                <button className="btn btn-secondary" onClick={() => {
                  setOverrideForm({
                    activity_value: selectedRecord.activity_value,
                    date_start: selectedRecord.date_start,
                    date_end: selectedRecord.date_end,
                    comment: ''
                  });
                  setShowOverrideModal(true);
                }}>
                  <Edit3 size={16} /> Override / Correct Data
                </button>
              </div>
            )}

            {/* Audit History Timeline */}
            <div>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, display: 'block', marginBottom: '16px' }}>Audit Trail History</span>
              <div style={{ position: 'relative', paddingLeft: '24px', borderLeft: '1px solid rgba(255,255,255,0.08)' }}>
                {selectedRecord.audit_trails && selectedRecord.audit_trails.map((trail, idx) => (
                  <div key={trail.id} style={{ marginBottom: '24px', position: 'relative' }}>
                    {/* Circle Dot */}
                    <div style={{ 
                      position: 'absolute', 
                      left: '-30px', 
                      top: '2px', 
                      width: '11px', 
                      height: '11px', 
                      borderRadius: '50%', 
                      background: 
                        trail.action_type === 'APPROVE' ? '#10b981' :
                        trail.action_type === 'REJECT' ? '#ef4444' :
                        trail.action_type === 'EDIT' ? '#fbbf24' : '#3b82f6',
                      border: '2px solid hsl(var(--bg-secondary))'
                    }}></div>
                    
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                      <strong style={{ fontSize: '0.9rem', textTransform: 'capitalize' }}>
                        {trail.action_type === 'INGEST' ? 'Ingested' : 
                         trail.action_type === 'EDIT' ? 'Override Applied' : 
                         trail.action_type === 'APPROVE' ? 'Approved' : 
                         trail.action_type === 'REJECT' ? 'Rejected' : 'Locked'}
                      </strong>
                      <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{new Date(trail.timestamp).toLocaleString()}</span>
                    </div>
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginTop: '4px' }}>
                      By: {trail.user_detail ? trail.user_detail.username : 'Ingestion Engine'}
                    </span>
                    <p style={{ fontSize: '0.85rem', color: '#e2e8f0', marginTop: '6px', fontStyle: 'italic' }}>
                      &ldquo;{trail.comment}&rdquo;
                    </p>

                    {trail.changed_fields && (
                      <div style={{ fontSize: '0.75rem', color: '#fcd34d', background: 'rgba(245,158,11,0.05)', padding: '8px', borderRadius: '4px', marginTop: '8px', fontFamily: 'var(--font-mono)' }}>
                        {Object.entries(trail.changed_fields).map(([field, delta]) => (
                          <div key={field}>
                            {field}: {delta.old} &rarr; {delta.new}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Override Value Modal */}
      {showOverrideModal && (
        <div className="overlay" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glass-panel" style={{ width: '400px', padding: '32px' }}>
            <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}><Edit3 size={20} /> Override Normalized Data</h3>
            
            <form onSubmit={handleOverrideSubmit}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Normalized Activity Value ({selectedRecord.activity_unit})</label>
                <input 
                  type="number" 
                  step="0.0001"
                  required
                  value={overrideForm.activity_value} 
                  onChange={(e) => setOverrideForm({...overrideForm, activity_value: e.target.value})} 
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Start Date</label>
                <input 
                  type="date" 
                  required
                  value={overrideForm.date_start} 
                  onChange={(e) => setOverrideForm({...overrideForm, date_start: e.target.value})} 
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>End Date</label>
                <input 
                  type="date" 
                  required
                  value={overrideForm.date_end} 
                  onChange={(e) => setOverrideForm({...overrideForm, date_end: e.target.value})} 
                />
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Justification Comment (Mandatory)</label>
                <textarea 
                  required
                  rows={3} 
                  placeholder="Explain why this data needs correction..."
                  value={overrideForm.comment} 
                  onChange={(e) => setOverrideForm({...overrideForm, comment: e.target.value})} 
                />
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowOverrideModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Overrides</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Lock Reporting Period Modal (Auditors only) */}
      {showLockModal && (
        <div className="overlay" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glass-panel" style={{ width: '400px', padding: '32px' }}>
            <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}><Lock size={20} style={{ color: '#fbbf24' }} /> Finalize Audit Sign-off</h3>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '20px' }}>Finalizing will freeze all APPROVED records in this reporting period. Locked records are legally sealed and cannot be edited, approved, or rejected.</p>
            
            <form onSubmit={handleLockSubmit}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Reporting Period Start</label>
                <input 
                  type="date" 
                  required
                  value={lockForm.date_start} 
                  onChange={(e) => setLockForm({...lockForm, date_start: e.target.value})} 
                />
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>Reporting Period End</label>
                <input 
                  type="date" 
                  required
                  value={lockForm.date_end} 
                  onChange={(e) => setLockForm({...lockForm, date_end: e.target.value})} 
                />
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowLockModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" style={{ background: '#fbbf24', color: '#000000' }}>Confirm Period Lock</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
