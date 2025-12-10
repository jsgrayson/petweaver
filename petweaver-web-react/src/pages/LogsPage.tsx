import React, { useEffect, useState } from 'react';
import { Layout } from '../components/layout/Layout';
import { apiListLogs } from '../api/client';
import './logs.css';

export const LogsPage: React.FC = () => {
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    // Poll logs every 5s
    const fetchLogs = () => {
      apiListLogs().then(setLogs).catch(console.error);
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Layout background="/assets/backgrounds/logs.png">
      <div className="page-panel logs-panel">
        <header className="logs-header">
          <h1 className="logs-title">System Logs</h1>
          <p className="logs-subtitle">
            Debug events, battle traces, and backend messages.
          </p>
        </header>

        <div className="logs-window">
          {logs.length === 0 ? <p className="text-slate-500 italic">No logs available.</p> : (
            <pre className="whitespace-pre-wrap font-mono text-xs">
              {logs.join('\n')}
            </pre>
          )}
        </div>
      </div>
    </Layout>
  );
};
