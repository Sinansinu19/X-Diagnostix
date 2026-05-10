import React, { useState, useEffect } from 'react';

const Dashboard = () => {
  const [telemetry, setTelemetry] = useState({
    predicted_RUL: null,
    risk_level: null,
    top_sensors: [],
    maintenance_action: null,
  });
  const [connectionStatus, setConnectionStatus] = useState('Connecting...');
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/dashboard');

    ws.onopen = () => {
      setConnectionStatus('Connected');
      setIsConnected(true);
      addLog('[Connection] WebSocket connected to ws://localhost:8000/ws/dashboard');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setTelemetry({
          predicted_RUL: data.predicted_RUL,
          risk_level: data.risk_level,
          top_sensors: data.top_sensors || [],
          maintenance_action: data.maintenance_action,
        });
        addLog(`[Message] ${JSON.stringify(data)}`);
      } catch (error) {
        addLog(`[Error] Failed to parse message: ${error.message}`);
      }
    };

    ws.onerror = (error) => {
      setConnectionStatus('Error');
      setIsConnected(false);
      addLog(`[Error] WebSocket error: ${error.message || 'Unknown error'}`);
    };

    ws.onclose = () => {
      setConnectionStatus('Disconnected');
      setIsConnected(false);
      addLog('[Connection] WebSocket disconnected');
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, []);

  const addLog = (message) => {
    setLogs((prevLogs) => {
      const newLogs = [message, ...prevLogs];
      return newLogs.slice(0, 50);
    });
  };

  const getRiskColor = (riskLevel) => {
    switch (riskLevel) {
      case 'HIGH':
        return '#dc2626';
      case 'MEDIUM':
        return '#f59e0b';
      case 'LOW':
        return '#10b981';
      default:
        return '#6b7280';
    }
  };

  const headerStyle = {
    padding: '24px',
    borderBottom: '1px solid #30363d',
    backgroundColor: '#0d1117',
  };

  const titleStyle = {
    margin: 0,
    fontSize: '28px',
    fontWeight: '600',
    color: '#c9d1d9',
  };

  const connectionIndicatorStyle = {
    display: 'inline-block',
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    marginRight: '8px',
    backgroundColor: isConnected ? '#10b981' : '#6b7280',
  };

  const statusStyle = {
    fontSize: '12px',
    color: '#8b949e',
    marginTop: '8px',
  };

  const containerStyle = {
    padding: '24px',
    backgroundColor: '#0d1117',
    minHeight: '100vh',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", sans-serif',
    color: '#c9d1d9',
  };

  const kpiGridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
    gap: '16px',
    marginBottom: '32px',
  };

  const cardStyle = {
    padding: '20px',
    backgroundColor: '#161b22',
    border: '1px solid #30363d',
    borderRadius: '8px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
  };

  const cardLabelStyle = {
    fontSize: '12px',
    fontWeight: '600',
    color: '#8b949e',
    textTransform: 'uppercase',
    marginBottom: '12px',
    letterSpacing: '0.5px',
  };

  const cardValueStyle = {
    fontSize: '28px',
    fontWeight: '700',
    color: '#c9d1d9',
    wordBreak: 'break-word',
  };

  const riskBadgeStyle = {
    display: 'inline-block',
    padding: '6px 12px',
    borderRadius: '4px',
    fontSize: '14px',
    fontWeight: '600',
    width: 'fit-content',
    backgroundColor: getRiskColor(telemetry.risk_level) + '20',
    color: getRiskColor(telemetry.risk_level),
    border: `1px solid ${getRiskColor(telemetry.risk_level)}`,
  };

  const sensorListStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  };

  const sensorTagStyle = {
    display: 'inline-block',
    padding: '4px 8px',
    backgroundColor: '#30363d',
    borderRadius: '4px',
    fontSize: '12px',
    color: '#79c0ff',
    width: 'fit-content',
  };

  const chartPlaceholderStyle = {
    padding: '40px',
    backgroundColor: '#161b22',
    border: '2px dashed #30363d',
    borderRadius: '8px',
    textAlign: 'center',
    marginBottom: '32px',
    minHeight: '250px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'column',
  };

  const placeholderTextStyle = {
    color: '#8b949e',
    fontSize: '14px',
  };

  const logSectionStyle = {
    marginTop: '32px',
  };

  const logTitleStyle = {
    fontSize: '14px',
    fontWeight: '600',
    color: '#8b949e',
    textTransform: 'uppercase',
    marginBottom: '12px',
    letterSpacing: '0.5px',
  };

  const logContainerStyle = {
    backgroundColor: '#0d1117',
    border: '1px solid #30363d',
    borderRadius: '8px',
    padding: '12px',
    maxHeight: '300px',
    overflowY: 'auto',
    fontFamily: 'monospace',
    fontSize: '11px',
    color: '#79c0ff',
  };

  const logEntryStyle = {
    padding: '4px 0',
    borderBottom: '1px solid #21262d',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
  };

  return (
    <div style={containerStyle}>
      <header style={headerStyle}>
        <h1 style={titleStyle}>Pathfinder Live Telemetry</h1>
        <div style={statusStyle}>
          <span style={connectionIndicatorStyle} />
          {connectionStatus}
        </div>
      </header>

      <main style={{ padding: '24px' }}>
        <section>
          <div style={kpiGridStyle}>
            <div style={cardStyle}>
              <div style={cardLabelStyle}>Remaining Useful Life (RUL)</div>
              <div style={cardValueStyle}>
                {telemetry.predicted_RUL !== null ? `${telemetry.predicted_RUL.toFixed(2)} cycles` : 'Awaiting data...'}
              </div>
            </div>

            <div style={cardStyle}>
              <div style={cardLabelStyle}>Risk Level</div>
              <div style={riskBadgeStyle}>
                {telemetry.risk_level || 'Awaiting data...'}
              </div>
            </div>

            <div style={cardStyle}>
              <div style={cardLabelStyle}>Top Contributing Sensors</div>
              <div style={sensorListStyle}>
                {telemetry.top_sensors && telemetry.top_sensors.length > 0 ? (
                  telemetry.top_sensors.map((sensor, index) => (
                    <span key={index} style={sensorTagStyle}>
                      {sensor}
                    </span>
                  ))
                ) : (
                  <span style={{ color: '#8b949e', fontSize: '12px' }}>Awaiting data...</span>
                )}
              </div>
            </div>

            <div style={cardStyle}>
              <div style={cardLabelStyle}>Recommended Maintenance Action</div>
              <div style={{ fontSize: '14px', color: '#c9d1d9', lineHeight: '1.5' }}>
                {telemetry.maintenance_action || 'Awaiting data...'}
              </div>
            </div>
          </div>
        </section>

        <section>
          <div style={chartPlaceholderStyle}>
            <div>
              <div style={{ ...placeholderTextStyle, fontWeight: '600', marginBottom: '8px' }}>
                📊 Chart.js / Plotly Integration Zone
              </div>
              <div style={placeholderTextStyle}>
                RUL Trend, Risk Distribution, and Sensor Analytics will render here.
              </div>
            </div>
          </div>
        </section>

        <section style={logsectionstyle}>
          <div style={logTitleStyle}>Developer Log (Raw WebSocket Stream)</div>
          <div style={logContainerStyle}>
            {logs.length > 0 ? (
              logs.map((log, index) => (
                <div key={index} style={logEntryStyle}>
                  {log}
                </div>
              ))
            ) : (
              <div style={logEntryStyle}>Awaiting connection...</div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
};

export default Dashboard;
