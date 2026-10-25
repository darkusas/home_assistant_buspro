// HDL Buspro panel: scan the bus, test channels with ON/OFF before adding them, add them as entities.
// Plain web component, no build step. Text from the bus only ever goes into textContent.

const STRINGS = {
  lt: {
    scan: "Skanuoti magistralę",
    scanning: "Skanuojama…",
    rounds: { 2: "Greitas (2 raundai)", 4: "Įprastas (4 raundai)", 6: "Kruopštus (6 raundai)" },
    phases: {
      discovery: "Ieškoma įrenginių",
      identify: "Atpažįstami įrenginiai",
      channels: "Skaitomos kanalų būsenos",
      mac: "Skaitomi MAC adresai",
      names: "Skaitomi kanalų pavadinimai",
    },
    found: "rasta: {n}",
    notScanned: "Magistralė dar neskanuota. Paspauskite „Skanuoti magistralę“: tai trunka apie minutę ir nieko neperjungia.",
    lastScan: "Rasta įrenginių: {n} (per {s} s)",
    filterOutputs: "Išėjimų moduliai",
    filterAll: "Visi įrenginiai",
    categories: {
      output_module: "Išėjimų modulis", curtain_module: "Užuolaidų modulis", sensor: "Jutiklis", panel: "Panelė",
      dry_contact_module: "Sausų kontaktų modulis", floor_heating: "Grindų šildymas", logic: "Logikos modulis",
      gateway: "IP šliuzas", unknown: "Nežinomas",
    },
    channelsShort: "{n} kan.",
    addedShort: "pridėta {n}",
    selectDevice: "Pasirinkite įrenginį sąraše.",
    refresh: "Atnaujinti būsenas",
    columns: { number: "Nr.", name: "Pavadinimas", type: "Tipas", state: "Būsena", test: "Testas", entity: "Entity" },
    types: { switch: "Jungiklis", light_onoff: "Šviestuvas (įj./išj.)", light: "Šviestuvas (dimeris)" },
    platforms: { switch: "Jungiklis", light: "Šviestuvas" },
    kinds: { relay: "rėlė", dimmer: "dimeris", dmx: "DMX", output: "išėjimas", curtain: "užuolaida" },
    on: "ĮJ", off: "IŠJ", pulse: "Impulsas", open: "▲", stop: "■", close: "▼",
    stateOn: "Įjungta", stateOff: "Išjungta",
    warn: "Testas realiai perjungs prijungtą apkrovą (šviestuvą, siurblį, šildymą, vartus…). Impulsas įjungia 2 s ir grąžina ankstesnę būseną. Tęsti?",
    confirmed: "✔ {value} · {code} · {ms} ms",
    notConfirmed: "✖ {error}",
    reported: "įrenginys praneša {value}",
    add: "Pridėti pasirinktus ({n})",
    selectAll: "Pažymėti visus nepridėtus",
    added: "Pridėta entity: {n}.",
    rejected: "Nepridėta: {list}",
    remove: "Pašalinti",
    removeConfirm: "Pašalinti {id}?",
    yaml: "YAML",
    laterStage: "Šio tipo įrenginių pridėjimas bus vėlesniame etape. Kanalus galima išbandyti.",
    noChannels: "Šis įrenginys neturi kanalų, kuriuos būtų galima pridėti.",
    unnamed: "Kanalas {n}",
    error: "Klaida: {message}",
    // Messages from the integration, which are in English.
    serverErrors: {
      "No answer from the device": "Įrenginys neatsakė",
      "The device reported a failure": "Įrenginys pranešė apie klaidą",
      "Could not read the current level, so it will not be restored": "Nepavyko nuskaityti būsenos, todėl ji nebus atstatyta",
      "Too many commands for this channel; wait a moment": "Per daug komandų šiam kanalui, palaukite akimirką",
      "An HDL bus scan is already running": "Skanavimas jau vyksta",
    },
  },
  en: {
    scan: "Scan bus",
    scanning: "Scanning…",
    rounds: { 2: "Quick (2 rounds)", 4: "Normal (4 rounds)", 6: "Thorough (6 rounds)" },
    phases: {
      discovery: "Looking for devices",
      identify: "Identifying devices",
      channels: "Reading channel state",
      mac: "Reading MAC addresses",
      names: "Reading channel names",
    },
    found: "found: {n}",
    notScanned: "The bus has not been scanned yet. Press “Scan bus”: it takes about a minute and switches nothing.",
    lastScan: "Devices found: {n} (in {s} s)",
    filterOutputs: "Output modules",
    filterAll: "All devices",
    categories: {
      output_module: "Output module", curtain_module: "Curtain module", sensor: "Sensor", panel: "Panel",
      dry_contact_module: "Dry contact module", floor_heating: "Floor heating", logic: "Logic module",
      gateway: "IP gateway", unknown: "Unknown",
    },
    channelsShort: "{n} ch.",
    addedShort: "{n} added",
    selectDevice: "Select a device in the list.",
    refresh: "Refresh state",
    columns: { number: "No.", name: "Name", type: "Type", state: "State", test: "Test", entity: "Entity" },
    types: { switch: "Switch", light_onoff: "Light (on/off)", light: "Light (dimmable)" },
    platforms: { switch: "Switch", light: "Light" },
    kinds: { relay: "relay", dimmer: "dimmer", dmx: "DMX", output: "output", curtain: "curtain" },
    on: "ON", off: "OFF", pulse: "Pulse", open: "▲", stop: "■", close: "▼",
    stateOn: "On", stateOff: "Off",
    warn: "The test really switches the connected load (light, pump, heating, gate…). A pulse turns it on for 2 s and then restores it. Continue?",
    confirmed: "✔ {value} · {code} · {ms} ms",
    notConfirmed: "✖ {error}",
    reported: "device reports {value}",
    add: "Add selected ({n})",
    selectAll: "Select all not added",
    added: "Entities added: {n}.",
    rejected: "Not added: {list}",
    remove: "Remove",
    removeConfirm: "Remove {id}?",
    yaml: "YAML",
    laterStage: "Adding this kind of device comes in a later stage. Its channels can be tested.",
    noChannels: "This device has no channels that can be added.",
    unnamed: "Channel {n}",
    error: "Error: {message}",
  },
};

const OUTPUT_KINDS = ["relay", "dimmer", "dmx", "output"];
const WARNING_KEY = "buspro-test-warning-accepted";

function format(text, values = {}) {
  return text.replace(/\{(\w+)\}/g, (_, key) => (key in values ? values[key] : `{${key}}`));
}

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key in node && typeof value !== "string") node[key] = value;
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function readFlag(key) {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch (err) {
    return false;
  }
}

function writeFlag(key) {
  try {
    window.localStorage.setItem(key, "1");
  } catch (err) {
    // Private mode or blocked storage: the warning is simply shown again next time.
  }
}

const STYLE = `
  :host {
    display: block;
    min-height: 100vh;
    background: var(--primary-background-color, #fafafa);
    color: var(--primary-text-color, #212121);
    font-family: var(--paper-font-body1_-_font-family, Roboto, "Segoe UI", sans-serif);
    font-size: 14px;
    --bp-card: var(--card-background-color, var(--ha-card-background, #fff));
    --bp-border: var(--divider-color, rgba(0, 0, 0, 0.12));
    --bp-muted: var(--secondary-text-color, #727272);
    --bp-primary: var(--primary-color, #03a9f4);
    --bp-on-primary: var(--text-primary-color, #fff);
    --bp-ok: var(--success-color, #43a047);
    --bp-error: var(--error-color, #db4437);
  }
  header {
    display: flex; align-items: center; gap: 8px; height: 56px; padding: 0 16px;
    background: var(--app-header-background-color, var(--bp-primary));
    color: var(--app-header-text-color, var(--bp-on-primary));
    font-size: 20px;
  }
  main { padding: 16px; max-width: 1400px; margin: 0 auto; box-sizing: border-box; }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; margin-bottom: 12px; }
  .progress { color: var(--bp-muted); }
  button, select, input[type=text] {
    font: inherit; color: inherit; border-radius: 6px; border: 1px solid var(--bp-border);
    background: var(--bp-card); padding: 6px 10px; min-height: 34px; box-sizing: border-box;
  }
  button { cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: default; }
  button.primary { background: var(--bp-primary); color: var(--bp-on-primary); border-color: transparent; }
  button.small { padding: 2px 8px; min-height: 28px; }
  .banner { padding: 10px 12px; border-radius: 6px; margin-bottom: 12px; background: var(--bp-card);
    border-left: 4px solid var(--bp-primary); white-space: pre-line; }
  .banner.error { border-left-color: var(--bp-error); }
  .layout { display: grid; grid-template-columns: minmax(240px, 320px) 1fr; gap: 16px; align-items: start; }
  .card { background: var(--bp-card); border-radius: 8px; border: 1px solid var(--bp-border); overflow: hidden; }
  .card-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px;
    padding: 12px 16px; border-bottom: 1px solid var(--bp-border); }
  .card-head h2 { margin: 0; font-size: 16px; font-weight: 500; }
  .muted { color: var(--bp-muted); }
  .empty { padding: 16px; color: var(--bp-muted); }
  .devices { max-height: calc(100vh - 200px); overflow-y: auto; }
  .device { display: block; width: 100%; text-align: left; border: 0; border-bottom: 1px solid var(--bp-border);
    border-radius: 0; padding: 10px 16px; background: transparent; }
  .device:hover { background: rgba(127, 127, 127, 0.08); }
  .device.selected { background: rgba(127, 127, 127, 0.16); box-shadow: inset 4px 0 0 var(--bp-primary); }
  .device.dim .device-name { color: var(--bp-muted); }
  .device-name { font-weight: 500; }
  .device-meta { font-size: 12px; color: var(--bp-muted); margin-top: 2px; }
  .info { padding: 12px 16px; color: var(--bp-muted); border-bottom: 1px solid var(--bp-border); }
  .table-wrap { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 6px 8px; border-bottom: 1px solid var(--bp-border); text-align: left; vertical-align: middle; }
  th { font-weight: 500; color: var(--bp-muted); font-size: 12px; white-space: nowrap; }
  td input[type=text] { width: 100%; min-width: 140px; }
  .kind { font-size: 12px; color: var(--bp-muted); }
  .state { white-space: nowrap; font-weight: 500; }
  .state.on { color: var(--bp-ok); }
  .tests { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
  .tests input[type=range] { width: 90px; }
  .result { font-size: 12px; margin-top: 2px; }
  .result.ok { color: var(--bp-ok); }
  .result.bad { color: var(--bp-error); }
  .entity { font-size: 12px; word-break: break-all; }
  .footer { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px;
    padding: 12px 16px; }
  label.check { display: inline-flex; align-items: center; gap: 6px; }
  @media (max-width: 870px) {
    main { padding: 8px; }
    .layout { grid-template-columns: 1fr; }
    .devices { max-height: 40vh; }
    /* One card per channel instead of a wide table. */
    table.outputs thead { display: none; }
    table.outputs, table.outputs tbody { display: block; }
    table.outputs tr {
      display: grid; grid-template-columns: 28px 1fr auto; gap: 8px 10px; padding: 10px 12px;
      grid-template-areas: "check number state" "name name name" "type type type" "test test test" "entity entity entity";
      border-bottom: 1px solid var(--bp-border);
    }
    table.outputs td { display: block; border: 0; padding: 0; }
    td.check { grid-area: check; } td.number { grid-area: number; } td.state { grid-area: state; }
    td.name { grid-area: name; } td.type { grid-area: type; } td.test { grid-area: test; }
    td.entity { grid-area: entity; }
    td.type select { width: 100%; }
  }
`;

class BusproPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null; // buspro/devices result
    this._filter = "outputs";
    this._rounds = 4;
    this._selected = null;
    this._edits = {}; // "subnet.device.channel" -> {checked, name, type}
    this._results = {}; // "address:target:number" -> test result text
    this._live = {}; // channel number -> level, for the selected device
    this._liveCells = {};
    this._banner = null;
    this._unsubScan = null;
    this._unsubState = null;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._menuButton) this._menuButton.hass = hass;
    if (first) this._start();
  }

  get hass() {
    return this._hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._menuButton) this._menuButton.narrow = narrow;
  }

  get t() {
    const language = (this._hass && this._hass.language) || "en";
    return STRINGS[language.split("-")[0]] || STRINGS.en;
  }

  disconnectedCallback() {
    this._unsubscribe("_unsubScan");
    this._unsubscribe("_unsubState");
  }

  connectedCallback() {
    if (this._hass && !this._unsubScan) this._start();
  }

  _unsubscribe(name) {
    const unsub = this[name];
    this[name] = null;
    if (unsub) Promise.resolve(unsub).then((fn) => fn && fn()).catch(() => {});
  }

  async _start() {
    const selected = this._selected;
    this._selected = null;
    this._render();
    this._unsubScan = this._hass.connection.subscribeMessage((event) => this._onScanEvent(event),
      { type: "buspro/scan/subscribe" });
    await this._load();
    if (selected && this._device(selected)) this._select(selected);
  }

  async _load() {
    try {
      this._data = await this._hass.callWS({ type: "buspro/devices" });
    } catch (err) {
      this._showError(err);
    }
    this._render();
  }

  _onScanEvent(event) {
    if (!this._data) this._data = { scanning: false, progress: null, scan: null };
    if (event.event === "progress") {
      this._data.scanning = true;
      this._data.progress = event.progress;
      this._renderProgress();
    } else if (event.event === "done") {
      this._load();
    } else if (event.event === "error") {
      this._data.scanning = false;
      this._banner = { text: format(this.t.error, { message: this._serverText(event.message) }), error: true };
      this._render();
    }
  }

  async _scan() {
    this._banner = null;
    try {
      await this._hass.callWS({ type: "buspro/scan/start", rounds: this._rounds });
      // The first progress event can arrive before this result; keep it.
      this._data = { ...(this._data || {}), scanning: true };
    } catch (err) {
      this._showError(err);
    }
    this._render();
  }

  _devices() {
    const devices = (this._data && this._data.scan && this._data.scan.devices) || [];
    const outputs = devices.filter((d) => d.category === "output_module");
    const others = devices.filter((d) => d.category !== "output_module");
    return this._filter === "outputs" ? outputs : outputs.concat(others);
  }

  _device(address) {
    const devices = (this._data && this._data.scan && this._data.scan.devices) || [];
    return devices.find((d) => d.address === address) || null;
  }

  _select(address) {
    if (this._selected === address) return;
    this._selected = address;
    this._live = {};
    this._unsubscribe("_unsubState");
    this._unsubState = this._hass.connection.subscribeMessage((event) => this._onState(event),
      { type: "buspro/state/subscribe", address });
    this._render();
    if (this._device(address) && this._device(address).category === "output_module") this._refresh();
  }

  async _refresh() {
    if (!this._selected) return;
    try {
      await this._hass.callWS({ type: "buspro/device/refresh", address: this._selected });
    } catch (err) {
      this._showError(err);
    }
  }

  _onState(event) {
    for (const update of event.updates || []) {
      if (update.kind === "channel") this._live[update.number] = update.value;
      else if (update.kind === "channels_on") {
        update.value.forEach((on, index) => {
          const number = index + 1;
          // The bitmask only says on/off; keep a known dimmer level when it agrees.
          if (!on) this._live[number] = 0;
          else if (!(this._live[number] > 0)) this._live[number] = 100;
        });
      }
    }
    this._renderLive();
  }

  _channelKey(device, channel) {
    return `${device.address}.${channel.number}`;
  }

  _edit(device, channel) {
    const key = this._channelKey(device, channel);
    if (!this._edits[key]) {
      const name = channel.name || (device.remark
        ? `${device.remark} ${channel.number}` : format(this.t.unnamed, { n: channel.number }));
      const type = channel.kind === "relay" ? "switch" : "light";
      this._edits[key] = { checked: false, name, type };
    }
    return this._edits[key];
  }

  _acceptWarning() {
    if (readFlag(WARNING_KEY)) return true;
    if (!window.confirm(this.t.warn)) return false;
    writeFlag(WARNING_KEY);
    return true;
  }

  async _test(device, channel, target, action, level) {
    if (!this._acceptWarning()) return;
    const resultKey = `${device.address}:${target}:${channel.number}`;
    const message = { type: "buspro/channel/test", address: device.address, channel: channel.number, target, action };
    if (level !== undefined) message.level = level;
    try {
      const result = await this._hass.callWS(message);
      this._results[resultKey] = this._describeResult(result);
    } catch (err) {
      this._results[resultKey] = { ok: false, text: format(this.t.notConfirmed,
        { error: this._serverText(err.message || String(err)) }) };
    }
    this._renderResult(resultKey);
  }

  _serverText(message) {
    return (this.t.serverErrors && this.t.serverErrors[message]) || message;
  }

  _describeResult(result) {
    const value = result.kind === "output" ? `${result.value} %` : result.value;
    if (result.confirmed) {
      return { ok: true, text: format(this.t.confirmed, { value, code: result.confirmed_by,
        ms: Math.round((result.latency || 0) * 1000) }) };
    }
    const error = result.error ? this._serverText(result.error) : format(this.t.reported, { value });
    return { ok: false, text: format(this.t.notConfirmed, { error }) };
  }

  async _addSelected(device) {
    const entities = [];
    for (const channel of device.channels) {
      const edit = this._edits[this._channelKey(device, channel)];
      if (!edit || !edit.checked || channel.entity) continue;
      entities.push({
        platform: edit.type === "switch" ? "switch" : "light",
        dimmable: edit.type === "light",
        address: device.address,
        channel: channel.number,
        name: edit.name.trim() || format(this.t.unnamed, { n: channel.number }),
        device_name: device.remark || null,
        device_model: device.type_code || null,
        mac: device.mac || null,
      });
    }
    if (!entities.length) return;
    try {
      const result = await this._hass.callWS({ type: "buspro/entities/add", entities });
      const lines = [format(this.t.added, { n: result.added.length })];
      if (result.rejected.length) {
        lines.push(format(this.t.rejected, { list: result.rejected.map((r) => `${r.key}: ${r.reason}`).join("; ") }));
      }
      this._banner = { text: lines.join("\n"), error: result.rejected.length > 0 };
      for (const key of result.added) delete this._edits[key];
    } catch (err) {
      this._showError(err);
    }
    await this._load();
    // Entity ids are assigned right after the entities are created.
    setTimeout(() => this._load(), 1000);
  }

  async _remove(entity) {
    if (!window.confirm(format(this.t.removeConfirm, { id: entity.entity_id || entity.key }))) return;
    try {
      await this._hass.callWS({ type: "buspro/entities/remove", keys: [entity.key] });
    } catch (err) {
      this._showError(err);
    }
    await this._load();
  }

  _showError(err) {
    this._banner = { text: format(this.t.error, { message: this._serverText((err && err.message) || String(err)) }),
      error: true };
  }

  // Rendering

  _render() {
    const t = this.t;
    const root = this.shadowRoot;
    root.textContent = "";
    root.append(el("style", { text: STYLE }));

    const header = el("header");
    const MenuButton = customElements.get("ha-menu-button");
    if (MenuButton) {
      this._menuButton = document.createElement("ha-menu-button");
      this._menuButton.hass = this._hass;
      this._menuButton.narrow = this._narrow;
      header.append(this._menuButton);
    }
    header.append(el("span", { text: "HDL Buspro" }));
    root.append(header);

    const main = el("main");
    const scanning = Boolean(this._data && this._data.scanning);
    const roundsSelect = el("select", {
      disabled: scanning, "aria-label": "rounds",
      onchange: (e) => { this._rounds = Number(e.target.value); },
    }, Object.entries(t.rounds).map(([value, label]) =>
      el("option", { value, selected: Number(value) === this._rounds, text: label })));
    this._progressNode = el("span", { class: "progress" });
    main.append(el("div", { class: "toolbar" }, [
      el("button", { class: "primary", disabled: scanning, onclick: () => this._scan(),
        text: scanning ? t.scanning : t.scan }),
      roundsSelect,
      this._progressNode,
    ]));
    this._renderProgress();

    if (this._banner) {
      main.append(el("div", { class: `banner${this._banner.error ? " error" : ""}`, text: this._banner.text }));
    }

    const scan = this._data && this._data.scan;
    if (!scan) {
      main.append(el("div", { class: "card empty", text: scanning ? t.scanning : t.notScanned }));
    } else {
      main.append(el("div", { class: "layout" }, [this._renderDeviceList(scan), this._renderDetail()]));
    }
    root.append(main);
  }

  _renderProgress() {
    if (!this._progressNode) return;
    const t = this.t;
    const data = this._data || {};
    let text = "";
    if (data.scanning && data.progress) {
      const p = data.progress;
      const step = p.total ? ` (${p.done + (p.phase === "discovery" ? 0 : 1)}/${p.total})` : "";
      text = `${t.phases[p.phase] || p.phase}${step} · ${format(t.found, { n: p.devices })}`;
    } else if (data.scanning) {
      text = t.scanning;
    } else if (data.scan) {
      text = format(t.lastScan, { n: data.scan.devices.length, s: Math.round(data.scan.duration) });
    }
    this._progressNode.textContent = text;
  }

  _renderDeviceList(scan) {
    const t = this.t;
    const filter = el("select", {
      "aria-label": "filter",
      onchange: (e) => { this._filter = e.target.value; this._render(); },
    }, [
      el("option", { value: "outputs", selected: this._filter === "outputs", text: t.filterOutputs }),
      el("option", { value: "all", selected: this._filter === "all", text: t.filterAll }),
    ]);
    const list = el("div", { class: "devices" });
    for (const device of this._devices()) {
      const added = device.channels.filter((c) => c.entity).length;
      const meta = [t.categories[device.category] || device.category];
      if (device.channels.length) meta.push(format(t.channelsShort, { n: device.channels.length }));
      if (added) meta.push(format(t.addedShort, { n: added }));
      list.append(el("button", {
        class: `device${device.address === this._selected ? " selected" : ""}${device.category === "output_module" ? "" : " dim"}`,
        onclick: () => this._select(device.address),
      }, [
        el("div", { class: "device-name", text: `${device.address} · ${device.remark || "—"}` }),
        el("div", { class: "device-meta", text: meta.join(" · ") }),
      ]));
    }
    return el("section", { class: "card" }, [el("div", { class: "card-head" }, [filter]), list]);
  }

  _renderDetail() {
    const t = this.t;
    const device = this._selected && this._device(this._selected);
    this._liveCells = {};
    this._resultCells = {};
    if (!device) return el("section", { class: "card empty", text: t.selectDevice });

    const facts = [t.categories[device.category] || device.category, device.type_code, device.mac && `MAC ${device.mac}`]
      .filter(Boolean).join(" · ");
    const head = el("div", { class: "card-head" }, [
      el("div", {}, [el("h2", { text: `${device.address} · ${device.remark || "—"}` }),
        el("div", { class: "muted", text: facts })]),
      device.category === "output_module"
        ? el("button", { onclick: () => this._refresh(), text: t.refresh }) : null,
    ]);
    const section = el("section", { class: "card" }, [head]);

    if (device.category === "output_module") {
      section.append(this._renderOutputTable(device));
    } else if (device.category === "curtain_module" && device.channels.length) {
      section.append(el("div", { class: "info", text: t.laterStage }), this._renderCurtainTable(device));
    } else {
      section.append(el("div", { class: "info", text: device.channels.length ? t.laterStage : t.noChannels }));
    }
    return section;
  }

  _renderOutputTable(device) {
    const t = this.t;
    const rows = device.channels.map((channel) => this._renderOutputRow(device, channel));
    const table = el("table", { class: "outputs" }, [
      el("thead", {}, el("tr", {}, ["", t.columns.number, t.columns.name, t.columns.type, t.columns.state,
        t.columns.test, t.columns.entity].map((text) => el("th", { text })))),
      el("tbody", {}, rows),
    ]);
    const addButton = el("button", { class: "primary", onclick: () => this._addSelected(device) });
    const updateCount = () => {
      const n = device.channels.filter((c) => !c.entity && this._edit(device, c).checked).length;
      addButton.textContent = format(t.add, { n });
      addButton.disabled = n === 0;
    };
    this._updateCount = updateCount;
    updateCount();
    const selectAll = el("button", {
      onclick: () => {
        for (const channel of device.channels) if (!channel.entity) this._edit(device, channel).checked = true;
        this._render();
      },
      text: t.selectAll,
    });
    return el("div", {}, [el("div", { class: "table-wrap" }, table),
      el("div", { class: "footer" }, [selectAll, addButton])]);
  }

  _renderOutputRow(device, channel) {
    const t = this.t;
    const edit = this._edit(device, channel);
    const entity = channel.entity;
    const checkbox = el("input", {
      type: "checkbox", checked: edit.checked, disabled: Boolean(entity), "aria-label": `select ${channel.number}`,
      onchange: (e) => { edit.checked = e.target.checked; this._updateCount && this._updateCount(); },
    });
    const nameInput = el("input", {
      type: "text", value: entity && entity.name ? entity.name : edit.name, disabled: Boolean(entity),
      "aria-label": `name ${channel.number}`, oninput: (e) => { edit.name = e.target.value; },
    });
    // Once added, show what the entity is, not the choice for a new one.
    const typeControl = entity
      ? el("span", { class: "muted", text: t.platforms[entity.platform] || entity.platform })
      : el("select", {
        "aria-label": `type ${channel.number}`,
        onchange: (e) => { edit.type = e.target.value; },
      }, Object.entries(t.types).map(([value, label]) =>
        el("option", { value, selected: value === edit.type, text: label })));

    const stateCell = el("td", { class: "state" });
    this._liveCells[channel.number] = stateCell;
    if (!(channel.number in this._live) && channel.level !== null && channel.level !== undefined) {
      this._live[channel.number] = channel.level;
    }

    const resultKey = `${device.address}:output:${channel.number}`;
    const resultNode = el("div", { class: "result" });
    this._resultCells[resultKey] = resultNode;
    const tests = el("div", { class: "tests" }, [
      el("button", { class: "small", onclick: () => this._test(device, channel, "output", "on"), text: t.on }),
      el("button", { class: "small", onclick: () => this._test(device, channel, "output", "off"), text: t.off }),
      el("button", { class: "small", onclick: () => this._test(device, channel, "output", "pulse"), text: t.pulse }),
    ]);
    if (channel.kind !== "relay") {
      tests.append(el("input", {
        type: "range", min: "0", max: "100", step: "5", value: String(this._live[channel.number] || 0),
        "aria-label": `level ${channel.number}`,
        onchange: (e) => this._test(device, channel, "output", "level", Number(e.target.value)),
      }));
    }

    let entityCell;
    if (entity && entity.source === "panel") {
      entityCell = el("td", { class: "entity" }, [
        el("div", { text: entity.entity_id || "…" }),
        el("button", { class: "small", onclick: () => this._remove(entity), text: t.remove }),
      ]);
    } else if (entity) {
      entityCell = el("td", { class: "entity", text: `${t.yaml}: ${entity.entity_id}` });
    } else {
      entityCell = el("td", { class: "entity muted", text: "—" });
    }

    const row = el("tr", {}, [
      el("td", { class: "check" }, checkbox),
      el("td", { class: "number" }, [String(channel.number),
        el("div", { class: "kind", text: t.kinds[channel.kind] || channel.kind })]),
      el("td", { class: "name" }, nameInput),
      el("td", { class: "type" }, typeControl),
      stateCell,
      el("td", { class: "test" }, [tests, resultNode]),
      entityCell,
    ]);
    this._fillLive(channel.number);
    this._renderResult(resultKey);
    return row;
  }

  _renderCurtainTable(device) {
    const t = this.t;
    const rows = device.channels.map((channel) => {
      const resultKey = `${device.address}:curtain:${channel.number}`;
      const resultNode = el("div", { class: "result" });
      this._resultCells[resultKey] = resultNode;
      const row = el("tr", {}, [
        el("td", { text: String(channel.number) }),
        el("td", { text: channel.name || format(t.unnamed, { n: channel.number }) }),
        el("td", {}, [el("div", { class: "tests" }, ["open", "stop", "close"].map((action) =>
          el("button", { class: "small", onclick: () => this._test(device, channel, "curtain", action),
            text: t[action] }))), resultNode]),
      ]);
      this._renderResult(resultKey);
      return row;
    });
    return el("div", { class: "table-wrap" }, el("table", {}, [
      el("thead", {}, el("tr", {}, [t.columns.number, t.columns.name, t.columns.test].map((text) => el("th", { text })))),
      el("tbody", {}, rows),
    ]));
  }

  _fillLive(number) {
    const cell = this._liveCells[number];
    if (!cell) return;
    const level = this._live[number];
    if (level === undefined || level === null) {
      cell.textContent = "—";
      cell.className = "state";
      return;
    }
    const device = this._device(this._selected);
    const channel = device && device.channels.find((c) => c.number === number);
    const dimmable = channel && channel.kind !== "relay";
    cell.textContent = level > 0 ? (dimmable ? `${level} %` : this.t.stateOn) : this.t.stateOff;
    cell.className = level > 0 ? "state on" : "state";
  }

  _renderLive() {
    for (const number of Object.keys(this._liveCells)) this._fillLive(Number(number));
  }

  _renderResult(key) {
    const node = this._resultCells && this._resultCells[key];
    const result = this._results[key];
    if (!node) return;
    node.textContent = result ? result.text : "";
    node.className = result ? `result ${result.ok ? "ok" : "bad"}` : "result";
  }
}

customElements.define("buspro-panel", BusproPanel);
