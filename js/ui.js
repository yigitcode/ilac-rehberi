/* DOM rendering for search results and drug detail. */
(function (global) {
  'use strict';

  const els = {
    searchView:    document.getElementById('search-view'),
    detailView:    document.getElementById('detail-view'),
    detailContent: document.getElementById('detail-content'),
    results:       document.getElementById('results'),
    status:        document.getElementById('search-status'),
    backBtn:       document.getElementById('back-btn'),
    title:         document.getElementById('app-title'),
  };

  function esc(s) {
    if (s === undefined || s === null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function setStatus(msg) {
    els.status.textContent = msg || '';
  }

  function makeResultItem(d) {
    const li = document.createElement('li');
    li.className = 'result-item' + (d.verified === false ? ' result-lite' : '');
    li.setAttribute('role', 'button');
    li.dataset.id = d.id;
    const others = (d.otherTradeNames && d.otherTradeNames.length)
      ? `<div class="result-aliases">ayrıca: ${esc(d.otherTradeNames.join(', '))}</div>`
      : '';
    const meta = d.verified === false
      ? `<span class="lite-badge">temel info</span> ${esc(d.atc || '')}${d.manufacturer ? ' &middot; ' + esc(d.manufacturer) : ''}`
      : `${esc(d.form || '')}${d.strength ? ' &middot; ' + esc(d.strength) : ''}`;
    li.innerHTML = `
      <div class="result-name">${esc(d.tradeName)}</div>
      <div class="result-ingredient">${esc(d.activeIngredient)}</div>
      <div class="result-meta">${meta}</div>
      ${others}
    `;
    return li;
  }

  function renderResults(drugs, query) {
    els.results.innerHTML = '';
    if (drugs.length === 0) {
      setStatus(`"${query}" için sonuç bulunamadı`);
      return;
    }
    setStatus(`${drugs.length} sonuç`);
    const frag = document.createDocumentFragment();
    for (const d of drugs) frag.appendChild(makeResultItem(d));
    els.results.appendChild(frag);
  }

  function firstLetter(name) {
    if (!name) return '#';
    const ch = String(name).trim().charAt(0).toLocaleUpperCase('tr-TR');
    return /[A-ZÇĞİÖŞÜ]/.test(ch) ? ch : '#';
  }

  function appendAlphabetical(frag, drugs) {
    const sorted = [...drugs].sort((a, b) =>
      (a.tradeName || '').localeCompare(b.tradeName || '', 'tr-TR', { sensitivity: 'base' })
    );
    let lastLetter = null;
    for (const d of sorted) {
      const letter = firstLetter(d.tradeName);
      if (letter !== lastLetter) {
        const header = document.createElement('li');
        header.className = 'letter-header';
        header.textContent = letter;
        header.setAttribute('aria-hidden', 'true');
        frag.appendChild(header);
        lastLetter = letter;
      }
      frag.appendChild(makeResultItem(d));
    }
  }

  let _liteExpanded = false;

  function renderAlphabetical(drugs) {
    els.results.innerHTML = '';
    if (!drugs || drugs.length === 0) {
      setStatus('İlaç bulunamadı');
      return;
    }
    const verified = drugs.filter((d) => d.verified !== false);
    const lite     = drugs.filter((d) => d.verified === false);

    els.status.innerHTML = `Detaylı: ${verified.length} ilaç${lite.length ? ` &middot; TİTCK temel: ${lite.length}` : ''}`;

    const frag = document.createDocumentFragment();
    appendAlphabetical(frag, verified);

    if (lite.length > 0) {
      const toggle = document.createElement('li');
      toggle.className = 'results-toggle';
      toggle.setAttribute('role', 'button');
      toggle.dataset.action = 'toggle-lite';
      toggle.textContent = _liteExpanded
        ? `TİTCK listesini gizle (${lite.length})`
        : `TİTCK listesini göster (${lite.length} ilaç — sadece temel bilgi)`;
      frag.appendChild(toggle);

      if (_liteExpanded) {
        appendAlphabetical(frag, lite);
      }
    }

    els.results.appendChild(frag);
  }

  function toggleLite() {
    _liteExpanded = !_liteExpanded;
  }

  function renderList(items) {
    if (!items || items.length === 0) return '<p><em>—</em></p>';
    return '<ul>' + items.map((x) => `<li>${esc(x)}</li>`).join('') + '</ul>';
  }

  function renderDosage(dose) {
    if (!dose) return '<p><em>—</em></p>';
    const labels = {
      adult:     'Erişkin',
      pediatric: 'Pediatrik',
      renal:     'Renal yetmezlik',
      hepatic:   'Hepatik yetmezlik',
    };
    let html = '<dl class="dose-grid">';
    for (const key of Object.keys(labels)) {
      if (dose[key]) {
        html += `<dt>${labels[key]}:</dt><dd>${esc(dose[key])}</dd>`;
      }
    }
    html += '</dl>';
    return html;
  }

  function renderSideEffects(se) {
    if (!se) return '<p><em>—</em></p>';
    let html = '';
    if (se.common && se.common.length) {
      html += '<p><strong>Sık:</strong></p>' + renderList(se.common);
    }
    if (se.serious && se.serious.length) {
      html += '<p><strong>Ciddi:</strong></p>' + renderList(se.serious);
    }
    return html || '<p><em>—</em></p>';
  }

  function renderInteractions(items) {
    if (!items || items.length === 0) return '<p><em>—</em></p>';
    return items.map((x) => `
      <div class="interaction-item">
        <div class="interaction-drug">${esc(x.drug)}</div>
        <div>${esc(x.note)}</div>
      </div>
    `).join('');
  }

  function section(title, html, danger) {
    return `
      <section class="detail-section${danger ? ' section-danger' : ''}">
        <h3>${esc(title)}</h3>
        ${html}
      </section>
    `;
  }

  function renderDetail(d) {
    if (d.verified === false) {
      return renderLiteDetail(d);
    }
    const aliasesBlock = (d.otherTradeNames && d.otherTradeNames.length)
      ? `<div class="detail-aliases"><strong>Diğer ticari adlar:</strong> ${esc(d.otherTradeNames.join(', '))}</div>`
      : '';
    const verifyBlock = (d.aiGenerated && !d.userVerified) ? `
      <div class="ai-banner">
        <strong>AI tarafından üretildi</strong> — Bu kayıt Claude tarafından otomatik özetlenmiştir.
        KÜB ile karşılaştırarak doğrulamadan klinik karar için kullanmayın.
        <button class="verify-btn" data-action="verify" data-id="${esc(d.id)}">KÜB ile karşılaştırdım, doğrula</button>
      </div>` : '';
    const userVerifiedBlock = d.userVerified ? `
      <div class="verified-banner">
        ✓ Doğrulandı (lokal olarak işaretli)
        <button class="verify-btn ghost" data-action="unverify" data-id="${esc(d.id)}">geri al</button>
      </div>` : '';
    const html = `
      <h2>${esc(d.tradeName)}</h2>
      <div class="detail-subtitle">
        ${esc(d.activeIngredient)}${d.atc ? ' &middot; ATC ' + esc(d.atc) : ''}<br>
        ${esc(d.form || '')}${d.strength ? ' &middot; ' + esc(d.strength) : ''}
      </div>
      ${aliasesBlock}
      ${verifyBlock}
      ${userVerifiedBlock}

      ${section('Endikasyonlar', renderList(d.indications))}
      ${section('Kontrendikasyonlar', renderList(d.contraindications), true)}
      ${section('Doz', renderDosage(d.dosage))}
      ${section('Yan etkiler', renderSideEffects(d.sideEffects))}
      ${section('İlaç etkileşimleri', renderInteractions(d.interactions))}
      ${d.antidote ? section('Antidot / Aşırı doz', `<p>${esc(d.antidote)}</p>`, true) : ''}
      ${d.pregnancy ? section('Gebelik', `<p>${esc(d.pregnancy)}</p>`) : ''}
      ${d.breastfeeding ? section('Emzirme', `<p>${esc(d.breastfeeding)}</p>`) : ''}
      ${d.storage ? section('Saklama', `<p>${esc(d.storage)}</p>`) : ''}
      ${d.notes ? section('Notlar', `<p>${esc(d.notes)}</p>`) : ''}

      <div class="source-info">
        <strong>Kaynak:</strong> ${esc(d.source || 'Belirtilmemiş')}<br>
        <em>Bu özet manuel hazırlanmıştır ve doğrulanmamış test verisidir. Klinik karar için resmi KÜB'e (titck.gov.tr) başvurunuz.</em>
      </div>
    `;
    els.detailContent.innerHTML = html;
  }

  function renderLiteDetail(d) {
    const titckSearch = 'https://www.titck.gov.tr/kubkt?searchTerm=' + encodeURIComponent(d.tradeName);
    const html = `
      <h2>${esc(d.tradeName)}</h2>
      <div class="detail-subtitle">
        ${esc(d.activeIngredient)}${d.atc ? ' &middot; ATC ' + esc(d.atc) : ''}
      </div>

      <div class="lite-warning">
        <strong>Temel info kaydı</strong> — Bu ilaç için KÜB özeti henüz hazırlanmadı.
        Klinik karar için resmi KÜB belgesine başvurmanız gerekir.
      </div>

      ${section('Mevcut bilgi', `
        <dl class="dose-grid">
          <dt>Ticari ad:</dt><dd>${esc(d.tradeName)}</dd>
          <dt>Etken madde:</dt><dd>${esc(d.activeIngredient)}</dd>
          ${d.atc ? `<dt>ATC kodu:</dt><dd>${esc(d.atc)}</dd>` : ''}
          ${d.manufacturer ? `<dt>Firma:</dt><dd>${esc(d.manufacturer)}</dd>` : ''}
          ${d.barkod ? `<dt>Barkod:</dt><dd>${esc(d.barkod)}</dd>` : ''}
        </dl>
      `)}

      ${section('Resmi KÜB / Kullanma Talimatı', `
        <p>Detaylı bilgi için TİTCK'in resmi sayfasında bu ilacı arayın:</p>
        <p><a href="${titckSearch}" target="_blank" rel="noopener">TİTCK KÜB araması →</a></p>
      `)}

      <div class="source-info">
        <strong>Kaynak:</strong> ${esc(d.source || '')}<br>
        <em>Bu kayıt sadece ilaç adı, etken madde ve firma bilgisi içerir. Doz, kontrendikasyon, etkileşim ve antidot bilgisi için resmi KÜB belgesine başvurunuz.</em>
      </div>
    `;
    els.detailContent.innerHTML = html;
  }

  function showSearch() {
    els.detailView.hidden = true;
    els.searchView.hidden = false;
    els.backBtn.hidden = true;
    els.title.textContent = 'İlaç Rehberi';
    window.scrollTo(0, 0);
  }

  function showDetail(drug) {
    renderDetail(drug);
    els.searchView.hidden = true;
    els.detailView.hidden = false;
    els.backBtn.hidden = false;
    els.title.textContent = drug.tradeName;
    window.scrollTo(0, 0);
  }

  global.IlacUI = {
    els,
    setStatus,
    renderResults,
    renderAlphabetical,
    toggleLite,
    showSearch,
    showDetail,
  };
})(window);
