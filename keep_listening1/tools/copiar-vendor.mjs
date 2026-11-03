/* ---------------------------------------------------------------------------
 * Copia a static/ los archivos de terceros que sirve Django.
 *
 * Reemplaza al `mkdir -p ... && cp ...` que tenia el script "vendor": esos
 * comandos no existen en el cmd.exe de Windows, asi que `npm run build`
 * fallaba en cualquier maquina que no fuera Linux o macOS.
 * ------------------------------------------------------------------------- */
import { cp, mkdir, readdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const desde = (...partes) => join(raiz, "node_modules", ...partes);
const hacia = (...partes) => join(raiz, "static", ...partes);

// Fuentes de Nunito que usa la hoja de estilos (pesos 400, 600, 700 y 800).
const PESOS_NUNITO = ["400", "600", "700", "800"];

async function copiarCarpeta(origen, destino, filtro = () => true) {
  const archivos = await readdir(origen);
  let copiados = 0;
  for (const archivo of archivos) {
    if (!filtro(archivo)) continue;
    await cp(join(origen, archivo), join(destino, archivo));
    copiados += 1;
  }
  return copiados;
}

await mkdir(hacia("js", "vendor"), { recursive: true });
await mkdir(hacia("fonts"), { recursive: true });

// El .map va junto al .js: el bundle lo referencia al final del archivo y
// collectstatic con manifiesto falla si esa referencia no se puede resolver.
for (const archivo of ["bootstrap.bundle.min.js", "bootstrap.bundle.min.js.map"]) {
  await cp(desde("bootstrap", "dist", "js", archivo), hacia("js", "vendor", archivo));
  console.log(`${archivo} -> static/js/vendor/`);
}

// La fuente de íconos no se copia entera: `npm run iconos` genera
// static/fonts/bootstrap-icons-kl.woff2 solo con los íconos que se usan.

const nunito = await copiarCarpeta(
  desde("@fontsource", "nunito", "files"),
  hacia("fonts"),
  (archivo) =>
    PESOS_NUNITO.some((peso) => archivo === `nunito-latin-${peso}-normal.woff2`),
);
console.log(`${nunito} archivo(s) de Nunito -> static/fonts/`);

const PESOS_SYNE = ["600", "700", "800"];
const syne = await copiarCarpeta(
  desde("@fontsource", "syne", "files"),
  hacia("fonts"),
  (archivo) =>
    PESOS_SYNE.some((peso) => archivo === `syne-latin-${peso}-normal.woff2`),
);
console.log(`${syne} archivo(s) de Syne -> static/fonts/`);
