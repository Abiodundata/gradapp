import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  api,
  clearSession,
  getRefreshToken,
  getSavedUser,
  onSessionExpired,
  saveSession,
  saveUser,
} from "./api";

/* ------------------------------------------------------------------ auth */

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getSavedUser());
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    onSessionExpired(() => {
      setUser(null);
      setSessionExpired(true);
    });
  }, []);

  // Refresh the stored user (e.g. is_staff may have changed).
  useEffect(() => {
    if (!user) return;
    api("/auth/me/")
      .then((fresh) => { saveUser(fresh); setUser(fresh); })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (username, password) => {
    const data = await api("/auth/login/", { method: "POST", body: { username, password } });
    saveSession(data);
    setSessionExpired(false);
    setUser(data.user);
  }, []);

  const register = useCallback(async (form) => {
    await api("/auth/register/", { method: "POST", body: form });
    await login(form.username, form.password);
  }, [login]);

  const logout = useCallback(async () => {
    const refresh = getRefreshToken();
    if (refresh) {
      try {
        await api("/auth/logout/", { method: "POST", body: { refresh }, retry: false });
      } catch {
        /* the token may already be expired; local sign-out still happens */
      }
    }
    clearSession();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, login, register, logout, sessionExpired }),
    [user, login, register, logout, sessionExpired],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);

/* --------------------------------------------------------- saved programs */

const SavedContext = createContext(null);

/** Keeps a map of programId -> savedProgramId so any screen can show and toggle saved state. */
export function SavedProvider({ children }) {
  const [saved, setSaved] = useState({});
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    try {
      const data = await api("/saved-programs/?page_size=100");
      setSaved(Object.fromEntries(data.results.map((entry) => [entry.program.id, entry.id])));
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const toggle = useCallback(async (programId) => {
    setError("");
    try {
      if (saved[programId]) {
        await api(`/saved-programs/${saved[programId]}/`, { method: "DELETE" });
        setSaved((current) => {
          const next = { ...current };
          delete next[programId];
          return next;
        });
      } else {
        const entry = await api("/saved-programs/", { method: "POST", body: { program_id: programId } });
        setSaved((current) => ({ ...current, [programId]: entry.id }));
      }
    } catch (err) {
      setError(err.message);
      reload();
    }
  }, [saved, reload]);

  const value = useMemo(
    () => ({ isSaved: (id) => Boolean(saved[id]), toggle, reload, count: Object.keys(saved).length, error }),
    [saved, toggle, reload, error],
  );
  return <SavedContext.Provider value={value}>{children}</SavedContext.Provider>;
}

export const useSaved = () => useContext(SavedContext);

/* ------------------------------------------------------------- compare */

const CompareContext = createContext(null);
const COMPARE_KEY = "gradapp_compare";
export const MAX_COMPARE = 4;

function readCompare() {
  try {
    const value = JSON.parse(localStorage.getItem(COMPARE_KEY));
    return Array.isArray(value) ? value.slice(0, MAX_COMPARE) : [];
  } catch {
    return [];
  }
}

export function CompareProvider({ children }) {
  const [items, setItems] = useState(readCompare);

  useEffect(() => {
    try { localStorage.setItem(COMPARE_KEY, JSON.stringify(items)); } catch { /* storage unavailable */ }
  }, [items]);

  const toggle = useCallback((program) => {
    setItems((current) => {
      if (current.some((item) => item.id === program.id)) return current.filter((item) => item.id !== program.id);
      if (current.length >= MAX_COMPARE) return current;
      return [...current, { id: program.id, name: program.name, university: program.university?.name || "" }];
    });
  }, []);

  const remove = useCallback((id) => setItems((current) => current.filter((item) => item.id !== id)), []);
  const clear = useCallback(() => setItems([]), []);

  const value = useMemo(
    () => ({ items, toggle, remove, clear, has: (id) => items.some((item) => item.id === id), full: items.length >= MAX_COMPARE }),
    [items, toggle, remove, clear],
  );
  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}

export const useCompare = () => useContext(CompareContext);
