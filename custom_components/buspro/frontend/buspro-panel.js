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
    platforms: { switch: "Jungiklis", light: "Šviestuvas", cover: "Užuolaida", sensor: "Jutiklis",
      binary_sensor: "Dvejetainis jutiklis", climate: "Termostatas" },
    features: { temperature: "Temperatūra", illuminance: "Apšvietimas", motion: "Judesys",
      dry_contact_1: "Sausas kontaktas 1", dry_contact_2: "Sausas kontaktas 2", curtain: "Užuolaida",
      floor_heating: "Grindų šildymas", heating_zone: "Šildymo zona", floor_sensor: "Grindų termometras" },
    feature: "Funkcija",
    openingTime: "Atidarymo laikas, s",
    positionControl: "Padėtis procentais (užuolaida pati žino padėtį)",
    goTo: "Į padėtį",
    motionYes: "Judesys", motionNo: "Nėra",
    curtainStatus: { 0: "Stop", 1: "Atidaroma", 2: "Uždaroma" },
    heatingOn: "Šildo", heatingOff: "Išjungta",
    presets: { 1: "normalus", 2: "dienos", 3: "nakties", 4: "išvykus", 5: "laikmatis" },
    heatingNote: "Šildymo skaitymas patikrintas įrašais; valdymas dar nebandytas su tikra įranga.",
    heatingModuleNote: "Zonų ir grindų termometrų skaitymas patikrintas įrašu. Valdymas atliekamas pagal HDL dokumentaciją ir su tikra įranga dar nebandytas: išbandykite zoną mygtukais ir žiūrėkite, ar modulis patvirtina.",
    zone: "Zona {n}",
    floorSensor: "Grindų termometras {n}",
    floorSensorZone: "Grindų termometras {n} · zona {zone}",
    floorSensorName: "grindys",
    setpoint: "Nustatyti",
    valveOpen: "vožtuvas atidarytas",
    notAddable: "dar nepalaikoma",
    universal: "Universalūs jungikliai",
    universalHelp: "Skanuojant jų nerasti: įveskite numerį (pvz. iš logikos modulio), išbandykite ir pridėkite.",
    universalNumber: "Nr.",
    addAsSwitch: "Pridėti kaip jungiklį",
    addAsSensor: "Pridėti kaip jutiklį",
    universalName: "Universalus jungiklis {n}",
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
    noChannels: "Šis įrenginys neturi kanalų, kuriuos būtų galima pridėti.",
    unnamed: "Kanalas {n}",
    error: "Klaida: {message}",
    override: "Pakeisti tipą",
    overrideHelp: "Jei įrenginys neatpažintas arba atpažintas neteisingai, nurodykite, kas tai yra. Taikoma visiems {code} tipo įrenginiams.",
    overrideCategory: "Tipas",
    overrideKind: "Kanalų tipas",
    overrideCount: "Kanalų sk.",
    overrideCurtains: "Užuolaidų sk.",
    overrideSave: "Išsaugoti tipą",
    overrideReset: "Grąžinti automatinį",
    overrideSaved: "Tipas {code} išsaugotas.",
    overrideRemoved: "Tipui {code} vėl naudojamas automatinis atpažinimas.",
    overrideBadCount: "Kanalų skaičius turi būti nuo 1 iki 64.",
    manualType: "rankinis tipas",
    // Messages from the integration, which are in English.
    serverErrors: {
      "No answer from the device": "Įrenginys neatsakė",
      "The device reported a failure": "Įrenginys pranešė apie klaidą",
      "Could not read the current level, so it will not be restored": "Nepavyko nuskaityti būsenos, todėl ji nebus atstatyta",
      "Too many commands for this channel; wait a moment": "Per daug komandų šiam kanalui, palaukite akimirką",
      "An HDL bus scan is already running": "Skanavimas jau vyksta",
      "A floor heating setpoint must be 5-35 °C": "Grindų šildymo temperatūra turi būti 5–35 °C",
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
    platforms: { switch: "Switch", light: "Light", cover: "Cover", sensor: "Sensor", binary_sensor: "Binary sensor",
      climate: "Thermostat" },
    features: { temperature: "Temperature", illuminance: "Illuminance", motion: "Motion",
      dry_contact_1: "Dry contact 1", dry_contact_2: "Dry contact 2", curtain: "Curtain",
      floor_heating: "Floor heating", heating_zone: "Heating zone", floor_sensor: "Floor sensor" },
    feature: "Feature",
    openingTime: "Opening time, s",
    positionControl: "Position in % (the curtain knows its position)",
    goTo: "Go to",
    motionYes: "Motion", motionNo: "Clear",
    curtainStatus: { 0: "Stopped", 1: "Opening", 2: "Closing" },
    heatingOn: "Heating", heatingOff: "Off",
    presets: { 1: "normal", 2: "day", 3: "night", 4: "away", 5: "timer" },
    heatingNote: "Reading the heating is confirmed by captures; control is not yet tested on real hardware.",
    heatingModuleNote: "Reading zones and floor sensors is confirmed by a capture. Control follows the HDL documentation and is not yet tested on real hardware: try a zone with the buttons and check that the module confirms.",
    zone: "Zone {n}",
    floorSensor: "Floor sensor {n}",
    floorSensorZone: "Floor sensor {n} · zone {zone}",
    floorSensorName: "floor",
    setpoint: "Set",
    valveOpen: "valve open",
    notAddable: "not supported yet",
    universal: "Universal switches",
    universalHelp: "A scan does not find them: enter the number (e.g. from a logic module), test it and add it.",
    universalNumber: "No.",
    addAsSwitch: "Add as switch",
    addAsSensor: "Add as sensor",
    universalName: "Universal switch {n}",
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
    noChannels: "This device has no channels that can be added.",
    unnamed: "Channel {n}",
    error: "Error: {message}",
    override: "Change type",
    overrideHelp: "If the device is not recognised, or recognised wrongly, say what it is. Applies to every device of type {code}.",
    overrideCategory: "Type",
    overrideKind: "Channel type",
    overrideCount: "Channels",
    overrideCurtains: "Curtains",
    overrideSave: "Save type",
    overrideReset: "Back to automatic",
    overrideSaved: "Type {code} saved.",
    overrideRemoved: "Type {code} is recognised automatically again.",
    overrideBadCount: "The number of channels must be from 1 to 64.",
    manualType: "set by hand",
  },
};

const OUTPUT_KINDS = ["relay", "dimmer", "dmx", "output"];
const FEATURE_PLATFORMS = { curtain: "cover", temperature: "sensor", illuminance: "sensor", floor_heating: "climate",
  heating_zone: "climate", floor_sensor: "sensor" };
// What a device type can be set to by hand (buspro/type_override/set).
const OVERRIDE_CATEGORIES = ["output_module", "curtain_module", "sensor", "panel", "logic", "gateway"];
const COUNTED_CATEGORIES = ["output_module", "curtain_module"];
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
  .tests input.setpoint { width: 64px; }
  table.features td.state { white-space: normal; min-width: 140px; }
  .result { font-size: 12px; margin-top: 2px; }
  .result.ok { color: var(--bp-ok); }
  .result.bad { color: var(--bp-error); }
  .entity { font-size: 12px; word-break: break-all; }
  .universal { padding: 12px 16px; border-top: 1px solid var(--bp-border); }
  .universal summary { cursor: pointer; font-weight: 500; }
  .universal .row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; margin-top: 8px; }
  input[type=number] { font: inherit; color: inherit; border-radius: 6px; border: 1px solid var(--bp-border);
    background: var(--bp-card); padding: 6px 8px; min-height: 34px; box-sizing: border-box; width: 84px; }
  .note { font-size: 12px; color: var(--bp-muted); }
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
    this._testValues = {}; // "address:target:number" -> typed setpoint or position, kept across re-renders
    this._live = {}; // channel number -> level, for the selected device
    this._liveCells = {};
    this._resetLive();
    this._universal = { number: "", name: "" };
    this._overrideEdits = {}; // type code -> {category, kind, count, open}
    this._banner = null;
    this._unsubScan = null;
    this._unsubState = null;
  }

  _resetLive() {
    this._liveSensor = {}; // temperature, illuminance, motion, dry_contact_1, dry_contact_2
    this._liveHeating = {};
    this._liveZones = {}; // floor heating module: zone -> status
    this._liveFloor = {}; // floor heating module: floor sensor -> °C
    this._liveCurtain = {}; // curtain -> status
    this._liveCurtainPosition = {}; // curtain -> % (curtains that know their position)
    this._liveUniversal = {}; // switch -> bool
    this._featureCells = {};
    this._universalCells = {};
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
    this._resetLive();
    this._unsubscribe("_unsubState");
    this._unsubState = this._hass.connection.subscribeMessage((event) => this._onState(event),
      { type: "buspro/state/subscribe", address });
    this._render();
    if (this._device(address)) this._refresh();
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
      else if (update.kind === "sensor") Object.assign(this._liveSensor, update.value);
      else if (update.kind === "floor_heating") Object.assign(this._liveHeating, update.value);
      else if (update.kind === "curtain") this._liveCurtain[update.number] = update.value;
      else if (update.kind === "curtain_position") this._liveCurtainPosition[update.number] = update.value;
      else if (update.kind === "heating_zone") this._liveZones[update.number] = update.value;
      else if (update.kind === "floor_sensor") this._liveFloor[update.number] = update.value;
      else if (update.kind === "universal_switch") this._liveUniversal[update.number] = update.value;
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

  async _test(device, channel, target, action, level, resultKey = `${device.address}:${target}:${channel.number}`) {
    if (!this._acceptWarning()) return;
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
    const t = this.t;
    let value = result.value;
    if (result.kind === "output") value = `${result.value} %`;
    else if (result.kind === "universal_switch") value = result.value ? t.stateOn : t.stateOff;
    else if (result.kind === "curtain") value = t.curtainStatus[result.value] || result.value;
    else if (result.kind === "curtain_position") value = `${result.value} %`;
    else if (result.kind === "heating_zone") {
      // On/off answers 1 or 0, a setpoint its temperature (5-35 °C).
      value = result.value === null ? null : (result.value <= 1 ? (result.value ? t.stateOn : t.stateOff) : `${result.value} °C`);
    }
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
        channel: channel.number,
        name: edit.name.trim() || format(this.t.unnamed, { n: channel.number }),
      });
    }
    await this._addEntities(device, entities);
  }

  async _addEntities(device, items) {
    // The device's own details go with every entity, for the Home Assistant device registry.
    const entities = items.map((item) => ({
      ...item,
      address: device.address,
      device_name: device.remark || null,
      device_model: device.type_code || null,
      device_category: device.category,
      mac: device.mac || null,
    }));
    if (!entities.length) return null;
    let result = null;
    try {
      result = await this._hass.callWS({ type: "buspro/entities/add", entities });
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
    return result;
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
      if (device.category === "unknown" && device.type_code) meta.push(device.type_code);
      if (device.override) meta.push(t.manualType);
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
    this._featureCells = {};
    this._universalCells = {};
    if (!device) return el("section", { class: "card empty", text: t.selectDevice });

    const facts = [t.categories[device.category] || device.category, device.override && t.manualType, device.type_code,
      device.mac && `MAC ${device.mac}`].filter(Boolean).join(" · ");
    const head = el("div", { class: "card-head" }, [
      el("div", {}, [el("h2", { text: `${device.address} · ${device.remark || "—"}` }),
        el("div", { class: "muted", text: facts })]),
      el("button", { onclick: () => this._refresh(), text: t.refresh }),
    ]);
    const section = el("section", { class: "card" }, [head]);

    if (device.category === "output_module") {
      section.append(this._renderOutputTable(device));
    } else if (device.channels.length) {
      section.append(this._renderFeatureTable(device));
    } else {
      section.append(el("div", { class: "info", text: t.noChannels }));
    }
    if (device.type_code && device.category !== "software") section.append(this._renderOverride(device));
    if (!["gateway", "software"].includes(device.category)) section.append(this._renderUniversal(device));
    return section;
  }

  _overrideEdit(device) {
    const code = device.type_code;
    if (!this._overrideEdits[code]) {
      const current = device.override || {};
      const counted = COUNTED_CATEGORIES.includes(device.category) && device.channels.length;
      this._overrideEdits[code] = {
        category: current.category || (OVERRIDE_CATEGORIES.includes(device.category) ? device.category : "output_module"),
        kind: current.kind || "relay",
        count: String(current.count || counted || ""),
        // Open where it is needed: devices the scan could not classify, or set by hand already.
        open: Boolean(device.override || device.category === "unknown"),
      };
    }
    return this._overrideEdits[code];
  }

  _renderOverride(device) {
    const t = this.t;
    const edit = this._overrideEdit(device);
    const categorySelect = el("select", {
      "aria-label": "override category",
      onchange: (e) => { edit.category = e.target.value; this._render(); },
    }, OVERRIDE_CATEGORIES.map((category) =>
      el("option", { value: category, selected: edit.category === category, text: t.categories[category] })));
    const kindSelect = el("select", {
      "aria-label": "override kind", onchange: (e) => { edit.kind = e.target.value; },
    }, ["relay", "dimmer"].map((kind) => el("option", { value: kind, selected: edit.kind === kind, text: t.kinds[kind] })));
    const countInput = el("input", {
      type: "number", min: "1", max: "64", value: edit.count, "aria-label": "override count",
      oninput: (e) => { edit.count = e.target.value; },
    });
    return el("details", {
      class: "universal override", open: edit.open, ontoggle: (e) => { edit.open = e.target.open; },
    }, [
      el("summary", { text: t.override }),
      el("div", { class: "note", text: format(t.overrideHelp, { code: device.type_code }) }),
      el("div", { class: "row" }, [
        el("label", {}, [`${t.overrideCategory} `, categorySelect]),
        edit.category === "output_module" ? el("label", {}, [`${t.overrideKind} `, kindSelect]) : null,
        COUNTED_CATEGORIES.includes(edit.category)
          ? el("label", {}, [`${edit.category === "curtain_module" ? t.overrideCurtains : t.overrideCount} `, countInput])
          : null,
        el("button", { class: "small primary", onclick: () => this._saveOverride(device), text: t.overrideSave }),
        device.override
          ? el("button", { class: "small", onclick: () => this._removeOverride(device), text: t.overrideReset })
          : null,
      ]),
    ]);
  }

  async _saveOverride(device) {
    const t = this.t;
    const edit = this._overrideEdit(device);
    const message = { type: "buspro/type_override/set", type_code: device.type_code, category: edit.category };
    if (edit.category === "output_module") message.kind = edit.kind;
    if (COUNTED_CATEGORIES.includes(edit.category) && edit.count !== "") {
      const count = Number(edit.count);
      if (!Number.isInteger(count) || count < 1 || count > 64) {
        this._banner = { text: t.overrideBadCount, error: true };
        this._render();
        return;
      }
      message.count = count;
    }
    try {
      await this._hass.callWS(message);
      this._banner = { text: format(t.overrideSaved, { code: device.type_code }) };
    } catch (err) {
      this._showError(err);
    }
    await this._load();
    this._refresh();  // the new channels' state
  }

  async _removeOverride(device) {
    try {
      await this._hass.callWS({ type: "buspro/type_override/remove", type_code: device.type_code });
      delete this._overrideEdits[device.type_code];
      this._banner = { text: format(this.t.overrideRemoved, { code: device.type_code }) };
    } catch (err) {
      this._showError(err);
    }
    await this._load();
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

    const row = el("tr", {}, [
      el("td", { class: "check" }, checkbox),
      el("td", { class: "number" }, [String(channel.number),
        el("div", { class: "kind", text: t.kinds[channel.kind] || channel.kind })]),
      el("td", { class: "name" }, nameInput),
      el("td", { class: "type" }, typeControl),
      stateCell,
      el("td", { class: "test" }, [tests, resultNode]),
      this._entityCell(entity),
    ]);
    this._fillLive(channel.number);
    this._renderResult(resultKey);
    return row;
  }

  _featureKey(device, channel) {
    return `${device.address}.${channel.entity_kind}.${channel.entity_number}`;
  }

  _featureEdit(device, channel) {
    const key = this._featureKey(device, channel);
    if (!this._edits[key]) {
      const t = this.t;
      const label = t.features[channel.entity_kind] || channel.kind;
      const base = channel.name || device.remark || device.address;
      let name = channel.entity_kind === "curtain" ? base : `${base} ${label.toLowerCase()}`;
      if (channel.entity_kind === "heating_zone") {
        name = channel.name || `${device.remark || device.address} ${format(t.zone, { n: channel.number }).toLowerCase()}`;
      } else if (channel.entity_kind === "floor_sensor") {
        name = channel.name || `${device.remark || device.address} ${t.floorSensorName} ${channel.number}`;
      }
      // A curtain that reported a position in the scan is controlled by position.
      const position = channel.kind === "curtain" && channel.level !== null && channel.level !== undefined;
      this._edits[key] = { checked: false, name, openingTime: 20, position };
    }
    return this._edits[key];
  }

  _renderFeatureTable(device) {
    const t = this.t;
    const channels = device.channels;
    const rows = channels.map((channel) => this._renderFeatureRow(device, channel));
    const table = el("table", { class: "outputs features" }, [
      el("thead", {}, el("tr", {}, ["", t.feature, t.columns.name, t.columns.type, t.columns.state, t.columns.test,
        t.columns.entity].map((text) => el("th", { text })))),
      el("tbody", {}, rows),
    ]);
    const addable = channels.filter((c) => c.entity_kind && !c.entity);
    const addButton = el("button", { class: "primary", onclick: () => this._addFeatures(device) });
    const updateCount = () => {
      const n = addable.filter((c) => this._featureEdit(device, c).checked).length;
      addButton.textContent = format(t.add, { n });
      addButton.disabled = n === 0;
    };
    this._updateCount = updateCount;
    updateCount();
    const parts = [el("div", { class: "table-wrap" }, table)];
    if (channels.some((c) => c.entity_kind === "floor_heating")) parts.push(el("div", { class: "info note", text: t.heatingNote }));
    if (channels.some((c) => c.kind === "heating_zone")) {
      parts.push(el("div", { class: "info note", text: t.heatingModuleNote }));
    }
    if (addable.length) parts.push(el("div", { class: "footer" }, [el("span"), addButton]));
    return el("div", {}, parts);
  }

  _renderFeatureRow(device, channel) {
    const t = this.t;
    const kind = channel.entity_kind;
    const entity = channel.entity;
    const label = this._featureLabel(channel);
    const stateCell = el("td", { class: "state" });
    const key = kind ? this._featureKey(device, channel) : `${device.address}.${channel.kind}.${channel.number}`;
    this._featureCells[key] = { cell: stateCell, device, channel };

    const target = { curtain: "curtain", heating_zone: "heating_zone" }[channel.kind];
    const resultKey = `${device.address}:${target}:${channel.number}`;
    const resultNode = el("div", { class: "result" });
    let tests = null;
    if (target) this._resultCells[resultKey] = resultNode;
    if (channel.kind === "curtain") {
      tests = el("div", { class: "tests" }, ["open", "stop", "close"].map((action) =>
        el("button", { class: "small", onclick: () => this._test(device, channel, "curtain", action), text: t[action] })));
      if (kind && this._featureEdit(device, channel).position) tests.append(...this._positionTest(device, channel));
    } else if (channel.kind === "heating_zone") {
      tests = this._zoneTests(device, channel);
    }

    if (!kind) {
      const row = el("tr", {}, [el("td", { class: "check" }), el("td", { class: "number", text: label }),
        el("td", { class: "name muted", text: channel.name || "—" }), el("td", { class: "type muted", text: t.notAddable }),
        stateCell, el("td", { class: "test" }, tests), el("td", { class: "entity muted", text: "—" })]);
      this._fillFeature(key);
      return row;
    }

    const edit = this._featureEdit(device, channel);
    const checkbox = el("input", {
      type: "checkbox", checked: edit.checked, disabled: Boolean(entity), "aria-label": `select ${kind}`,
      onchange: (e) => { edit.checked = e.target.checked; this._updateCount && this._updateCount(); },
    });
    const nameInput = el("input", {
      type: "text", value: entity && entity.name ? entity.name : edit.name, disabled: Boolean(entity),
      "aria-label": `name ${kind}`, oninput: (e) => { edit.name = e.target.value; },
    });
    const platform = FEATURE_PLATFORMS[kind] || "binary_sensor";
    const typeCell = el("td", { class: "type" }, [el("div", { class: "muted", text: t.platforms[platform] })]);
    if (kind === "curtain" && !entity) {
      typeCell.append(el("label", { class: "check note" }, [el("input", {
        type: "checkbox", checked: edit.position, "aria-label": "position control",
        onchange: (e) => { edit.position = e.target.checked; this._render(); },
      }), t.positionControl]));
      if (!edit.position) {
        typeCell.append(el("label", { class: "note" }, [`${t.openingTime} `, el("input", {
          type: "number", min: "1", max: "600", value: String(edit.openingTime), "aria-label": "opening time",
          oninput: (e) => { edit.openingTime = Number(e.target.value) || 20; },
        })]));
      }
    }
    const row = el("tr", {}, [
      el("td", { class: "check" }, checkbox),
      el("td", { class: "number", text: label }),
      el("td", { class: "name" }, nameInput),
      typeCell,
      stateCell,
      el("td", { class: "test" }, [tests, resultNode]),
      this._entityCell(entity),
    ]);
    this._fillFeature(key);
    this._renderResult(resultKey);
    return row;
  }

  _featureLabel(channel) {
    const t = this.t;
    if (channel.kind === "heating_zone") return format(t.zone, { n: channel.number });
    if (channel.kind === "floor_sensor") {
      return channel.zone ? format(t.floorSensorZone, { n: channel.number, zone: channel.zone })
        : format(t.floorSensor, { n: channel.number });
    }
    return channel.entity_kind ? t.features[channel.entity_kind]
      : `${t.kinds[channel.kind] || channel.kind} ${channel.number}`;
  }

  _positionTest(device, channel) {
    const key = `${device.address}:curtain_position:${channel.number}`;
    const known = this._liveCurtainPosition[channel.number];
    const fallback = known === undefined ? (channel.level === null || channel.level === undefined ? 50 : channel.level) : known;
    const input = el("input", {
      type: "number", min: "0", max: "100", class: "setpoint", "aria-label": `position ${channel.number}`,
      value: String(this._testValues[key] ?? fallback), oninput: (e) => { this._testValues[key] = e.target.value; },
    });
    return [input, el("button", {
      class: "small", text: this.t.goTo,
      onclick: () => this._test(device, channel, "curtain", "level", Number(input.value)),
    })];
  }

  _zoneTests(device, channel) {
    const t = this.t;
    const key = `${device.address}:heating_zone:${channel.number}`;
    const zone = this._liveZones[channel.number];
    const setpoint = el("input", {
      type: "number", min: "5", max: "35", value: String(this._testValues[key] ?? (zone && zone.target ? zone.target : 21)),
      class: "setpoint", "aria-label": `setpoint ${channel.number}`,
      oninput: (e) => { this._testValues[key] = e.target.value; },
    });
    return el("div", { class: "tests" }, [
      el("button", { class: "small", onclick: () => this._test(device, channel, "heating_zone", "on"), text: t.on }),
      el("button", { class: "small", onclick: () => this._test(device, channel, "heating_zone", "off"), text: t.off }),
      setpoint,
      el("button", {
        class: "small", text: t.setpoint,
        onclick: () => this._test(device, channel, "heating_zone", "level", Number(setpoint.value)),
      }),
    ]);
  }

  _entityCell(entity) {
    const t = this.t;
    if (entity && entity.source === "panel") {
      return el("td", { class: "entity" }, [
        el("div", { text: entity.entity_id || "…" }),
        el("button", { class: "small", onclick: () => this._remove(entity), text: t.remove }),
      ]);
    }
    if (entity) return el("td", { class: "entity", text: `${t.yaml}: ${entity.entity_id}` });
    return el("td", { class: "entity muted", text: "—" });
  }

  _featureText(channel) {
    const t = this.t;
    const s = this._liveSensor;
    switch (channel.entity_kind || channel.kind) {
      case "temperature": return s.temperature === undefined ? null : `${s.temperature} °C`;
      case "illuminance": return s.illuminance === undefined ? null : `${s.illuminance} lx`;
      case "motion": return s.motion === undefined ? null : (s.motion ? t.motionYes : t.motionNo);
      case "dry_contact_1":
      case "dry_contact_2": {
        const value = s[channel.entity_kind];
        return value === undefined ? null : (value ? t.stateOn : t.stateOff);
      }
      case "curtain": {
        const status = this._liveCurtain[channel.number];
        const position = this._liveCurtainPosition[channel.number];
        const parts = [];
        if (status !== undefined) parts.push(t.curtainStatus[status] || String(status));
        if (position !== undefined) parts.push(`${position} %`);
        return parts.length ? parts.join(" · ") : null;
      }
      case "heating_zone": {
        const z = this._liveZones[channel.number];
        if (z === undefined) return null;
        const current = z.temperature === null || z.temperature === undefined ? "" : `${z.temperature} °C → `;
        const valve = z.on && z.valve ? ` · ${t.valveOpen}` : "";
        return `${z.on ? t.heatingOn : t.heatingOff} · ${current}${z.target} °C (${t.presets[z.mode] || z.mode})${valve}`;
      }
      case "floor_sensor": {
        const value = this._liveFloor[channel.number];
        return value === undefined || value === null ? null : `${value} °C`;
      }
      case "floor_heating": {
        const h = this._liveHeating;
        if (h.status === undefined) return null;
        const setpoint = h[{ 1: "normal", 2: "day", 3: "night", 4: "away", 5: "normal" }[h.mode] || "normal"];
        const current = h.temperature === undefined ? "" : `${h.temperature} °C → `;
        return `${h.status ? t.heatingOn : t.heatingOff} · ${current}${setpoint} °C (${t.presets[h.mode] || h.mode})`;
      }
      default: return null;
    }
  }

  _fillFeature(key) {
    const entry = this._featureCells[key];
    if (!entry) return;
    const text = this._featureText(entry.channel);
    entry.cell.textContent = text === null ? "—" : text;
    const on = ["motion", "dry_contact_1", "dry_contact_2"].includes(entry.channel.entity_kind)
      && this._liveSensor[entry.channel.entity_kind];
    const zone = entry.channel.kind === "heating_zone" && this._liveZones[entry.channel.number];
    entry.cell.className = on || (entry.channel.entity_kind === "floor_heating" && this._liveHeating.status)
      || (zone && zone.on) ? "state on" : "state";
  }

  _renderUniversal(device) {
    const t = this.t;
    const state = this._universal;
    const resultKey = `${device.address}:universal_switch:input`;
    const resultNode = el("div", { class: "result" });
    this._resultCells[resultKey] = resultNode;
    this._renderResult(resultKey);  // a test result stays visible when the panel re-renders
    const numberInput = el("input", {
      type: "number", min: "1", max: "255", value: state.number, "aria-label": "universal switch number",
      oninput: (e) => { state.number = e.target.value; },
    });
    const nameInput = el("input", {
      type: "text", value: state.name, "aria-label": "universal switch name",
      placeholder: format(t.universalName, { n: state.number || "…" }), oninput: (e) => { state.name = e.target.value; },
    });
    const number = () => {
      const n = Number(state.number);
      return Number.isInteger(n) && n >= 1 && n <= 255 ? n : null;
    };
    const test = (action) => {
      const n = number();
      if (n === null) return;
      this._test(device, { number: n }, "universal_switch", action, undefined, resultKey);
    };
    const add = async (platform) => {
      const n = number();
      if (n === null) return;
      const result = await this._addEntities(device, [{ kind: "universal_switch", platform, channel: n,
        name: state.name.trim() || format(t.universalName, { n }) }]);
      if (result && result.added.length) {
        state.number = "";
        state.name = "";
        this._render();
      }
    };
    const existing = (device.universal_switches || []).map((item) => {
      const cell = el("span", { class: "state" });
      this._universalCells[item.number] = cell;
      this._fillUniversal(item.number);
      return el("div", { class: "row" }, [
        el("span", { text: `${t.universalNumber} ${item.number}` }), cell,
        el("span", { class: "entity", text: item.entity ? item.entity.entity_id || "…" : "—" }),
        item.entity ? el("button", { class: "small", onclick: () => this._remove(item.entity), text: t.remove }) : null,
      ]);
    });
    // Open when it is what the device is for (e.g. logic modules have no channels of their own).
    const open = Boolean(existing.length || state.number || !device.channels.length || device.category === "logic");
    return el("details", { class: "universal", open }, [
      el("summary", { text: t.universal }),
      el("div", { class: "note", text: t.universalHelp }),
      el("div", { class: "row" }, [
        el("label", {}, [`${t.universalNumber} `, numberInput]),
        el("button", { class: "small", onclick: () => test("on"), text: t.on }),
        el("button", { class: "small", onclick: () => test("off"), text: t.off }),
        nameInput,
        el("button", { class: "small", onclick: () => add("switch"), text: t.addAsSwitch }),
        el("button", { class: "small", onclick: () => add("binary_sensor"), text: t.addAsSensor }),
      ]),
      resultNode,
      ...existing,
    ]);
  }

  _fillUniversal(number) {
    const cell = this._universalCells[number];
    if (!cell) return;
    const value = this._liveUniversal[number];
    cell.textContent = value === undefined ? "—" : (value ? this.t.stateOn : this.t.stateOff);
    cell.className = value ? "state on" : "state";
  }

  async _addFeatures(device) {
    const entities = [];
    for (const channel of device.channels) {
      if (!channel.entity_kind || channel.entity) continue;
      const edit = this._featureEdit(device, channel);
      if (!edit.checked) continue;
      const kind = channel.entity_kind;
      const platform = FEATURE_PLATFORMS[kind] || "binary_sensor";
      const item = { kind, platform, channel: channel.entity_number, name: edit.name.trim() || this.t.features[kind] };
      if (kind === "curtain" && edit.position) item.position = true;
      else if (kind === "curtain") item.opening_time = edit.openingTime;
      entities.push(item);
    }
    await this._addEntities(device, entities);
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
    for (const key of Object.keys(this._featureCells)) this._fillFeature(key);
    for (const number of Object.keys(this._universalCells)) this._fillUniversal(Number(number));
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
