import React, { useEffect, useState } from 'react';
import { Layout } from '../components/layout/Layout';
import { apiListPets, apiRunSimulation, PetSummary, SimulationResult } from '../api/client';
import './simulator.css';

export const SimulatorPage: React.FC = () => {
  const [pets, setPets] = useState<PetSummary[]>([]);
  const [yourTeam, setYourTeam] = useState<string[]>([]);
  const [enemyTeam, setEnemyTeam] = useState<string[]>([]);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiListPets().then(setPets).catch(console.error);
  }, []);

  const togglePet = (id: string, team: 'your' | 'enemy') => {
    if (team === 'your') {
      setYourTeam(prev =>
        prev.includes(id) ? prev.filter(p => p !== id) : prev.length < 3 ? [...prev, id] : prev
      );
    } else {
      setEnemyTeam(prev =>
        prev.includes(id) ? prev.filter(p => p !== id) : prev.length < 3 ? [...prev, id] : prev
      );
    }
  };

  const runSimulation = async () => {
    if (yourTeam.length === 0 || enemyTeam.length === 0) {
      setError('Select at least one pet for each team');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiRunSimulation({
        player_pets: yourTeam,
        enemy_pets: enemyTeam
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const getPetName = (id: string) => pets.find(p => String(p.id) === id)?.name || id;

  return (
    <Layout background="/assets/backgrounds/simulator.png">
      <div className="page-panel simulator-container">

        <header className="sim-header">
          <h1 className="sim-title">Pet Battle Simulator</h1>
          <p className="sim-subtitle">
            Configure teams, abilities, and run predictive battles.
          </p>
        </header>

        <div className="sim-panels">

          {/* LEFT SIDE – CONFIG */}
          <div className="sim-left">
            <section className="sim-section">
              <h2 className="sim-section-title">Your Team ({yourTeam.length}/3)</h2>
              <div className="sim-pet-grid">
                {pets.map(pet => (
                  <button
                    key={pet.id}
                    className={`sim-pet-btn ${yourTeam.includes(String(pet.id)) ? 'selected' : ''}`}
                    onClick={() => togglePet(String(pet.id), 'your')}
                  >
                    {pet.name}
                  </button>
                ))}
              </div>
            </section>

            <section className="sim-section">
              <h2 className="sim-section-title">Enemy Team ({enemyTeam.length}/3)</h2>
              <div className="sim-pet-grid">
                {pets.map(pet => (
                  <button
                    key={pet.id}
                    className={`sim-pet-btn ${enemyTeam.includes(String(pet.id)) ? 'selected enemy' : ''}`}
                    onClick={() => togglePet(String(pet.id), 'enemy')}
                  >
                    {pet.name}
                  </button>
                ))}
              </div>
            </section>

            <button className="sim-run-btn" onClick={runSimulation} disabled={loading}>
              {loading ? 'Running...' : 'Run Simulation'}
            </button>
            {error && <p className="sim-error">{error}</p>}
          </div>

          {/* RIGHT SIDE – RESULTS */}
          <div className="sim-right">
            <section className="sim-results-section">
              <h2 className="sim-section-title">Results</h2>
              <div className="sim-results-box">
                {result ? (
                  <div>
                    <p className="sim-winner">Winner: <strong>{result.winner}</strong></p>
                    <p>Turns: {result.turns}</p>
                    <p>{result.message}</p>
                  </div>
                ) : (
                  <p>Simulation results will appear here.</p>
                )}
              </div>
            </section>

            <section className="sim-logs-section">
              <h2 className="sim-section-title">Battle Log</h2>
              <div className="sim-log-window">
                {result?.log && result.log.length > 0 ? (
                  <pre>{result.log.join('\n')}</pre>
                ) : (
                  <p>No simulation run yet.</p>
                )}
              </div>
            </section>
          </div>

        </div>
      </div>
    </Layout>
  );
};
