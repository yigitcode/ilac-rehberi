/* Search layer — Fuse.js + Turkish character normalization. */
(function (global) {
  'use strict';

  const FUSE_OPTIONS = {
    includeScore: true,
    threshold: 0.35,
    minMatchCharLength: 2,
    ignoreLocation: true,
    keys: [
      { name: 'tradeNameN',        weight: 1.0 },
      { name: 'otherTradeNamesN',  weight: 0.95 },
      { name: 'activeIngredientN', weight: 0.85 },
      { name: 'atc',               weight: 0.4 },
      { name: 'indicationsN',      weight: 0.3 },
    ],
  };

  // Map Turkish (and a few common diacritics) → ASCII for resilient matching.
  const TR_MAP = {
    'ı': 'i', 'İ': 'i', 'I': 'i',
    'ş': 's', 'Ş': 's',
    'ç': 'c', 'Ç': 'c',
    'ğ': 'g', 'Ğ': 'g',
    'ü': 'u', 'Ü': 'u',
    'ö': 'o', 'Ö': 'o',
    'â': 'a', 'Â': 'a',
    'î': 'i', 'Î': 'i',
    'û': 'u', 'Û': 'u',
  };

  function normalize(text) {
    if (!text) return '';
    let out = '';
    const str = String(text);
    for (let i = 0; i < str.length; i++) {
      const ch = str[i];
      out += (TR_MAP[ch] !== undefined ? TR_MAP[ch] : ch).toLowerCase();
    }
    return out;
  }

  function buildIndex(drugs) {
    const enriched = drugs.map((d) => ({
      ...d,
      tradeNameN: normalize(d.tradeName),
      otherTradeNamesN: (d.otherTradeNames || []).map(normalize).join(' '),
      activeIngredientN: normalize(d.activeIngredient),
      indicationsN: (d.indications || []).map(normalize).join(' '),
    }));
    return new global.Fuse(enriched, FUSE_OPTIONS);
  }

  /**
   * Run a query against the prebuilt Fuse index.
   * Returns up to `limit` raw drug objects (without the *N fields).
   */
  function search(fuse, query, limit) {
    const q = normalize(query).trim();
    if (q.length < 2) return [];
    // Pull more than requested so verified picks survive the post-sort cutoff.
    const raw = fuse.search(q, { limit: (limit || 30) * 2 });
    raw.sort((a, b) => {
      const av = a.item.verified === true ? 0 : 1;
      const bv = b.item.verified === true ? 0 : 1;
      if (av !== bv) return av - bv;            // verified first
      return (a.score || 0) - (b.score || 0);   // then by Fuse score
    });
    return raw.slice(0, limit || 30).map((r) => stripNorm(r.item));
  }

  function stripNorm(drug) {
    const { tradeNameN, otherTradeNamesN, activeIngredientN, indicationsN, ...rest } = drug;
    return rest;
  }

  global.IlacSearch = { buildIndex, search, normalize };
})(window);
