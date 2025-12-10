import React, { useEffect, useState } from 'react';
import { Layout } from '../components/layout/Layout';
import { apiListEncounters } from '../api/client';
import './encounters.css';

export const EncountersPage: React.FC = () => {
  const [encounters, setEncounters] = useState<any[]>([]);

  useEffect(() => {
    apiListEncounters().then(setEncounters).catch(console.error);
  }, []);

  return (
    <Layout background="/assets/backgrounds/encounters.png">
      <div className="page-panel enc-panel">
        <header className="enc-header">
          <h1 className="enc-title">Encounter Map</h1>
          <p className="enc-subtitle">
            View where key battles and spawn points are located.
          </p>
        </header>

        <div className="enc-body">
          <section className="enc-map">
            <p className="text-slate-400 text-center mt-10">Map View placeholder</p>
          </section>
          <section className="enc-sidebar">
            <h2>Encounter List</h2>
            <ul className="space-y-2 mt-4 max-h-[400px] overflow-y-auto">
              {encounters.map((enc, i) => (
                <li key={i} className="text-sm p-2 bg-slate-800/50 rounded border border-slate-700/50">
                  {enc.name || `Encounter #${i + 1}`}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </Layout>
  );
};
