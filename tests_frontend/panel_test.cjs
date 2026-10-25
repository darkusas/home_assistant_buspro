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
        functions: [[2, 2, 1]], channels: [{ number: 1, kind: "curtain", name: "Langas A", level: null }] },
      { address: "1.30", type_code: "0x0134", category: "sensor", remark: "12in1", mac: null, functions: null,
        channels: [] },
    ],
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
      const updates = device(msg.address).channels.map((c) => ({ kind: "channel", number: c.number, value: c.level }));
      setTimeout(() => emit(`state:${msg.address}`, { updates }), 10);
      return { levels: updates.map((u) => u.value) };
    },
    "buspro/channel/test": (msg) => {
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
      for (const item of msg.entities) {
        device(item.address).channels.find((c) => c.number === item.channel).entity = {
          key: `${item.address}.${item.channel}`, source: "panel", platform: item.platform,
          entity_id: `${item.platform}.${slug(item.name)}`, name: item.name };
      }
      return { added: msg.entities.map((e) => `${e.address}.${e.channel}`), rejected: [] };
    },
    "buspro/entities/remove": (msg) => {
      for (const d of scan.devices) for (const c of d.channels) if (c.entity && msg.keys.includes(c.entity.key)) c.entity = null;
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
  assert.strictEqual(await panel.locator(".device").count(), 4);

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
    { platform: "switch", dimmable: false, address: "1.89", channel: 1, name: "Virtuvė",
      device_name: "Rėlės 1 aukštas", device_model: "0x01AC", mac: "10:20:30:40:50:60:01:59" },
    { platform: "light", dimmable: false, address: "1.89", channel: 2, name: "Koridoriaus lubos",
      device_name: "Rėlės 1 aukštas", device_model: "0x01AC", mac: "10:20:30:40:50:60:01:59" },
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

  // Curtain module: testable, not addable yet.
  await panel.getByText("1.40 · Užuolaidos").click();
  await panel.getByText("Šio tipo įrenginių pridėjimas bus vėlesniame etape").waitFor();
  await panel.getByRole("button", { name: "▲" }).click();
  const curtain = (await calls("buspro/channel/test")).pop();
  assert.deepStrictEqual([curtain.target, curtain.action, curtain.channel], ["curtain", "open", 1]);

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
