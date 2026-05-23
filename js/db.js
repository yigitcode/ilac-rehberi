/* IndexedDB layer (uses vendored `idb` UMD global). */
(function (global) {
  'use strict';

  const DB_NAME = 'ilac-rehberi-v2';
  const DB_VERSION = 1;
  const STORE = 'drugs';
  const META_KEY_VERSION = 'ilac-rehberi/data-version';

  let dbPromise = null;
  let cachedDrugs = null;

  function openDatabase() {
    if (!dbPromise) {
      dbPromise = global.idb.openDB(DB_NAME, DB_VERSION, {
        upgrade(db) {
          if (!db.objectStoreNames.contains(STORE)) {
            db.createObjectStore(STORE, { keyPath: 'id' });
          }
        },
      });
    }
    return dbPromise;
  }

  async function fetchJson(path) {
    const res = await fetch(path, { cache: 'no-store' });
    if (!res.ok) throw new Error(path + ' alınamadı: HTTP ' + res.status);
    return res.json();
  }

  async function loadFromNetwork() {
    const [curated, lite, enriched] = await Promise.all([
      fetchJson('data/ilaclar.json'),
      fetchJson('data/ilaclar-lite.json').catch((err) => {
        console.warn('Lite list yüklenemedi:', err);
        return null;
      }),
      fetchJson('data/ilaclar-enriched.json').catch(() => null),
    ]);

    const curatedDrugs = (curated.drugs || []).map((d) => ({ ...d, verified: true }));
    const liteDrugs    = lite ? (lite.drugs || []) : [];
    const enrichedDrugs = enriched ? (enriched.drugs || []) : [];

    // Enriched (AI-generated) records override lite records for the same id.
    const enrichedById = new Map(enrichedDrugs.map((d) => [d.id, d]));
    const liteFinal = liteDrugs.map((d) => enrichedById.has(d.id) ? enrichedById.get(d.id) : d);

    // Apply locally-stored verification state (set via UI).
    const verifiedSet = readVerifiedSet();
    const apply = (d) => verifiedSet.has(d.id) ? { ...d, verified: true, userVerified: true } : d;

    return {
      version: (curated.version || '0') + '|' + (lite ? lite.version : 'none') + '|' + (enriched ? enriched.version : 'none'),
      drugs: curatedDrugs.map(apply).concat(liteFinal.map(apply)),
    };
  }

  const VERIFIED_KEY = 'ilac-rehberi/verified-ids';

  function readVerifiedSet() {
    try {
      const raw = localStorage.getItem(VERIFIED_KEY);
      return new Set(raw ? JSON.parse(raw) : []);
    } catch (_) { return new Set(); }
  }

  function writeVerifiedSet(set) {
    try {
      localStorage.setItem(VERIFIED_KEY, JSON.stringify([...set]));
    } catch (_) { /* ignore */ }
  }

  async function markVerified(id) {
    const set = readVerifiedSet();
    set.add(id);
    writeVerifiedSet(set);
    cachedDrugs = null;  // force refresh on next call
    const db = await openDatabase();
    const drug = await db.get(STORE, id);
    if (drug) {
      drug.verified = true;
      drug.userVerified = true;
      await db.put(STORE, drug);
    }
  }

  async function unmarkVerified(id) {
    const set = readVerifiedSet();
    set.delete(id);
    writeVerifiedSet(set);
    cachedDrugs = null;
  }

  async function importAll(payload) {
    const db = await openDatabase();
    const tx = db.transaction(STORE, 'readwrite');
    tx.store.clear();
    for (const drug of payload.drugs) {
      tx.store.put(drug);
    }
    await tx.done;
    try {
      localStorage.setItem(META_KEY_VERSION, payload.version || 'unknown');
    } catch (_) { /* private mode: ignore */ }
  }

  /**
   * Returns all drugs as an array. First call may fetch + import.
   * Subsequent calls return a cached copy (so search is fast).
   */
  async function getAllDrugs() {
    if (cachedDrugs) return cachedDrugs;

    const db = await openDatabase();
    let drugs = await db.getAll(STORE);

    const storedVersion = (() => {
      try { return localStorage.getItem(META_KEY_VERSION); } catch (_) { return null; }
    })();

    if (drugs.length === 0 || !storedVersion) {
      const payload = await loadFromNetwork();
      await importAll(payload);
      drugs = await db.getAll(STORE);
    } else {
      // Background freshness check — non-blocking.
      loadFromNetwork()
        .then(async (payload) => {
          if (payload.version && payload.version !== storedVersion) {
            await importAll(payload);
            cachedDrugs = payload.drugs;
            global.dispatchEvent(new CustomEvent('drugs:updated'));
          }
        })
        .catch(() => { /* offline or fetch failed — silently keep cache */ });
    }

    cachedDrugs = drugs;
    return drugs;
  }

  async function getDrugById(id) {
    const db = await openDatabase();
    return db.get(STORE, id);
  }

  global.IlacDB = { getAllDrugs, getDrugById, markVerified, unmarkVerified };
})(window);
