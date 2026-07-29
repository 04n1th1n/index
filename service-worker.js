/* Service worker del Aparthotel Paros.
 *
 * Tres estrategias, segun lo que se pida:
 *
 *   /api/...        -> SIEMPRE red, nunca cache. Son los datos en vivo del
 *                      hotel: servir una ocupacion cacheada seria peor que
 *                      no funcionar.
 *   navegacion      -> stale-while-revalidate. Pinta al instante desde cache
 *                      y baja la version nueva por detras, asi que un
 *                      despliegue en Render se ve en la siguiente recarga
 *                      sin tocar nada a mano.
 *   estaticos y CDN -> cache-first. Iconos, manifest, fuentes y Font Awesome
 *                      no cambian; una vez cacheados, la app abre sin red.
 *
 * Al cambiar CACHE_VERSION se borran todas las caches anteriores.
 */

const CACHE_VERSION = 'paros-v1';

// El HTML va aparte: se revalida en segundo plano, los estaticos no.
const APP_SHELL = [
  '/',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

// Origenes externos que si conviene cachear (fuentes e iconos de la interfaz).
const CDN_HOSTS = [
  'fonts.googleapis.com',
  'fonts.gstatic.com',
  'cdnjs.cloudflare.com',
];

// ---------------------------------------------------------------
//  Instalacion: precachear el esqueleto de la app
// ---------------------------------------------------------------
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      // addAll falla entero si un solo recurso falla; con este map cada uno va
      // por su cuenta y un 401 en '/' no aborta toda la instalacion.
      .then((cache) => Promise.all(
        APP_SHELL.map((url) => cache.add(url).catch((err) => {
          console.warn('[SW] No se pudo precachear', url, err);
        }))
      ))
      .then(() => self.skipWaiting())
  );
});

// ---------------------------------------------------------------
//  Activacion: tirar las caches de versiones viejas
// ---------------------------------------------------------------
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((nombres) => Promise.all(
        nombres
          .filter((nombre) => nombre !== CACHE_VERSION)
          .map((nombre) => caches.delete(nombre))
      ))
      .then(() => self.clients.claim())
  );
});

// ---------------------------------------------------------------
//  Estrategias
// ---------------------------------------------------------------

/** Guarda en cache solo respuestas utiles: un 401 o un 502 cacheado dejaria
 *  la app rota hasta que caduque la cache. */
function esCacheable(respuesta) {
  return respuesta && respuesta.ok && respuesta.status === 200;
}

/** Devuelve lo cacheado ya mismo y actualiza por detras para la proxima visita. */
async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_VERSION);
  const cacheada = await cache.match(request);

  const enRed = fetch(request)
    .then((respuesta) => {
      if (esCacheable(respuesta)) {
        cache.put(request, respuesta.clone());
      }
      return respuesta;
    })
    .catch(() => null);

  // Si no hay nada cacheado todavia (primera visita) hay que esperar a la red.
  if (cacheada) {
    // No await: la actualizacion sigue sola mientras la pagina ya se pinta.
    enRed.catch(() => {});
    return cacheada;
  }

  const respuesta = await enRed;
  if (respuesta) return respuesta;

  // Sin cache y sin red: al menos devolver algo legible en vez de un fallo seco.
  return new Response(
    '<!doctype html><meta charset="utf-8">' +
    '<body style="font-family:sans-serif;background:#060a14;color:#f0f0f5;' +
    'display:grid;place-items:center;height:100vh;margin:0;text-align:center">' +
    '<div><h1>Sin conexión</h1>' +
    '<p>Abre la aplicación una vez con internet para poder usarla sin red.</p></div>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}

/** Cache primero; si no esta, red y se guarda. */
async function cacheFirst(request) {
  const cache = await caches.open(CACHE_VERSION);
  const cacheada = await cache.match(request);
  if (cacheada) return cacheada;

  try {
    const respuesta = await fetch(request);
    if (esCacheable(respuesta)) {
      cache.put(request, respuesta.clone());
    }
    return respuesta;
  } catch (err) {
    // Cross-origin sin CORS devuelve respuestas opacas (status 0) que no
    // podemos inspeccionar; si tampoco hay red, no hay nada que ofrecer.
    return Response.error();
  }
}

// ---------------------------------------------------------------
//  Router
// ---------------------------------------------------------------
self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Un POST no se cachea: /api/update tiene que llegar al servidor siempre.
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Los datos del hotel nunca se cachean.
  if (url.origin === self.location.origin && url.pathname.startsWith('/api/')) {
    return; // sin respondWith: lo gestiona el navegador como siempre
  }

  // El documento HTML: rapido desde cache, actualizado por detras.
  if (request.mode === 'navigate') {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // Estaticos propios y CDN conocidos.
  const esPropio = url.origin === self.location.origin;
  const esCDN = CDN_HOSTS.includes(url.hostname);
  if (esPropio || esCDN) {
    event.respondWith(cacheFirst(request));
  }
});
