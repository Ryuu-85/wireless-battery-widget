const path = require("path");
const http = require("http");
const fs = require("fs");
const childProcess = require("child_process");

function printResult(result) {
  process.stdout.write(JSON.stringify(result));
}

let printed = false;
function finish(result, exitCode = 0) {
  if (printed) return;
  printed = true;
  printResult(result);
  process.exit(exitCode);
}

setTimeout(() => {
  finish({ ok: false, error: "timeout" });
}, 16000).unref();

function loadModule(modulePath) {
  return require(modulePath);
}

function loadHid(primaryPath, fallbackNodeModules) {
  try {
    return require(primaryPath);
  } catch {}
  if (fallbackNodeModules) {
    return require(path.join(fallbackNodeModules, "node-hid"));
  }
  return require("node-hid");
}

function getJson(url, timeoutMs = 1500) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let body = "";
      res.on("data", (chunk) => {
        body += chunk;
      });
      res.on("end", () => {
        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(error);
        }
      });
    });
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error("timeout"));
    });
    req.on("error", reject);
  });
}

async function evaluateCdp(wsUrl, expression, timeoutMs = 2500) {
  if (typeof WebSocket === "undefined") return null;
  return await new Promise((resolve) => {
    let done = false;
    const finish = (value) => {
      if (done) return;
      done = true;
      try {
        ws.close();
      } catch {}
      resolve(value);
    };
    const ws = new WebSocket(wsUrl);
    const timer = setTimeout(() => finish(null), timeoutMs);
    let id = 1;
    const pending = new Map();
    ws.onopen = () => {
      ws.send(JSON.stringify({ id: id++, method: "Runtime.enable" }));
      const evalId = id++;
      pending.set(evalId, true);
      ws.send(
        JSON.stringify({
          id: evalId,
          method: "Runtime.evaluate",
          params: { expression, returnByValue: true, awaitPromise: true },
        }),
      );
    };
    ws.onerror = () => finish(null);
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (!pending.has(message.id)) return;
        clearTimeout(timer);
        finish(message.result && message.result.result ? message.result.result.value : null);
      } catch {
        finish(null);
      }
    };
  });
}

function parseAtkPageBattery(text) {
  if (!text) return null;
  const patterns = [
    /V75\s*Series[\s\S]{0,80}?(\d{1,3})\s*%/i,
    /ATK\s*V75X[\s\S]{0,80}?(\d{1,3})\s*%/i,
    /VXE\s*V75X[\s\S]{0,80}?(\d{1,3})\s*%/i,
  ];
  for (const pattern of patterns) {
    const match = String(text).match(pattern);
    if (!match) continue;
    const level = Number(match[1]);
    if (Number.isInteger(level) && level >= 0 && level <= 100) return level;
  }
  return null;
}

function parseAtkPageState(text) {
  if (!text) return null;
  const level = parseAtkPageBattery(text);
  if (Number.isInteger(level)) return { level, status: "online" };
  if (/V75\s*Series|ATK\s*V75X|VXE\s*V75X/i.test(String(text)) && /休眠|sleep/i.test(String(text))) {
    return { level: null, status: "sleeping" };
  }
  return null;
}

async function readFromAtkDebugPage(port) {
  try {
    const pages = await getJson(`http://127.0.0.1:${port}/json`);
    const page = pages.find((item) => item.title === "ATK HUB") || pages.find((item) => item.type === "page");
    if (!page || !page.webSocketDebuggerUrl) return null;
    const text = await evaluateCdp(page.webSocketDebuggerUrl, "document.body.innerText");
    return parseAtkPageState(text);
  } catch {
    return null;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForDebugPage(port, timeoutMs = 9000) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    const state = await readFromAtkDebugPage(port);
    if (state) return state;
    await sleep(500);
  }
  return null;
}

async function startAtkDebugPage(atkHubPath, port, profilePath) {
  try {
    const exePath = path.join(atkHubPath, "ATK HUB.exe");
    if (!fs.existsSync(exePath)) return;
    const args = [
      `--remote-debugging-port=${port}`,
      "--remote-allow-origins=*",
    ];
    if (profilePath) {
      fs.mkdirSync(profilePath, { recursive: true });
      const configPath = path.join(profilePath, "config.json");
      if (!fs.existsSync(configPath)) {
        fs.writeFileSync(
          configPath,
          JSON.stringify({ setting: { startMinimized: true, closeMinimizeTray: true } }, null, 2),
        );
      }
      args.unshift(`--user-data-dir=${profilePath}`);
      args.push("--hidden");
    }
    const child = childProcess.spawn(
      exePath,
      args,
      {
        cwd: atkHubPath,
        detached: true,
        stdio: "ignore",
        windowsHide: true,
      },
    );
    child.on("error", () => {});
    child.unref();
  } catch {}
}

function decodeBattery(controller, report) {
  const looksLikeAck =
    report.includes(255) &&
    report.length >= 12 &&
    report.slice(12).every((value) => value === 0);
  if (looksLikeAck) {
    return null;
  }
  const attempts = [
    () => controller.receiveDeviceBattery(report, report.length),
    () => controller.receiveDeviceBattery(report.slice(1), report.length - 1),
  ];
  for (const attempt of attempts) {
    try {
      const decoded = attempt();
      if (typeof decoded === "number") return decoded;
      if (decoded && typeof decoded.batteryLevel === "number") return decoded.batteryLevel;
      if (decoded && typeof decoded.level === "number") return decoded.level;
      if (Array.isArray(decoded)) {
        const match = decoded.find((value) => Number.isInteger(value) && value >= 0 && value <= 100);
        if (match !== undefined) return match;
      }
    } catch {}
  }
  return null;
}

function padReport(reportId, payload) {
  const data = [reportId, ...payload];
  while (data.length < 64) data.push(0);
  return data.slice(0, 64);
}

async function main() {
  const atkHubPath = process.argv[2] || "E:\\software\\ATK HUB";
  const debugPort = Number(process.argv[4] || process.env.ATK_HUB_DEBUG_PORT || 9224);
  const debugProfilePath = process.argv[5] || "";
  const allowStart = (process.argv[6] || "").toLowerCase() === "start";
  if (!fs.existsSync(path.join(atkHubPath, "ATK HUB.exe"))) {
    finish({ ok: false, error: `ATK HUB not found: ${atkHubPath}` });
    return;
  }
  const pageLevel = await readFromAtkDebugPage(debugPort);
  if (pageLevel) {
    finish({ ok: true, level: pageLevel.level, status: pageLevel.status, source: "ATK HUB page" });
    return;
  }
  if (allowStart) {
    await startAtkDebugPage(atkHubPath, debugPort, debugProfilePath);
    const startedPageLevel = await waitForDebugPage(debugPort);
    if (startedPageLevel) {
      finish({ ok: true, level: startedPageLevel.level, status: startedPageLevel.status, source: "ATK HUB page" });
      return;
    }
  }

  const nodeModules = path.join(atkHubPath, "resources", "app.asar.unpacked", "node_modules");
  const keyLinkerPath = path.join(nodeModules, "key-linker-lib");
  const hidPath = path.join(nodeModules, "node-hid");
  const fallbackNodeModules = process.argv[3] || "";

  if (fallbackNodeModules) {
    process.env.NODE_PATH = fallbackNodeModules;
    require("module").Module._initPaths();
  }

  const keylib = loadModule(keyLinkerPath);
  const HID = loadHid(hidPath, fallbackNodeModules);
  const controller = new keylib.KeyLinkerLibController();
  const command = controller.readDeviceBattery();
  const devices = HID.devices().filter((device) => {
    return device.vendorId === 0x320f && (device.productId === 0x5055 || device.productId === 0x5088);
  });
  const targets = devices.filter((device) => device.usagePage === 65308 || device.usage === 128 || device.usagePage >= 0xff00);

  for (const device of targets) {
    let handle;
    try {
      handle = new HID.HID(device.path);
      try {
        handle.setNonBlocking(1);
      } catch {}

      const writes = [padReport(4, command), padReport(0, command), padReport(1, command), padReport(102, command)];
      for (const payload of writes) {
        try {
          handle.write(payload);
        } catch {
          continue;
        }
        for (let i = 0; i < 6; i++) {
          const report = handle.readTimeout ? handle.readTimeout(250) : [];
          if (!report || !report.length) continue;
          const level = decodeBattery(controller, report);
          if (Number.isInteger(level) && level >= 0 && level <= 100) {
            finish({ ok: true, level, source: "ATK HUB HID" });
            return;
          }
        }
      }
    } catch (error) {
      // Keep probing other HID collections.
    } finally {
      try {
        if (handle) handle.close();
      } catch {}
    }
  }

  finish({ ok: false });
}

try {
  main().catch((error) => {
    finish({ ok: false, error: String(error && error.message ? error.message : error) });
  });
} catch (error) {
  finish({ ok: false, error: String(error && error.message ? error.message : error) });
}
