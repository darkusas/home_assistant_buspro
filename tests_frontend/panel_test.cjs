// Browser test of the HDL Buspro panel against a simulated Home Assistant WebSocket API.
// Run: node tests_frontend/panel_test.cjs [screenshot directory]
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const PANEL = path.join(__dirname, "..", "custom_components", "buspro", "frontend", "buspro-panel.js");
const SHOTS = process.argv[2];

// Runs in the page: a fake `hass` with callWS and connection.subscribeMessage.
function installMockHass() {
  const relay = (number, name, level, entity = null) => ({ number, kind: "relay", name, level, entity });
  const feature = (kind, number, entityKind, entityNumber = 1, name = null) => (
    { number, kind, name, level: null, entity_kind: entityKind, entity_number: entityNumber, entity: null });
  const liveReadings = {
    "1.30": [{ kind: "sensor", number: null, value: { temperature: 22, illuminance: 300, motion: true,
      dry_contact_1: false, dry_contact_2: true } }],
    "1.42": [{ kind: "floor_heating", number: null, value: { temperature: 22, status: 1, mode: 3, normal: 24, day: 21,
      night: 19, away: 18 } }],
    "1.40": [{ kind: "curtain", number: 1, value: 0 }],
    "1.204": [
      { kind: "heating_zone", number: 1, value: { on: true, mode: 1, timer: 0, temperature: 21, valve: false, normal: 21,
        day: 21, night: 20, away: 14, target: 21 } },
      { kind: "heating_zone", number: 3, value: { on: true, mode: 5, timer: 1, temperature: 22, valve: true, normal: 23,
        day: 22, night: 20, away: 16, target: 20 } },
      { kind: "floor_sensor", number: 1, value: 24 },
    ],
  };
  const zone = (number, name) => feature("heating_zone", number, "heating_zone", number, name);
  const floorSensor = (number, name, zoneNumber) => (
    { ...feature("floor_sensor", number, "floor_sensor", number, name), zone: zoneNumber });
  const scan = {
    duration: 41.2,
    ignored_sources: 1,
    devices: [
      { address: "1.89", type_code: "0x01AC", category: "output_module", remark: "Rėlės 1 aukštas",
        mac: "10:20:30:40:50:60:01:59", functions: [[1, 1, 4]],
        channels: [relay(1, "Virtuvė", 0), relay(2, "Koridorius", 100),
          relay(3, null, 0, { key: "1.89.3", source: "yaml", platform: "switch", entity_id: "switch.yaml_relay" }),
          relay(4, null, 0)] },
      { address: "1.20", type_code: "0x026D", category: "output_module", remark: "Dimeris <b>x</b>", mac: null,
        functions: [[1, 0, 2]], channels: [{ number: 1, kind: "dimmer", name: "Svetainė", level: 40, entity: null },
          { number: 2, kind: "dimmer", name: null, level: 0, entity: null }] },
      { address: "1.40", type_code: "0x02CF", category: "curtain_module", remark: "Užuolaidos", mac: null,
        functions: [[2, 2, 1]], channels: [feature("curtain", 1, "curtain", 1, "Langas A")] },
      { address: "1.30", type_code: "0x0134", category: "sensor", remark: "12in1", mac: null, functions: null,
        channels: [feature("temperature", 1, "temperature"), feature("illuminance", 1, "illuminance"),
          feature("motion", 1, "motion"), feature("dry_contact", 1, "dry_contact_1"),
          feature("dry_contact", 2, "dry_contact_2")] },
      { address: "1.42", type_code: "0x238C", category: "panel", remark: "2A Belos", mac: null,
        functions: [[4, 1, 8], [8, 1, 1]], channels: [feature("floor_heating", 1, "floor_heating")] },
      { address: "56.54", type_code: "0x0453", category: "logic", remark: "Logika", mac: null, functions: null,
        channels: [] },
      { address: "1.19", type_code: "0x1194", category: "unknown", remark: "AS1-2", mac: null, functions: null,
        channels: [] },
      { address: "1.204", type_code: "0x00CF", category: "floor_heating", remark: "Šildymas", mac: null,
        functions: [[8, 0, 6]], channels: [zone(1, "Sandėlis"), zone(2, null), zone(3, "Svetainė"),
          floorSensor(1, "Svetainės grindys", 3)] },
    ].map((d) => ({ universal_switches: [], override: null, ...d })),
  };
  const subscriptions = {};
  let scanned = false;
  window.wsCalls = [];
  const emit = (type, event) => (subscriptions[type] || []).forEach((cb) => cb(event));
  const device = (address) => scan.devices.find((d) => d.address === address);
  const slug = (text) => text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "_");

  const handlers = {
    "buspro/devices": () => ({ scanning: false, progress: null, scan: scanned ? JSON.parse(JSON.stringify(scan)) : null }),
    "buspro/scan/start": () => {
      setTimeout(() => emit("buspro/scan/subscribe", { event: "progress",
        progress: { phase: "discovery", devices: 3, done: 1, total: 2 } }), 30);
      setTimeout(() => { scanned = true; emit("buspro/scan/subscribe", { event: "done", devices: 4 }); }, 250);
      return null;
    },
    "buspro/device/refresh": (msg) => {
      const updates = liveReadings[msg.address]
        || device(msg.address).channels.map((c) => ({ kind: "channel", number: c.number, value: c.level }));
      setTimeout(() => emit(`state:${msg.address}`, { updates }), 10);
      return { levels: updates.map((u) => u.value) };
    },
    "buspro/channel/test": (msg) => {
      if (msg.target === "curtain") {
        const status = { open: 1, close: 2, stop: 0 }[msg.action];
        setTimeout(() => emit(`state:${msg.address}`, { updates: [{ kind: "curtain", number: msg.channel, value: status }] }), 10);
        return { confirmed: true, value: status, kind: "curtain", confirmed_by: "0xE3E1", latency: 0.021, error: null };
      }
      if (msg.target === "heating_zone") {
        const value = msg.action === "level" ? msg.level : (msg.action === "on" ? 1 : 0);
        return { confirmed: true, value, kind: "heating_zone", confirmed_by: "0x1C5D", latency: 0.021, error: null };
      }
      if (msg.target === "universal_switch") {
        const on = msg.action === "on";
        setTimeout(() => emit(`state:${msg.address}`, { updates: [{ kind: "universal_switch", number: msg.channel, value: on }] }), 10);
        return { confirmed: true, value: on ? 1 : 0, kind: "universal_switch", confirmed_by: "0xE01D", latency: 0.021,
          error: null };
      }
      if (msg.channel === 4) {
        return { confirmed: false, value: null, kind: "output", confirmed_by: null, latency: null,
          error: "No answer from the device" };
      }
      const value = { on: 100, off: 0, pulse: 100, level: msg.level }[msg.action];
      const channel = device(msg.address).channels.find((c) => c.number === msg.channel);
      channel.level = value;
      setTimeout(() => emit(`state:${msg.address}`, { updates: [{ kind: "channel", number: msg.channel, value }] }), 10);
      return { confirmed: true, value, kind: "output", confirmed_by: "0x0032", latency: 0.021, error: null };
    },
    "buspro/entities/add": (msg) => {
      const keys = [];
      for (const item of msg.entities) {
        const kind = item.kind || "output";
        const key = kind === "output" ? `${item.address}.${item.channel}` : `${item.address}.${kind}.${item.channel}`;
        const entity = { key, source: "panel", platform: item.platform, entity_id: `${item.platform}.${slug(item.name)}`,
          name: item.name };
        const d = device(item.address);
        if (kind === "universal_switch") d.universal_switches.push({ number: item.channel, entity });
        else if (kind === "output") d.channels.find((c) => c.number === item.channel).entity = entity;
        else d.channels.find((c) => c.entity_kind === kind && c.entity_number === item.channel).entity = entity;
        keys.push(key);
      }
      return { added: keys, rejected: [] };
    },
    // Like the server: the type applies to every device of that type code.
    "buspro/type_override/set": (msg) => {
      const override = { category: msg.category };
      if (msg.category === "output_module") override.kind = msg.kind;
      if (msg.count) override.count = msg.count;
      for (const d of scan.devices.filter((x) => x.type_code === msg.type_code)) {
        d.override = override;
        d.category = msg.category;
        d.channels = msg.category === "output_module"
          ? Array.from({ length: msg.count }, (_, i) => ({ number: i + 1, kind: msg.kind, name: null, level: 0, entity: null }))
          : [];
      }
      return { type_code: msg.type_code, override };
    },
    "buspro/type_override/remove": (msg) => {
      for (const d of scan.devices.filter((x) => x.type_code === msg.type_code)) {
        Object.assign(d, { override: null, category: "unknown", channels: [] });
      }
      return null;
    },
    "buspro/entities/remove": (msg) => {
      for (const d of scan.devices) {
        for (const c of d.channels) if (c.entity && msg.keys.includes(c.entity.key)) c.entity = null;
        d.universal_switches = d.universal_switches.filter((u) => !msg.keys.includes(u.entity.key));
      }
      return { removed: msg.keys };
    },
  };

  window.mockHass = {
    language: "lt",
    callWS: async (msg) => {
      window.wsCalls.push(msg);
      const handler = handlers[msg.type];
      if (!handler) throw { code: "unknown_command", message: msg.type };
      return handler(msg);
    },
    connection: {
      subscribeMessage: async (callback, msg) => {
        window.wsCalls.push(msg);
        const key = msg.type === "buspro/state/subscribe" ? `state:${msg.address}` : msg.type;
        (subscriptions[key] = subscriptions[key] || []).push(callback);
        return () => { subscriptions[key] = subscriptions[key].filter((cb) => cb !== callback); };
      },
    },
  };
}

const PAGE = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0"><script type="module" src="/buspro-panel.js"></script><buspro-panel></buspro-panel></body></html>`;

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
  const errors = [];
  page.on("pageerror", (err) => errors.push(err.message));
  const dialogs = [];
  page.on("dialog", (dialog) => { dialogs.push(dialog.message()); dialog.accept(); });
  await page.route("http://panel.test/**", (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/buspro-panel.js") {
      return route.fulfill({ contentType: "text/javascript", body: fs.readFileSync(PANEL, "utf8") });
    }
    return route.fulfill({ contentType: "text/html", body: PAGE });
  });
  await page.addInitScript(installMockHass);
  await page.goto("http://panel.test/");
  await page.evaluate(async () => {
    await customElements.whenDefined("buspro-panel");
    document.querySelector("buspro-panel").hass = window.mockHass;
  });
  const panel = page.locator("buspro-panel");
  const calls = (type) => page.evaluate((t) => window.wsCalls.filter((m) => m.type === t), type);
  const shot = async (name) => SHOTS && page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });

  // Before any scan.
  await panel.getByText("Magistralė dar neskanuota").waitFor();
  await shot("1-empty");

  // Scan: progress, then the device list (output modules first, others behind the filter).
  await panel.getByRole("button", { name: "Skanuoti magistralę" }).click();
  await panel.getByText("Ieškoma įrenginių (1/2) · rasta: 3").waitFor();
  await panel.getByText("1.89 · Rėlės 1 aukštas").waitFor();
  assert.strictEqual(await panel.locator(".device").count(), 2);
  await panel.getByLabel("filter").selectOption("all");
  assert.strictEqual(await panel.locator(".device").count(), 8);

  // Relay module: names from the device, live state, YAML channel locked.
  await panel.getByText("1.89 · Rėlės 1 aukštas").click();
  await panel.locator("td.state").nth(1).getByText("Įjungta").waitFor();
  assert.strictEqual(await panel.getByLabel("name 1").inputValue(), "Virtuvė");
  assert.strictEqual(await panel.getByLabel("name 4").inputValue(), "Rėlės 1 aukštas 4");
  assert.strictEqual(await panel.getByLabel("type 1").inputValue(), "switch");
  assert.ok(await panel.getByLabel("select 3").isDisabled());
  await panel.getByText("YAML: switch.yaml_relay").waitFor();

  // ON test: warning first time only, confirmation and live state.
  const row = (n) => panel.locator("tbody tr").nth(n - 1);
  await row(1).getByRole("button", { name: "ĮJ" }).click();
  await row(1).getByText("✔ 100 % · 0x0032 · 21 ms").waitFor();
  await row(1).locator("td.state").getByText("Įjungta").waitFor();
  await row(1).getByRole("button", { name: "IŠJ" }).click();
  await row(1).locator("td.state").getByText("Išjungta").waitFor();
  assert.strictEqual(dialogs.length, 1);
  assert.ok(dialogs[0].startsWith("Testas realiai perjungs"));
  await row(4).getByRole("button", { name: "Impulsas" }).click();
  await row(4).getByText("✖ Įrenginys neatsakė").waitFor();
  const tests = await calls("buspro/channel/test");
  assert.deepStrictEqual(tests.map((m) => [m.channel, m.action]), [[1, "on"], [1, "off"], [4, "pulse"]]);
  await shot("2-relay");

  // Select, rename, change type and add.
  await panel.getByLabel("select 1").check();
  await panel.getByLabel("select 2").check();
  await panel.getByLabel("name 2").fill("Koridoriaus lubos");
  await panel.getByLabel("type 2").selectOption("light_onoff");
  await panel.getByRole("button", { name: "Pridėti pasirinktus (2)" }).click();
  await panel.getByText("Pridėta entity: 2.").waitFor();
  const [add] = await calls("buspro/entities/add");
  assert.deepStrictEqual(add.entities, [
    { platform: "switch", dimmable: false, address: "1.89", channel: 1, name: "Virtuvė", device_name: "Rėlės 1 aukštas",
      device_model: "0x01AC", device_category: "output_module", mac: "10:20:30:40:50:60:01:59" },
    { platform: "light", dimmable: false, address: "1.89", channel: 2, name: "Koridoriaus lubos",
      device_name: "Rėlės 1 aukštas", device_model: "0x01AC", device_category: "output_module",
      mac: "10:20:30:40:50:60:01:59" },
  ]);
  await panel.getByText("switch.virtuve").waitFor();
  await panel.getByText("light.koridoriaus_lubos").waitFor();
  assert.ok(await panel.getByLabel("select 1").isDisabled());
  assert.strictEqual(await row(2).locator("td.type").innerText(), "Šviestuvas");  // not the default for a relay
  await shot("3-added");

  // Remove asks first.
  await row(1).getByRole("button", { name: "Pašalinti" }).click();
  await panel.getByLabel("select 1").and(page.locator(":enabled")).waitFor();
  assert.deepStrictEqual((await calls("buspro/entities/remove"))[0].keys, ["1.89.1"]);
  assert.ok(dialogs[1].startsWith("Pašalinti switch.virtuve"));

  // Dimmer: light by default, names from the bus are shown as text, not HTML.
  await panel.getByText("1.20 · Dimeris <b>x</b>").click();
  assert.strictEqual(await panel.getByLabel("type 1").inputValue(), "light");
  assert.strictEqual(await panel.locator("b").count(), 0);
  await panel.locator("td.state").first().getByText("40 %").waitFor();
  await panel.getByLabel("level 2").fill("60");
  await row(2).getByText("✔ 60 % · 0x0032 · 21 ms").waitFor();

  const lastAdd = async () => (await calls("buspro/entities/add")).pop().entities;

  // Curtain module: live status, test, opening time, add as a cover.
  await panel.getByText("1.40 · Užuolaidos").click();
  await panel.locator("td.state").getByText("Stop").waitFor();
  await panel.getByRole("button", { name: "▲" }).click();
  await panel.getByText("✔ Atidaroma · 0xE3E1 · 21 ms").waitFor();
  await panel.locator("td.state").getByText("Atidaroma").waitFor();
  await panel.getByLabel("opening time").fill("35");
  await panel.getByLabel("select curtain").check();
  await panel.getByRole("button", { name: "Pridėti pasirinktus (1)" }).click();
  await panel.getByText("cover.langas_a").waitFor();
  assert.deepStrictEqual(await lastAdd(), [{ kind: "curtain", platform: "cover", channel: 1, name: "Langas A",
    opening_time: 35, address: "1.40", device_name: "Užuolaidos", device_model: "0x02CF",
    device_category: "curtain_module", mac: null }]);

  // 12-in-1 sensor: live readings, then add temperature and motion.
  await panel.getByText("1.30 · 12in1").click();
  await panel.getByText("22 °C").waitFor();
  await panel.getByText("300 lx").waitFor();
  const featureRow = (label) => panel.locator("tbody tr", { hasText: label });
  assert.strictEqual(await featureRow("Sausas kontaktas 2").locator("td.state").innerText(), "Įjungta");
  assert.strictEqual(await featureRow("Sausas kontaktas 1").locator("td.state").innerText(), "Išjungta");
  await panel.getByLabel("select temperature").check();
  await panel.getByLabel("select motion").check();
  await panel.getByRole("button", { name: "Pridėti pasirinktus (2)" }).click();
  await panel.getByText("binary_sensor.12in1_judesys").waitFor();
  assert.deepStrictEqual((await lastAdd()).map((e) => [e.kind, e.platform, e.channel, e.name, e.device_category]), [
    ["temperature", "sensor", 1, "12in1 temperatūra", "sensor"], ["motion", "binary_sensor", 1, "12in1 judesys", "sensor"]]);
  await shot("6-sensor");

  // DLP panel: floor heating state and the note that control is not yet proven.
  await panel.getByText("1.42 · 2A Belos").click();
  await panel.getByText("Šildo · 22 °C → 19 °C (nakties)").waitFor();
  await panel.getByText("Šildymo skaitymas patikrintas įrašais").waitFor();

  // Logic module: no channels, but universal switches can be tested and added.
  await panel.getByText("56.54 · Logika").click();
  await panel.getByText("Šis įrenginys neturi kanalų").waitFor();
  await panel.getByLabel("universal switch number").fill("100");
  await panel.locator("details.universal").getByRole("button", { name: "ĮJ" }).click();
  await panel.getByText("✔ Įjungta · 0xE01D · 21 ms").waitFor();
  const universalTest = (await calls("buspro/channel/test")).pop();
  assert.deepStrictEqual([universalTest.target, universalTest.action, universalTest.channel],
    ["universal_switch", "on", 100]);
  await panel.getByLabel("universal switch name").fill("Režimas");
  await panel.getByRole("button", { name: "Pridėti kaip jungiklį" }).click();
  await panel.getByText("switch.rezimas").waitFor();
  assert.deepStrictEqual((await lastAdd()).map((e) => [e.kind, e.platform, e.channel, e.name]),
    [["universal_switch", "switch", 100, "Režimas"]]);
  assert.strictEqual(await panel.getByLabel("universal switch number").inputValue(), "");  // ready for the next one
  await shot("7-universal");

  // Floor heating module: zones and floor sensors with live values, zone tests, add as climate and sensor.
  await panel.getByText("1.204 · Šildymas").click();
  await panel.getByText("Šildo · 22 °C → 20 °C (laikmatis) · vožtuvas atidarytas").waitFor();
  await panel.getByText("Šildo · 21 °C → 21 °C (normalus)").waitFor();
  await panel.getByText("Grindų termometras 1 · zona 3").waitFor();
  await panel.locator("td.state").getByText("24 °C").waitFor();
  await panel.getByText("Valdymas atliekamas pagal HDL dokumentaciją").waitFor();
  assert.strictEqual(await panel.getByLabel("name heating_zone").nth(1).inputValue(), "Šildymas zona 2");  // unnamed zone
  const zoneRow = (n) => panel.locator("tbody tr", { has: page.locator("td.number", { hasText: new RegExp(`^Zona ${n}$`) }) });
  await zoneRow(3).getByRole("button", { name: "IŠJ" }).click();
  await zoneRow(3).getByText("✔ Išjungta · 0x1C5D · 21 ms").waitFor();
  await panel.getByLabel("setpoint 3").fill("21");
  await zoneRow(3).getByRole("button", { name: "Nustatyti" }).click();
  await zoneRow(3).getByText("✔ 21 °C · 0x1C5D · 21 ms").waitFor();
  assert.deepStrictEqual((await calls("buspro/channel/test")).slice(-2).map((m) => [m.target, m.channel, m.action, m.level]),
    [["heating_zone", 3, "off", undefined], ["heating_zone", 3, "level", 21]]);
  await zoneRow(3).getByLabel("select heating_zone").check();
  await panel.getByLabel("select floor_sensor").check();
  await panel.getByRole("button", { name: "Pridėti pasirinktus (2)" }).click();
  await panel.getByText("climate.svetaine").waitFor();
  assert.deepStrictEqual((await lastAdd()).map((e) => [e.kind, e.platform, e.channel, e.name, e.device_category]), [
    ["heating_zone", "climate", 3, "Svetainė", "floor_heating"],
    ["floor_sensor", "sensor", 1, "Svetainės grindys", "floor_heating"]]);
  await shot("9-floor-heating");

  // Unknown device: its type code is shown and its type can be set by hand.
  await panel.locator(".device", { hasText: "1.19 · AS1-2" }).getByText("Nežinomas · 0x1194").waitFor();
  await panel.getByText("1.19 · AS1-2").click();
  await panel.getByText("Taikoma visiems 0x1194 tipo įrenginiams").waitFor();  // open for unknown devices
  assert.strictEqual(await panel.getByLabel("override category").inputValue(), "output_module");
  await panel.getByLabel("override category").selectOption("curtain_module");
  await panel.getByText("Užuolaidų sk.").waitFor();
  assert.strictEqual(await panel.getByLabel("override kind").count(), 0);  // relay/dimmer is for output modules
  await panel.getByLabel("override category").selectOption("output_module");
  await panel.getByLabel("override kind").selectOption("dimmer");
  await panel.getByLabel("override count").fill("99");
  await panel.getByRole("button", { name: "Išsaugoti tipą" }).click();
  await panel.getByText("Kanalų skaičius turi būti nuo 1 iki 64.").waitFor();
  assert.strictEqual((await calls("buspro/type_override/set")).length, 0);
  await panel.getByLabel("override count").fill("4");
  await panel.getByRole("button", { name: "Išsaugoti tipą" }).click();
  await panel.getByText("Tipas 0x1194 išsaugotas.").waitFor();
  assert.deepStrictEqual((await calls("buspro/type_override/set")).map(({ id, ...m }) => m), [
    { type: "buspro/type_override/set", type_code: "0x1194", category: "output_module", kind: "dimmer", count: 4 }]);
  await panel.getByText("Išėjimų modulis · rankinis tipas · 0x1194").waitFor();
  assert.strictEqual(await panel.locator("table.outputs tbody tr").count(), 4);
  assert.strictEqual(await panel.getByLabel("type 1").inputValue(), "light");  // dimmer channels default to lights
  await shot("8-override");
  await panel.getByRole("button", { name: "Grąžinti automatinį" }).click();
  await panel.getByText("Tipui 0x1194 vėl naudojamas automatinis atpažinimas.").waitFor();
  await panel.getByText("Šis įrenginys neturi kanalų").waitFor();
  assert.deepStrictEqual((await calls("buspro/type_override/remove")).map((m) => m.type_code), ["0x1194"]);

  // Dark theme and phone width, for the screenshots.
  await panel.getByText("1.89 · Rėlės 1 aukštas").click();
  await page.evaluate(() => {
    const style = document.querySelector("buspro-panel").style;
    style.setProperty("--primary-background-color", "#111111");
    style.setProperty("--card-background-color", "#1c1c1c");
    style.setProperty("--primary-text-color", "#e1e1e1");
    style.setProperty("--secondary-text-color", "#9b9b9b");
    style.setProperty("--divider-color", "rgba(225, 225, 225, 0.12)");
  });
  await shot("4-dark");
  await page.setViewportSize({ width: 390, height: 844 });
  await shot("5-phone");
  // On a phone every channel is a card, so its test buttons are on screen.
  const box = await row(4).getByRole("button", { name: "Impulsas" }).boundingBox();
  assert.ok(box.x + box.width <= 390, `test button is off screen at x=${box.x}`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  assert.ok(overflow <= 0, `page scrolls sideways by ${overflow}px on a phone`);

  assert.deepStrictEqual(errors, []);
  await browser.close();
  console.log("panel test passed");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
