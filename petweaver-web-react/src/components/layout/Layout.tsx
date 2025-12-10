import { NavLink, useLocation } from 'react-router-dom';
import './layout.css';

const navLinkBase =
  'px-3 py-2 text-xs md:text-sm font-medium transition-colors relative rounded-md';
const activeEmber =
  'text-ember-light bg-bg-panel/70';

const links = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/pets', label: 'Pet Codex' },
  { to: '/simulator', label: 'Simulator' },
  { to: '/genetic', label: 'Optimizer' },
  { to: '/encounters', label: 'Encounters' },
  { to: '/server', label: 'Server' },
  { to: '/logs', label: 'Logs' },
  { to: '/settings', label: 'Settings' },
];

const bgByPath: Record<string, string> = {
  '/': '/assets/backgrounds/dashboard.png',
  '/dashboard': '/assets/backgrounds/dashboard.png',
  '/pets': '/assets/backgrounds/codex.png',
  '/codex': '/assets/backgrounds/codex.png',
  '/simulator': '/assets/backgrounds/simulator.png',
  '/genetic': '/assets/backgrounds/genetic.png',
  '/encounters': '/assets/backgrounds/encounters.png',
  '/server': '/assets/backgrounds/server.png',
  '/logs': '/assets/backgrounds/logs.png',
  '/settings': '/assets/backgrounds/settings.png',
};

// Fallback logic for dynamic routes like /pets/:id
const getBackground = (pathname: string): string => {
  // 1. Exact match
  if (bgByPath[pathname]) return bgByPath[pathname];

  // 2. Prefix match for specific sections
  if (pathname.startsWith('/pets/')) return '/assets/backgrounds/pet_details.png';

  // 3. Default fallback
  return '/assets/backgrounds/dashboard.png';
};

export const Layout: React.FC<{ children: React.ReactNode; background?: string }> = ({
  children,
  background: bgOverride,
}) => {
  const { pathname } = useLocation();
  const background = bgOverride || getBackground(pathname);

  return (
    <div
      className="app-shell"
      style={{ backgroundImage: `url(${background})` }}
    >
      <div className="ambient-glow-overlay" />
      <div className="app-backdrop">
        <div className="app-content">

          {/* Header embedded in content flow */}
          <header className="mb-6 pb-4">
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-full bg-gradient-to-tr from-ember-deep via-ember-light to-arcane-mid shadow-ember flex items-center justify-center">
                    <span className="text-xl">🐾</span>
                  </div>
                  <div>
                    <div className="font-title tracking-[0.15em] text-[10px] text-ember-light uppercase">
                      PetWeaver
                    </div>
                    <div className="text-xs text-slate-200">
                      Arcane Pet Battle Lab
                    </div>
                  </div>
                </div>
              </div>

              <nav className="flex flex-wrap items-center gap-2 text-sm bg-bg-panel/40 backdrop-blur-sm p-1 rounded-lg">
                {links.map((link) => (
                  <NavLink
                    key={link.to}
                    to={link.to}
                    className={({ isActive }) =>
                      [
                        navLinkBase,
                        isActive
                          ? activeEmber
                          : 'text-slate-300 hover:text-white hover:bg-white/5',
                      ].join(' ')
                    }
                  >
                    {link.label}
                  </NavLink>
                ))}
              </nav>
            </div>
          </header>

          <main className="flex-1 relative">
            {children}
          </main>

          <footer className="mt-8 pt-4 text-xs text-slate-500 flex justify-between">
            <span>PetWeaver • Arcane Pet Battle Intelligence</span>
            <span className="text-slate-600">
              Backend: <span className="text-amber-300">Not connected</span>
            </span>
          </footer>

        </div>
      </div>
    </div>
  );
};
