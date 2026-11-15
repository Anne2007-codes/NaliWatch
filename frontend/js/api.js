// HTTP client for the FastAPI backend. Token lives in localStorage.
(function (g) {
  const KEY_T = "NW_TOKEN", KEY_U = "NW_USER";
  function origin() {
    if (g.NW_API) return g.NW_API.replace(/\/$/, "");
    const { protocol, hostname, port } = location;
    if (port === "8000" || /\/docs$/.test(location.pathname)) return "";
    return "http://localhost:8000";
  }
  function headers(extra) {
    const h = Object.assign({ Accept: "application/json" }, extra || {});
    if (g.token) h.Authorization = "Bearer " + g.token;
    return h;
  }
  async function parse(res) {
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = { detail: text }; }
    if (!res.ok) {
      const d = data && data.detail;
      const msg = typeof d === "string" ? d : (Array.isArray(d) ? d.map(x => x.msg || x).join("; ") : (res.statusText || "request failed"));
      const err = new Error(msg);
      err.status = res.status;
      err.body = data;
      throw err;
    }
    return data;
  }
  async function req(method, path, body, isForm) {
    const opt = { method, headers: headers(isForm ? {} : (body ? { "Content-Type": "application/json" } : {})) };
    if (isForm) opt.body = body;
    else if (body !== undefined) opt.body = JSON.stringify(body);
    return parse(await fetch(origin() + path, opt));
  }
  g.api = {
    origin,
    setSession(tok, user) {
      g.token = tok || "";
      g.me = user || null;
      if (tok) localStorage.setItem(KEY_T, tok); else localStorage.removeItem(KEY_T);
      if (user) localStorage.setItem(KEY_U, JSON.stringify(user)); else localStorage.removeItem(KEY_U);
    },
    get: (path) => req("GET", path),
    post: (path, body) => req("POST", path, body),
    patch: (path, body) => req("PATCH", path, body),
    postForm: (path, fd) => req("POST", path, fd, true),
    requestOtp: (phone) => req("POST", "/auth/otp/request", { phone }),
    verifyOtp: (phone, otp, extra) => req("POST", "/auth/otp/verify", Object.assign({ phone, otp }, extra || {})),
    me: () => req("GET", "/auth/me"),
  };
})(window);