import React, { useEffect, useState } from 'react';
import { Layout } from '../components/layout/Layout';
import { apiGetServerStatus, ServerStatus } from '../api/client';
import './serverStatus.css';

export const ServerStatusPage: React.FC = () => {
  const [status, setStatus] = useState<ServerStatus | null>(null);

  useEffect(() => {
    apiGetServerStatus().then(setStatus).catch(console.error);
  }, []);

  const s: ServerStatus = status || {
    status: 'offline',
    uptimeSeconds: 0,
    queueDepth: 0,
    workers: 0,
    combatStats: { wins: 0, total_battles: 0, win_rate: 0 },
    dbStats: { pets: 0, unique: 0, max_level: 0, rare_or_better: 0, avg_level: 0 }
  };

  return (
    <Layout background="/assets/backgrounds/server.png">
      <div className="page-panel server-panel">
        <header className="server-header">
          <h1 className="server-title">Server Status</h1>
          <p className="server-subtitle">
            Current uptime, latency, and shard health.
          </p>
        </header>

        <div className="server-grid">
          <div className="server-card">
            <h2>Uptime</h2>
            <p className="server-metric">{s.status === 'online' ? 'Online' : 'Offline'}</p>
          </div>
          <div className="server-card">
            <h2>Queue Depth</h2>
            <p className="server-metric">{s.queueDepth}</p>
          </div>
          <div className="server-card">
            <h2>Active Battles</h2>
            <p className="server-metric">{s.combatStats?.total_battles || 0}</p>
          </div>
        </div>

        <section className="server-log">
          <h2>Database Stats</h2>
          <div className="server-log-window">
            <pre>{JSON.stringify(s.dbStats, null, 2)}</pre>
          </div>
        </section>
      </div>
    </Layout>
  );
};
