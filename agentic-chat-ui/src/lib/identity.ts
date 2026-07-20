const USER_ID_KEY = "ingest-console.user_id";
const SESSION_ID_PREFIX = "ingest-console.session_id.";
// Single active "conversation slot" for this simple UI — swap this for a
// real conversation switcher key if the app grows multiple threads.
const ACTIVE_CONVERSATION = "default";

function uuid(): string {
  if ("randomUUID" in crypto) return crypto.randomUUID();
  // Fallback for older browsers.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getUserId(): string {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = uuid();
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

export function getSessionId(): string {
  const key = SESSION_ID_PREFIX + ACTIVE_CONVERSATION;
  let id = localStorage.getItem(key);
  if (!id) {
    id = uuid();
    localStorage.setItem(key, id);
  }
  return id;
}

/** Starts a brand-new conversation (new session_id) while keeping the same user_id. */
export function resetSessionId(): string {
  const key = SESSION_ID_PREFIX + ACTIVE_CONVERSATION;
  const id = uuid();
  localStorage.setItem(key, id);
  return id;
}
