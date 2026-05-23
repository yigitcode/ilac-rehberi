/* App bootstrap: load data, wire up search input + clicks + history. */
(function () {
  'use strict';

  let fuse = null;
  let allDrugs = [];

  function debounce(fn, wait) {
    let timer = null;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  async function init() {
    const ui = window.IlacUI;
    ui.setStatus('Veri yükleniyor…');

    try {
      allDrugs = await window.IlacDB.getAllDrugs();
    } catch (err) {
      console.error('Veri yüklenemedi', err);
      ui.setStatus('Veri yüklenemedi — bağlantınızı kontrol edin');
      return;
    }

    fuse = window.IlacSearch.buildIndex(allDrugs);
    ui.renderAlphabetical(allDrugs);

    wireSearch();
    wireResultClicks();
    wireBackNavigation();
    wireServiceWorker();
    handleInitialRoute();
  }

  function wireSearch() {
    const input = window.IlacUI.els.searchInput || document.getElementById('search-input');
    const onInput = debounce(() => {
      const q = input.value || '';
      if (!fuse) return;
      if (q.trim().length < 2) {
        window.IlacUI.renderAlphabetical(allDrugs);
        return;
      }
      const matches = window.IlacSearch.search(fuse, q, 100);
      window.IlacUI.renderResults(matches, q);
    }, 150);
    input.addEventListener('input', onInput);
  }

  function wireResultClicks() {
    document.getElementById('results').addEventListener('click', async (e) => {
      const toggle = e.target.closest('[data-action="toggle-lite"]');
      if (toggle) {
        window.IlacUI.toggleLite();
        window.IlacUI.renderAlphabetical(allDrugs);
        return;
      }
      const item = e.target.closest('.result-item');
      if (!item) return;
      const id = item.dataset.id;
      const drug = await window.IlacDB.getDrugById(id);
      if (drug) {
        history.pushState({ id }, '', '#' + encodeURIComponent(id));
        window.IlacUI.showDetail(drug);
      }
    });

    document.getElementById('detail-view').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-action="verify"], [data-action="unverify"]');
      if (!btn) return;
      const id = btn.dataset.id;
      if (btn.dataset.action === 'verify') {
        await window.IlacDB.markVerified(id);
      } else {
        await window.IlacDB.unmarkVerified(id);
      }
      allDrugs = await window.IlacDB.getAllDrugs();
      const drug = await window.IlacDB.getDrugById(id);
      if (drug) window.IlacUI.showDetail(drug);
    });
  }

  function wireBackNavigation() {
    document.getElementById('back-btn').addEventListener('click', () => {
      history.back();
    });
    window.addEventListener('popstate', async (e) => {
      const id = e.state && e.state.id;
      if (id) {
        const drug = await window.IlacDB.getDrugById(id);
        if (drug) { window.IlacUI.showDetail(drug); return; }
      }
      window.IlacUI.showSearch();
    });
  }

  async function handleInitialRoute() {
    const hash = decodeURIComponent((location.hash || '').replace(/^#/, ''));
    if (hash) {
      const drug = await window.IlacDB.getDrugById(hash);
      if (drug) {
        history.replaceState({ id: hash }, '', '#' + encodeURIComponent(hash));
        window.IlacUI.showDetail(drug);
        return;
      }
    }
    window.IlacUI.showSearch();
  }

  function wireServiceWorker() {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('service-worker.js')
          .catch((err) => console.warn('SW kaydı başarısız:', err));
      });
    }
  }

  window.addEventListener('drugs:updated', async () => {
    allDrugs = await window.IlacDB.getAllDrugs();
    fuse = window.IlacSearch.buildIndex(allDrugs);
    const input = document.getElementById('search-input');
    if (!input.value || input.value.trim().length < 2) {
      window.IlacUI.renderAlphabetical(allDrugs);
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
