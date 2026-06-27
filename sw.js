var C='nazwozbior-v14',U=[
  '/','/index.html','/dane.js',
  '/css/main.css', '/css/base.css',
  '/js/constants.js','/js/utils.js','/js/data.js','/js/state.js',
  '/js/pool.js','/js/descriptions.js','/js/details.js','/js/render.js',
  '/js/csv.js','/js/events.js'
];
self.addEventListener('install',function(e){e.waitUntil(caches.open(C).then(function(c){return c.addAll(U)}));self.skipWaiting()});
self.addEventListener('activate',function(e){e.waitUntil(caches.keys().then(function(ks){return Promise.all(ks.filter(function(k){return k!==C}).map(function(k){return caches.delete(k)}))}).then(function(){return clients.claim()}))});
self.addEventListener('fetch',function(e){
  if(e.request.method!=='GET')return;
  if(new URL(e.request.url).origin!==location.origin)return;
  e.respondWith(fetch(e.request).then(function(r){
    if(r.ok){var cp=r.clone();caches.open(C).then(function(c){c.put(e.request,cp)});}
    return r;
  }).catch(function(){return caches.match(e.request)}));
});
