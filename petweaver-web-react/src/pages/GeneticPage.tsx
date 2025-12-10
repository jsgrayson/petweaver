import React from 'react';
import { Layout } from '../components/layout/Layout';
import './genetic.css';

export const GeneticPage: React.FC = () => {
  return (
    <Layout background="/assets/backgrounds/genetic.png">
      <div className="page-panel genetic-panel">
        <header className="gen-header">
          <h1 className="gen-title">Genetic Optimizer</h1>
          <p className="gen-subtitle">
            Blend traits and find optimal pet builds.
          </p>
        </header>

        <div className="gen-layout">
          <section className="gen-section">
            <h2>Inputs</h2>
            <p>Pick base pets, traits, and constraints.</p>
          </section>

          <section className="gen-section gen-visual">
            <h2>Visualization</h2>
            <p>Graphs, trees, or result summaries go here.</p>
          </section>
        </div>
      </div>
    </Layout>
  );
};
