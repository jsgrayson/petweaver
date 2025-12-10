import React, { useEffect, useState } from 'react';
import { Layout } from '../components/layout/Layout';
import { apiGetServerStatus, apiListLogs, apiListPets } from '../api/client';
import './dashboard.css';

export const DashboardPage: React.FC = () => {
  const [petCount, setPetCount] = useState<number>(0);
  const [status, setStatus] = useState<string>('Checking...');
  const [simCount, setSimCount] = useState<number>(0);

  useEffect(() => {
    // Quick load of real stats
    apiListPets().then(pets => setPetCount(pets.length)).catch(() => setPetCount(0));
    apiGetServerStatus().then(s => setStatus(s.status === 'online' ? 'Online' : 'Offline')).catch(() => setStatus('Offline'));
    // Mock simulation count for now or fetch if API exists
    setSimCount(12);
  }, []);

  return (
    <Layout background="/assets/backgrounds/dashboard.png">
      <div className="page-panel dashboard-panel">
        <header className="dash-header">
          <div>
            <h1 className="dash-title">PetWeaver Dashboard</h1>
            <p className="dash-subtitle">
              Overview of your pet collections, simulations, and server status.
            </p>
          </div>
        </header>

        <section className="dash-grid">
          <div className="dash-card">
            <h2>Total Pets</h2>
            <p className="dash-metric">{petCount}</p>
            <p className="dash-label">Discovered across all families.</p>
          </div>
          <div className="dash-card">
            <h2>Recent Simulations</h2>
            <p className="dash-metric">{simCount}</p>
            <p className="dash-label">Results in the last 24 hours.</p>
          </div>
          <div className="dash-card">
            <h2>Server Status</h2>
            <p className={`dash-metric ${status === 'Online' ? 'dash-ok' : 'text-red-400'}`}>{status}</p>
            <p className="dash-label">Latency & uptime summary.</p>
          </div>
        </section>
      </div>
    </Layout>
  );
};
