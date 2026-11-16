import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth, useCompare, useSaved } from "../context";
import { Icon } from "../icons";
import { Alert } from "./ui";

const NAV = [
  { to: "/", label: "Discover", end: true },
  { to: "/recommendations", label: "For you" },
  { to: "/faculty", label: "Faculty" },
  { to: "/funding", label: "Funding" },
  { to: "/saved", label: "Saved" },
  { to: "/deadlines", label: "Deadlines" },
  { to: "/ask", label: "Ask AI" },
];

function CompareTray() {
  const { items, remove, clear } = useCompare();
  const navigate = useNavigate();
  const location = useLocation();
  if (!items.length || location.pathname === "/compare" || location.pathname.startsWith("/ask")) return null;
  return (
    <aside className="compare-tray" aria-label="Programs selected for comparison">
      <div className="compare-items">
        <strong>Compare ({items.length}/4)</strong>
        {items.map((item) => (
          <span key={item.id} className="compare-chip">
            {item.name}<small>{item.university}</small>
            <button onClick={() => remove(item.id)} aria-label={`Remove ${item.name} from comparison`}><Icon name="close" size={14} /></button>
          </span>
        ))}
      </div>
      <div className="compare-tray-actions">
        <button className="secondary" onClick={clear}>Clear</button>
        <button className="primary" disabled={items.length < 2} onClick={() => navigate("/compare")}>
          Compare now<Icon name="arrow" size={17} />
        </button>
      </div>
    </aside>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { count, error: savedError } = useSaved();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const name = user?.first_name || user?.username || "Student";

  useEffect(() => { setMenuOpen(false); window.scrollTo?.(0, 0); }, [location.pathname]);

  const links = [...NAV, ...(user?.is_staff ? [{ to: "/admin/users", label: "Users" }] : [])];

  return (
    <div className="app-shell">
      <header>
        <Link to="/" className="brand"><span className="brand-mark"><Icon name="school" /></span>GradApp</Link>
        <nav className={menuOpen ? "open" : ""} aria-label="Main">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className={({ isActive }) => (isActive ? "nav-active" : "")}>
              {link.label}
              {link.to === "/saved" && count > 0 && <span className="nav-count">{count}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="user-menu">
          <Link to="/profile" className="profile-link" title="My profile">
            <span className="avatar">{name.charAt(0).toUpperCase()}</span>
            <span>{name}</span>
          </Link>
          <button className="icon-button" onClick={logout} title="Sign out" aria-label="Sign out"><Icon name="logout" /></button>
          <button className="icon-button menu-toggle" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle menu" aria-expanded={menuOpen}>
            <Icon name={menuOpen ? "close" : "menu"} />
          </button>
        </div>
      </header>
      <main className="main">
        {savedError && <div className="page"><Alert>{savedError}</Alert></div>}
        <Outlet />
      </main>
      <CompareTray />
      <footer>
        <div className="brand"><span className="brand-mark"><Icon name="school" /></span>GradApp</div>
        <p>Making graduate program discovery simpler. Always confirm details on official university websites.</p>
        <span>DevCave</span>
      </footer>
    </div>
  );
}
