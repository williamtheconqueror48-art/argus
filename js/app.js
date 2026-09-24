/* ARGUS shared data layer — static JSON, no backend */
const DATA_FILES = ["vendors", "products", "corporate_entities", "legal_actions", "incidents", "customer_links", "sources", "screening_list"];
const DB = {};

async function loadDB() {
  const got = await Promise.all(DATA_FILES.map(f => fetch("data/" + f + ".json").then(r => {
    if (!r.ok) throw new Error("failed to load " + f);
    return r.json();
  })));
  DATA_FILES.forEach((f, i) => DB[f] = got[i]);
  DB.sourceById = Object.fromEntries(DB.sources.map(s => [s.id, s]));
  DB.vendorById = Object.fromEntries(DB.vendors.map(v => [v.id, v]));
  DB.productById = Object.fromEntries(DB.products.map(p => [p.id, p]));
  return DB;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}

function statusBadge(v) {
  const label = { active: "Active", rebranded: "Rebranded", defunct: "Defunct", acquired: "Acquired", unknown: "Unknown" }[v.status] || v.status;
  return `<span class="badge ${esc(v.status)}">${esc(label)}</span>`;
}

function countryBadge(cc) {
  return cc ? `<span class="badge country" title="Headquarters country (ISO)">${esc(cc)}</span>` : "";
}

function claimBadge(cs) {
  const labels = { confirmed: "Confirmed", forensically_attributed: "Forensically attributed", reported: "Reported", alleged: "Alleged", denied: "Denied" };
  return `<span class="cs ${esc(cs)}">${esc(labels[cs] || cs)}</span>`;
}

function vendorOf(r) {
  if (r.vendor_id && DB.vendorById[r.vendor_id]) return r.vendor_id;
  const p = r.product_id && DB.productById[r.product_id];
  return p ? p.vendor_id : null;
}

function productName(pid) {
  const p = pid && DB.productById[pid];
  return p ? p.name : "—";
}

function vendorName(vid) {
  const v = vid && DB.vendorById[vid];
  return v ? v.name : "—";
}

function customerLinksFor(vendorId) {
  return DB.customer_links.filter(c => vendorOf(c) === vendorId);
}

function incidentsFor(vendorId) {
  return DB.incidents.filter(i => vendorOf(i) === vendorId);
}

function sourceLinks(ids) {
  return (ids || []).map(id => {
    const s = DB.sourceById[id];
    if (!s) return "";
    return `<a class="ext" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.publisher)}</a>`;
  }).filter(Boolean).join(" · ");
}

/* Screening-list entries whose matched terms overlap this vendor's name/aliases */
function screeningMatchesFor(vendor) {
  const terms = [vendor.name, ...(vendor.aliases || [])].map(t => t.toLowerCase());
  return (DB.screening_list.entries || []).filter(e =>
    (e.matched_terms || []).some(mt => terms.some(t => t === mt.toLowerCase() || mt.toLowerCase().includes(t) || t.includes(mt.toLowerCase())))
  );
}

function vendorCard(v) {
  const products = DB.products.filter(p => p.vendor_id === v.id).map(p => esc(p.name)).join(", ");
  return `<div class="card" data-name="${esc((v.name + " " + (v.aliases || []).join(" ")).toLowerCase())}">
    <h3><a href="vendor.html?id=${encodeURIComponent(v.id)}">${esc(v.name)}</a></h3>
    <div class="meta">${countryBadge(v.country_hq)} ${statusBadge(v)}${products ? ` <span class="mono" style="font-size:12px">${products}</span>` : ""}</div>
    <p class="desc">${esc(v.description)}</p>
    <div class="tags">${(v.aliases || []).map(a => `<span class="badge alias">fka ${esc(a)}</span>`).join("")}</div>
  </div>`;
}

function renderVendorDetail(id) {
  const v = DB.vendorById[id];
  if (!v) return `<p class="empty">Unknown vendor: ${esc(id)}</p>`;
  const products = DB.products.filter(p => p.vendor_id === id);
  const entities = DB.corporate_entities.filter(e => e.vendor_id === id);
  const actions = DB.legal_actions.filter(a => (a.vendor_ids || []).includes(id));
  const clinks = customerLinksFor(id);
  const vinc = incidentsFor(id);
  const screened = screeningMatchesFor(v);
  const srcs = (v.source_ids || []).map(sid => DB.sourceById[sid]).filter(Boolean);

  const rows = (list, cols) => list.length
    ? `<table class="rows"><tr>${cols.map(c => `<th>${c[0]}</th>`).join("")}</tr>` +
      list.map(r => `<tr>${cols.map(c => `<td>${c[1](r)}</td>`).join("")}</tr>`).join("") + `</table>`
    : `<p class="empty">None recorded yet.</p>`;

  return `
  <div class="detail-head">
    <h2>${esc(v.name)}</h2>
    <div>${countryBadge(v.country_hq)} ${statusBadge(v)}
      ${(v.aliases || []).map(a => `<span class="badge alias">fka ${esc(a)}</span>`).join("")}</div>
    <dl class="kv">
      <dt>Description</dt><dd>${esc(v.description)}</dd>
      <dt>Sources</dt><dd>${sourceLinks(v.source_ids) || "—"}</dd>
    </dl>
  </div>

  <section class="block"><h3>Products (${products.length})</h3>
    ${rows(products, [["Product", r => esc(r.name)], ["Category", r => esc(r.category || "—")], ["Sources", r => sourceLinks(r.source_ids)]])}</section>

  <section class="block"><h3>Corporate entities (${entities.length})</h3>
    ${rows(entities, [["Entity", r => esc(r.name)], ["Role", r => esc(r.role)], ["Jurisdiction", r => esc(r.jurisdiction || "—")], ["Note", r => esc(r.relationship_note || "")]])}</section>

  <section class="block"><h3>Legal &amp; regulatory actions (${actions.length})</h3>
    ${actions.length ? actions.map(a => `
      <div class="src-card">
        <h4>${esc(a.title)}</h4>
        <div class="pub"><span class="badge">${esc(a.type.replace(/_/g, " "))}</span> ${esc(a.jurisdiction || "")}${a.date_filed ? " · filed " + esc(a.date_filed) : ""}${a.date_resolved ? " · resolved " + esc(a.date_resolved) : ""}</div>
        <p style="font-size:14px">${esc(a.outcome || "")}</p>
        <div class="pub">${a.docket_url ? `<a class="ext" href="${esc(a.docket_url)}" target="_blank" rel="noopener">Case filings (CourtListener)</a> · ` : ""}${sourceLinks(a.source_ids)}</div>
      </div>`).join("") : `<p class="empty">None recorded yet.</p>`}</section>

  <section class="block"><h3>Reported customers (${clinks.length})</h3>
    ${rows(clinks, [
      ["Customer", r => esc(r.customer_name)],
      ["Country", r => esc(r.customer_country || "—")],
      ["Product", r => esc(productName(r.product_id))],
      ["Claim strength", r => claimBadge(r.claim_strength)],
      ["First reported", r => esc(r.first_reported_year || "—")],
      ["Sources", r => sourceLinks(r.source_ids)],
    ])}
    <p class="pub" style="font-size:12px;color:#6b7280">Each link carries a claim-strength label. See the <a href="methodology.html">methodology</a> for what each label means.</p></section>

  <section class="block"><h3>Documented incidents (${vinc.length})</h3>
    ${rows(vinc, [
      ["Date", r => esc(r.date || "—")],
      ["Target", r => esc(r.victim_description)],
      ["Product", r => esc(productName(r.product_id))],
      ["Claim strength", r => claimBadge(r.claim_strength)],
      ["Sources", r => sourceLinks(r.source_ids)],
    ])}
    <p class="pub" style="font-size:12px;color:#6b7280">Victim descriptions quote the source's own characterization.</p></section>

  <section class="block"><h3>US screening-list hits (${screened.length})</h3>
    ${rows(screened, [
      ["Entry", r => esc(r.name)],
      ["List", r => esc(r.source)],
      ["Type", r => esc(r.type)],
      ["Programs", r => esc((r.programs || []).join(", "))],
      ["Detail", r => r.source_information_url ? `<a class="ext" href="${esc(r.source_information_url)}" target="_blank" rel="noopener">source</a>` : "—"],
    ])}
    <p class="pub" style="font-size:12px;color:#6b7280">Matched ${esc(DB.screening_list.entries_scanned)} screened-list entries on ${esc(DB.screening_list.retrieved_date)} via <a class="ext" href="https://www.trade.gov/consolidated-screening-list" target="_blank" rel="noopener">trade.gov</a>. Matches are mechanical name matches — review the entry before drawing conclusions.</p></section>

  <section class="block"><h3>Cited sources (${srcs.length})</h3>
    ${srcs.map(s => `<div class="src-card"><h4>${esc(s.title)}</h4>
      <div class="pub">${esc(s.publisher)}${s.published_date ? " · " + esc(s.published_date) : ""} · retrieved ${esc(s.retrieved_date)}</div>
      <div class="pub"><a class="ext" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a></div></div>`).join("")}</section>`;
}

function renderSources() {
  return DB.sources.map(s => `<div class="src-card">
    <h4>${esc(s.title)}</h4>
    <div class="pub">${esc(s.publisher)}${s.published_date ? " · published " + esc(s.published_date) : ""} · retrieved ${esc(s.retrieved_date)} · <span class="mono">${esc(s.source_type)}</span></div>
    <div class="pub"><a class="ext" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a></div>
    ${s.license_note ? `<div class="pub" style="font-style:italic">${esc(s.license_note)}</div>` : ""}
  </div>`).join("");
}

function renderLegalTimeline() {
  const acts = [...DB.legal_actions].sort((a, b) => (a.date_filed || "").localeCompare(b.date_filed || ""));
  return acts.map(a => {
    const names = (a.vendor_ids || []).map(id => DB.vendorById[id] ? DB.vendorById[id].name : id).join(", ");
    return `<div class="src-card">
      <h4>${esc(a.title)}</h4>
      <div class="pub"><span class="badge">${esc(a.type.replace(/_/g, " "))}</span> ${esc(a.date_filed || a.date_resolved || "")} · ${esc(names)}</div>
      <p style="font-size:14px">${esc(a.outcome || "")}</p>
      <div class="pub">${a.docket_url ? `<a class="ext" href="${esc(a.docket_url)}" target="_blank" rel="noopener">Case filings</a> · ` : ""}${sourceLinks(a.source_ids)}</div>
    </div>`;
  }).join("");
}

/* ---- Incidents & Customers pages ---- */

function renderIncidents(filter) {
  const needle = (filter || "").trim().toLowerCase();
  const list = [...DB.incidents]
    .filter(i => !needle || ((i.victim_description || "") + " " + productName(i.product_id) + " " + vendorName(vendorOf(i)) + " " + (i.country || "")).toLowerCase().includes(needle))
    .sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  if (!list.length) return `<p class="empty">No incidents recorded yet.</p>`;
  return `<table class="rows"><tr><th>Date</th><th>Target</th><th>Product</th><th>Vendor</th><th>Country</th><th>Claim strength</th><th>Sources</th></tr>` +
    list.map(i => `<tr>
      <td class="mono">${esc(i.date || "—")}</td>
      <td>${esc(i.victim_description)}${i.infection_vector && i.infection_vector !== "unknown" ? `<div class="pub" style="font-size:12px">vector: ${esc(i.infection_vector)}</div>` : ""}</td>
      <td>${esc(productName(i.product_id))}</td>
      <td>${esc(vendorName(vendorOf(i)))}</td>
      <td>${esc(i.country || "—")}</td>
      <td>${claimBadge(i.claim_strength)}</td>
      <td>${sourceLinks(i.source_ids)}</td>
    </tr>`).join("") + `</table>`;
}

function renderCustomers(filter) {
  const needle = (filter || "").trim().toLowerCase();
  const list = [...DB.customer_links]
    .filter(c => !needle || ((c.customer_name || "") + " " + (c.customer_country || "") + " " + vendorName(vendorOf(c)) + " " + productName(c.product_id)).toLowerCase().includes(needle))
    .sort((a, b) => (a.customer_name || "").localeCompare(b.customer_name || ""));
  if (!list.length) return `<p class="empty">No customer links recorded yet.</p>`;
  return `<table class="rows"><tr><th>Customer</th><th>Country</th><th>Vendor</th><th>Product</th><th>Claim strength</th><th>First reported</th><th>Sources</th></tr>` +
    list.map(c => `<tr>
      <td>${esc(c.customer_name)}</td>
      <td>${esc(c.customer_country || "—")}</td>
      <td>${esc(vendorName(vendorOf(c)))}</td>
      <td>${esc(productName(c.product_id))}</td>
      <td>${claimBadge(c.claim_strength)}</td>
      <td class="mono">${esc(c.first_reported_year || "—")}</td>
      <td>${sourceLinks(c.source_ids)}</td>
    </tr>`).join("") + `</table>`;
}
