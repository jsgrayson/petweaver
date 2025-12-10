import React, { useEffect, useState } from 'react';
import { Layout } from '../components/layout/Layout';
import { apiListPets, PetSummary } from '../api/client';
import './codex.css';

const FALLBACK_IMAGE = '/assets/pets/magic.png';

// Robust image component with fallback
function PetCodexCard({ pet }: { pet: PetSummary }) {
  const [imgError, setImgError] = useState(false);

  // Build portrait URL from family if not provided
  const familySlug = pet.family.toLowerCase();
  const portraitSrc = !imgError && pet.portraitUrl
    ? pet.portraitUrl
    : !imgError
      ? `/assets/pets/${familySlug}.png`
      : FALLBACK_IMAGE;

  return (
    <article className="codex-card">
      <div className={`codex-card-portrait rarity-${pet.rarity.toLowerCase()}`}>
        <img
          src={portraitSrc}
          alt={pet.name}
          loading="lazy"
          onError={() => setImgError(true)}
        />
      </div>
      <div className="codex-card-body">
        <h2 className="codex-card-name">{pet.name}</h2>
        <div className="codex-card-meta">
          <span className="codex-card-family">{pet.family}</span>
          <span
            className={`codex-card-rarity codex-rarity-${pet.rarity.toLowerCase()}`}
          >
            {pet.rarity}
          </span>
        </div>
      </div>
    </article>
  );
}

export const PetsPage: React.FC = () => {
  const [pets, setPets] = useState<PetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiListPets()
      .then((data) => {
        setPets(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load pets');
        setLoading(false);
      });
  }, []);

  return (
    <Layout background="/assets/backgrounds/codex.png">
      <div className="codex-page">
        <div className="page-panel codex-panel">
          <div className="codex-vignette" />
          <div className="codex-inner">
            <header className="codex-header">
              <div>
                <h1 className="codex-title">Pet Codex</h1>
                <p className="codex-subtitle">
                  Browse all discovered companions and their battle potential.
                </p>
              </div>
              <input
                type="search"
                className="codex-search"
                placeholder="Search by name or family…"
              />
            </header>

            {loading && (
              <p style={{ color: '#94a3b8', textAlign: 'center' }}>Loading pets...</p>
            )}
            {error && (
              <p style={{ color: '#f87171', textAlign: 'center' }}>{error}</p>
            )}

            <section className="codex-grid">
              {pets.map((pet) => (
                <PetCodexCard key={pet.id} pet={pet} />
              ))}
            </section>
          </div>
        </div>
      </div>
    </Layout>
  );
};
