import axios from "axios";

// Empty in the Docker build: the app is served from the same origin as /api (nginx proxy).
const BASE = process.env.REACT_APP_BACKEND_URL || "";
export const API = `${BASE}/api`;

export const assetUrl = (path) => (path ? `${BASE}${path}` : null);

export const wsUrl = (channel) =>
  `${(BASE || window.location.origin).replace(/^http/, "ws")}/api/ws/${channel}`;

const tokenKey = (area) => `ss_session_${area}`;
export const getToken = (area) => localStorage.getItem(tokenKey(area));
export const setToken = (area, token) => localStorage.setItem(tokenKey(area), token);
export const clearToken = (area) => localStorage.removeItem(tokenKey(area));

function adminClient(area) {
  const inst = axios.create({ baseURL: API });
  inst.interceptors.request.use((c) => {
    const t = getToken(area);
    if (t) c.headers.Authorization = `Bearer ${t}`;
    return c;
  });
  inst.interceptors.response.use(
    (r) => r,
    (e) => {
      if (e.response?.status === 401) {
        clearToken(area);
        window.dispatchEvent(new CustomEvent("ss-locked", { detail: area }));
      }
      return Promise.reject(e);
    },
  );
  return inst;
}

export const registerApi = adminClient("register");
export const bibleApi = adminClient("bible");
export const settingsApi = adminClient("settings");

export function errMsg(e, fallback = "Something went wrong.") {
  const d = e?.response?.data?.detail;
  if (!d) return e?.response ? fallback : "Cannot reach the server. Check the connection.";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return d.msg || String(d);
}

export const todayLocal = () => new Date().toLocaleDateString("en-CA");

export const formatDate = (iso) =>
  iso
    ? new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
        weekday: "short", month: "short", day: "numeric", year: "numeric",
      })
    : "";

export const formatMoney = (n, currency) =>
  n == null
    ? null
    : `${currency}${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const formatCount = (n) => (n == null ? null : Number(n).toLocaleString());
