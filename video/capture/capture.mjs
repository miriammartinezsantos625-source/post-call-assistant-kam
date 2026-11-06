// Walks one synthetic visit through the real local app and saves 2x screenshots
// for the promo video. Usage: node capture.mjs <puppeteer-core dir> <chrome path> <out dir>
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const [, , pptrDir, chromePath, outDir] = process.argv;
const require = createRequire(path.join(pptrDir, "package.json"));
const puppeteer = require(pptrDir);
const URL = "http://localhost:8502";
const NOTE =
  "Visita a la jefa de servicio de la cuenta 4. Objetivo: que acepte una sesión clínica sobre transición a adultos " +
  "antes de diciembre. Le ha parecido bien. Me comenta que una paciente suya, Ana López, ha tenido mareos desde que " +
  "empezó el tratamiento. Me pide el resumen de la guía en PDF. Vuelvo en tres semanas para cerrar la fecha.";

fs.mkdirSync(outDir, { recursive: true });
const browser = await puppeteer.launch({ executablePath: chromePath, headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900, deviceScaleFactor: 2 });

const hasText = (t, timeout = 30000) =>
  page.waitForFunction((s) => document.body.innerText.includes(s), { timeout }, t);
const idle = async () => {
  await new Promise((r) => setTimeout(r, 600));
  await page.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), { timeout: 240000 });
  await new Promise((r) => setTimeout(r, 900));
};
const shot = async (name, fullPage = false) => {
  await page.screenshot({ path: path.join(outDir, name), fullPage });
  console.log("saved", name);
};
const clickText = async (sel, text) => {
  const el = await page.waitForSelector(`${sel}::-p-text(${text})`, { timeout: 30000 });
  await el.click();
};

await page.goto(URL, { waitUntil: "networkidle2" });
await hasText("Del dictado a la");
await idle();

// Context: example N02 sets account 4 / jefe de servicio
await page.click('input[aria-label="Nota sintética de ejemplo (demo)"]');
await page.keyboard.type("N02");
await page.keyboard.press("Enter");
await idle();

// 01 · dictation mode
await clickText("button", "Dictar");
await idle();
await shot("01_dictar.png");

// 02 · the note (as it would arrive from the transcription)
await clickText("button", "Escribir");
await idle();
const ta = await page.waitForSelector('textarea[aria-label="Resumen"]');
await ta.click({ clickCount: 3 });
await page.keyboard.down("Meta"); await page.keyboard.press("A"); await page.keyboard.up("Meta");
await page.keyboard.press("Backspace");
await page.keyboard.type(NOTE);
await page.keyboard.press("Tab");
await idle();
await shot("02_nota.png");

// 03 · generate and review
const t0 = Date.now();
await clickText("button", "Generar ficha");
await hasText("Revisa, corrige", 300000);
await idle();
console.log("proposal seconds", ((Date.now() - t0) / 1000).toFixed(1));
await page.evaluate(() => window.scrollTo(0, 0));
await shot("03_revision.png");
await shot("03_revision_full.png", true);

// 04 · confirm every alert
const labels = ["He notificado a Farmacovigilancia", "He derivado la pregunta a Medical / Información Médica",
  "He derivado la solicitud a Medical / Información Médica"];
for (const l of labels) {
  const el = await page.$(`label::-p-text(${l})`);
  if (el) { await el.click(); await idle(); console.log("checked", l); }
}
await shot("04_panel_ok.png");
await shot("04_panel_ok_full.png", true);

// 05 · approve
const approve = await page.waitForSelector("button::-p-text(Aprobar y guardar)");
const disabled = await approve.evaluate((b) => b.disabled);
if (disabled) {
  console.log("APPROVE DISABLED: summary or alert needs attention");
  await shot("05_blocked_full.png", true);
  await browser.close();
  process.exit(2);
}
await approve.click();
await hasText("y lista para el CRM", 60000);
await idle();
await page.evaluate(() => window.scrollTo(0, 0));
await shot("05_salidas.png");
await shot("05_salidas_full.png", true);

// 06 · history for account 4
await page.goto(URL + "/page_history", { waitUntil: "networkidle2" });
await hasText("Historial y");
await idle();
await page.click('input[aria-label="Cuenta"]');
await page.keyboard.type("4 ·");
await page.keyboard.press("Enter");
await idle();
await shot("06_historial.png");
await shot("06_historial_full.png", true);

await browser.close();
