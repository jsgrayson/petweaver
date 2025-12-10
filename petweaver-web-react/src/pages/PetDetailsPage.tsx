import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Layout } from '../components/layout/Layout';
import { apiGetPet, PetDetails } from '../api/client';
import './petDetails.css';

export const PetDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [pet, setPet] = useState<PetDetails | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      apiGetPet(id)
        .then(setPet)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [id]);

  if (loading) {
    return <Layout><div className="p-8 text-center text-slate-400">Loading pet data...</div></Layout>;
  }

  if (!pet) {
    return <Layout><div className="p-8 text-center text-red-400">Pet not found.</div></Layout>;
  }

  const portrait = pet.portraitUrl ?? `/assets/pets/${pet.family.toLowerCase()}.png`;

  return (
    <Layout background="/assets/backgrounds/pet_details.png">
      <div className="page-panel pet-panel">
        <div className="pet-header">
          <div className="pet-portrait-wrap">
            <div className="pet-portrait-circle">
              <img
                src={portrait}
                alt={pet.name}
                onError={(e) => (e.target as HTMLImageElement).src = '/assets/pets/beast.png'}
              />
            </div>
          </div>
          <div className="pet-header-text">
            <h1 className="pet-name">{pet.name}</h1>
            <p className="pet-meta">
              {pet.family} • <span className={`pet-rarity pet-rarity-${pet.rarity.toLowerCase()}`}>{pet.rarity}</span>
            </p>
            <p className="pet-desc">
              {pet.flavorText ?? 'A mysterious creature with untapped potential.'}
            </p>
          </div>
        </div>

        <div className="pet-body">
          <section className="pet-section">
            <h2>Stats</h2>
            <div className="space-y-2 mt-4 text-sm text-slate-300">
              <div className="flex justify-between"><span>Health</span> <span className="text-green-300">{pet.health}</span></div>
              <div className="flex justify-between"><span>Power</span> <span className="text-amber-300">{pet.power}</span></div>
              <div className="flex justify-between"><span>Speed</span> <span className="text-blue-300">{pet.speed}</span></div>
            </div>
          </section>

          <section className="pet-section">
            <h2>Abilities</h2>
            <div className="grid grid-cols-2 gap-2 mt-2">
              {(pet.abilities || []).map(ab => (
                <div key={ab.id} className="p-2 bg-slate-900/50 rounded border border-slate-700/50 text-xs">
                  <div className="font-semibold text-slate-200">{ab.name}</div>
                  <div className="text-slate-500 mt-1">{ab.description || 'No description'}</div>
                </div>
              ))}
              {(!pet.abilities || pet.abilities.length === 0) && <p className="text-xs text-slate-500">No abilities discovered.</p>}
            </div>
          </section>
        </div>
      </div>
    </Layout>
  );
};
