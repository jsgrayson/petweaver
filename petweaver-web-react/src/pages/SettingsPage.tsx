import React from 'react';
import { Layout } from '../components/layout/Layout';
import './settings.css';

export const SettingsPage: React.FC = () => {
  return (
    <Layout background="/assets/backgrounds/settings.png">
      <div className="page-panel settings-panel">
        <header className="settings-header">
          <h1 className="settings-title">Settings</h1>
          <p className="settings-subtitle">
            Configure PetWeaver behavior and connections.
          </p>
        </header>

        <div className="settings-grid">
          <section className="settings-section">
            <h2>General</h2>
            <p className="text-slate-400 text-sm">Use PetWeaver Automation: <span className="text-green-400">Enabled</span></p>
          </section>
          <section className="settings-section">
            <h2>API / Server</h2>
            <p className="text-slate-400 text-sm">Backend: <span className="text-slate-200">http://127.0.0.1:5003</span></p>
            <p className="text-slate-400 text-sm">Status: <span className="text-green-400">Connected</span></p>
          </section>
          <section className="settings-section">
            <h2>UI & Theme</h2>
            <p className="text-slate-400 text-sm">Theme: <span className="text-slate-200">Arcane Glass</span></p>
          </section>
        </div>
      </div>
    </Layout>
  );
};
