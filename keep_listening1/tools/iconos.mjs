// Genera, con solo los íconos de Bootstrap Icons que aparecen en templates,
// JS y Python:
//   - static/scss/abstracts/_iconos-usados.scss (las reglas .bi-*)
//   - static/fonts/bootstrap-icons-kl.woff2 (la fuente recortada a esos íconos)
//
// El set completo son ~2000 íconos (100 KB de CSS y 134 KB de fuente); el sitio
// usa menos de 100 (unos 10 KB de fuente). Se corre con `npm run iconos` cada
// vez que se usa un ícono nuevo; los dos archivos quedan en el repo (el build de
// Docker no ve los templates). Recortar la fuente necesita Python con fonttools
// y brotli (`pip install fonttools brotli`); sin eso, se avisa y no se toca.

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, extname } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("..", import.meta.url));
const CARPETAS = ["templates", "static/js", "musica", "tienda", "usuarios", "panel"];
const EXTENSIONES = new Set([".html", ".js", ".py"]);
const IGNORAR = new Set(["vendor", "node_modules", "migrations", "__pycache__"]);

function archivos(carpeta) {
  const lista = [];
  if (!existsSync(carpeta)) return lista;
  for (const nombre of readdirSync(carpeta)) {
    if (IGNORAR.has(nombre)) continue;
    const ruta = join(carpeta, nombre);
    if (statSync(ruta).isDirectory()) lista.push(...archivos(ruta));
    else if (EXTENSIONES.has(extname(nombre))) lista.push(ruta);
  }
  return lista;
}

const mapa = JSON.parse(readFileSync(join(RAIZ, "node_modules/bootstrap-icons/font/bootstrap-icons.json"), "utf8"));
const usados = new Set();
for (const carpeta of CARPETAS) {
  for (const archivo of archivos(join(RAIZ, carpeta))) {
    for (const [, nombre] of readFileSync(archivo, "utf8").matchAll(/\bbi-([a-z0-9-]+)/g)) {
      if (mapa[nombre] !== undefined) usados.add(nombre);
    }
  }
}

const reglas = [...usados].sort().map((nombre) => {
  const codigo = mapa[nombre].toString(16);
  return `.bi-${nombre}::before { content: "\\${codigo}"; }`;
});

const salida = `// ---------------------------------------------------------------------------
// GENERADO por tools/iconos.mjs (npm run iconos). No editar a mano.
// ${usados.size} íconos de Bootstrap Icons que usa el sitio.
// ---------------------------------------------------------------------------

@font-face {
  font-display: swap;
  font-family: "bootstrap-icons";
  src: url("../fonts/bootstrap-icons-kl.woff2") format("woff2");
}

.bi::before,
[class^="bi-"]::before,
[class*=" bi-"]::before {
  display: inline-block;
  font-family: bootstrap-icons !important;
  font-style: normal;
  font-weight: normal !important;
  font-variant: normal;
  text-transform: none;
  line-height: 1;
  vertical-align: -.125em;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

${reglas.join("\n")}
`;

writeFileSync(join(RAIZ, "static/scss/abstracts/_iconos-usados.scss"), salida);
console.log(`Íconos: ${usados.size} de ${Object.keys(mapa).length}`);

// La fuente, recortada a los mismos íconos.
const codigos = [...usados].map((nombre) => `U+${mapa[nombre].toString(16).toUpperCase()}`).join(",");
const recorte = spawnSync("python", [
  "-m", "fontTools.subset",
  join(RAIZ, "node_modules/bootstrap-icons/font/fonts/bootstrap-icons.woff2"),
  `--unicodes=${codigos}`,
  "--flavor=woff2",
  "--layout-features=",
  "--no-hinting",
  `--output-file=${join(RAIZ, "static/fonts/bootstrap-icons-kl.woff2")}`,
], { stdio: "inherit" });
if (recorte.status === 0) {
  const peso = statSync(join(RAIZ, "static/fonts/bootstrap-icons-kl.woff2")).size;
  console.log(`Fuente recortada: ${(peso / 1024).toFixed(1)} KB`);
} else {
  console.warn("No se pudo recortar la fuente (¿falta `pip install fonttools brotli`?). Queda la anterior.");
}
