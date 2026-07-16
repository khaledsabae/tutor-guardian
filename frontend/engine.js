/* ============================================================================
   Tutor Guardian Scroll-World JS Engine (Video-Scrub & Image Fallback)
   Now supports TWO modes:
     1. Single continuous "journey" video — smooth scroll-scrub like alsaba.cloud
     2. Legacy multi-clip per segment — original per-scene clip swapping
   ============================================================================ */

function mountScrollWorld(container, config) {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const coarse = window.matchMedia('(hover: none) and (pointer: coarse)').matches;
  const smallMQ = window.matchMedia('(max-width: 860px)');
  const isMobile = () => coarse || smallMQ.matches;

  const SECTIONS = config.sections || [];
  const CONNECTORS = config.connectors || [];
  const CONNECTORS_M = config.connectorsMobile || [];
  const DIVE_W = config.diveScroll || 1.5;
  const CONN_W = config.connScroll || 1.0;
  const CROSSFADE = (config.crossfade != null) ? config.crossfade : 0.25;
  const N = SECTIONS.length;
  if (!N) return;

  const JOURNEY_MODE = !!config.journey;

  container.classList.add('sw-root');

  // ---- 1. Build the interleaved segment chain (dives and connectors) ----
  const SEGMENTS = [];
  SECTIONS.forEach((s, i) => {
    const dive = {
      kind: 'dive',
      si: i,
      clip: s.clip,
      clipM: s.clipMobile,
      still: s.still,
      accent: s.accent,
      w: s.scroll || DIVE_W,
      linger: s.linger || 0,
      timeStart: s.timeStart != null ? s.timeStart : null,
      timeEnd: s.timeEnd != null ? s.timeEnd : null
    };
    SEGMENTS.push(dive);
    s._seg = dive;

    if (i < N - 1 && CONNECTORS[i]) {
      SEGMENTS.push({
        kind: 'conn',
        si: i,
        clip: CONNECTORS[i],
        clipM: CONNECTORS_M[i],
        still: SECTIONS[i + 1].still,
        accent: SECTIONS[i + 1].accent,
        w: CONN_W,
        timeStart: null,
        timeEnd: null
      });
    }
  });
  const NSEG = SEGMENTS.length;

  // ---- 2. Create DOM elements ----
  const sky = el('div', 'sw-sky');
  if (config.atmosphere !== false) {
    sky.appendChild(el('div', 'sw-sky__grad'));
    sky.appendChild(el('div', 'sw-sky__glow'));
  }
  const particles = el('div', 'sw-particles');
  sky.appendChild(particles);

  const scrollbar = el('div', 'sw-scrollbar');
  const scrollbarFill = el('span');
  scrollbar.appendChild(scrollbarFill);

  const topbar = el('div', 'sw-topbar');
  if (config.brand) {
    const brand = el('a', 'sw-brand');
    brand.href = config.brand.href || '#top';
    brand.appendChild(el('span', 'sw-brand__mark'));
    const nm = el('span', 'sw-brand__name');
    nm.textContent = config.brand.name || '';
    brand.appendChild(nm);
    topbar.appendChild(brand);
  }

  const nav = el('nav', 'sw-nav');
  if (config.nav !== false) topbar.appendChild(nav);

  if (config.cta && config.cta.label) {
    const c = el('a', 'sw-topcta');
    c.href = config.cta.href || '#';
    c.textContent = config.cta.label;
    topbar.appendChild(c);
  }

  const stage = el('div', 'sw-stage');
  const copylayer = el('div', 'sw-copylayer');
  const route = el('div', 'sw-route');

  const hint = el('div', 'sw-hint');
  const hintText = el('span');
  hintText.textContent = config.hint || 'انزل للأسفل للاستكشاف';
  hint.appendChild(hintText);
  hint.appendChild(el('i'));

  const track = el('div', 'sw-track');

  const stickyWrap = el('div', 'sw-sticky-wrap');
  [sky, scrollbar, topbar, stage, copylayer, route, hint].forEach(n => stickyWrap.appendChild(n));

  container.appendChild(stickyWrap);
  container.appendChild(track);

  // Build scenes in the stage
  SEGMENTS.forEach(s => {
    const scene = el('div', 'sw-scene');
    scene.style.setProperty('--sw-accent', s.accent || '');

    let img = null;
    if (!JOURNEY_MODE && !s.clip && s.still) {
      img = el('img', 'sw-scene__still');
      img.alt = '';
      img.decoding = 'async';
      img.loading = 'lazy';
      img.src = s.still;
      scene.appendChild(img);
    }

    stage.appendChild(scene);

    s.el = scene;
    s.img = img;
    s.video = null;
    s.hasClip = false;
    s.loading = false;
    s.ready = false;
    s.cur = 0;
    s.target = 0;
    s.visible = false;
  });

  // ---- Single continuous journey video ----
  let journeyVideo = null;
  let journeyDuration = 1;
  let journeyReady = false;
  let journeyLoading = false;

  if (JOURNEY_MODE) {
    const firstScene = SEGMENTS[0].el;
    const v = document.createElement('video');
    v.className = 'sw-scene__video';
    v.muted = true;
    v.playsInline = true;
    v.preload = 'auto';
    v.src = config.journey;
    v.style.opacity = '0';
    v.setAttribute('muted', '');
    v.setAttribute('playsinline', '');
    firstScene.appendChild(v);
    journeyVideo = v;
    journeyLoading = true;

    v.addEventListener('loadedmetadata', () => {
      journeyDuration = v.duration || 1;
      journeyReady = true;
      journeyLoading = false;
      v.style.opacity = '1';
      SEGMENTS.forEach(s => {
        s.el.classList.add('has-clip');
        s.hasClip = true;
        s.ready = true;
        if (s.img) { s.img.remove(); s.img = null; }
      });
      read();
    }, { once: true });

    v.addEventListener('loadeddata', () => {
      if (userReady) primeVideo(v);
    }, { once: true });

    v.addEventListener('error', (e) => {
      console.warn('Journey video failed to load:', config.journey, e);
      journeyLoading = false;
    }, { once: true });
  }

  // Build content copy and route indicators
  const copies = [], dots = [];
  SECTIONS.forEach((s, i) => {
    const c = el('article', 'sw-copy');
    c.style.setProperty('--sw-accent', s.accent || '');

    c.innerHTML =
      `<span class="sw-copy__num">${pad(i + 1)} / ${pad(N)}</span>` +
      (s.eyebrow ? `<span class="sw-copy__eyebrow">${esc(s.eyebrow)}</span>` : '') +
      (s.title ? `<h2 class="sw-copy__title">${esc(s.title)}</h2>` : '') +
      (s.body ? `<p class="sw-copy__body">${esc(s.body)}</p>` : '') +
      (s.tags && s.tags.length ? `<ul class="sw-copy__tags">${s.tags.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : '') +
      (s.cta ? `<div class="sw-copy__cta">${ctaBtns(s.cta)}</div>` : '');

    copylayer.appendChild(c);
    copies.push(c);

    const dot = el('button', 'sw-route__dot');
    dot.style.setProperty('--sw-accent', s.accent || '');
    dot.innerHTML = `<span class="sw-route__label">${esc(s.label || '')}</span><i></i>`;
    dot.addEventListener('click', () => jumpTo(i));
    route.appendChild(dot);
    dots.push(dot);

    if (config.nav !== false) {
      const b = el('button', 'sw-nav__item');
      b.textContent = s.label || '';
      b.addEventListener('click', () => jumpTo(i));
      nav.appendChild(b);
    }
  });

  // ---- 3. Mathematics & Logic ----
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const smooth = x => { x = clamp(x); return x * x * (3 - 2 * x); };

  const lingerEase = (x, L) => {
    L = clamp(L);
    const c = x - 0.5;
    return (1 - L) * x + L * (4 * c * c * c + 0.5);
  };

  let vh = window.innerHeight, totalW = 0, activeIndex = -1, ticking = false;
  let laidOutW = window.innerWidth;
  let stageX = window.innerWidth > 860 ? 4 : 0;

  function layout() {
    vh = window.innerHeight;
    laidOutW = window.innerWidth;
    stageX = window.innerWidth > 860 ? 4 : 0;

    let off = 0;
    SEGMENTS.forEach(s => {
      s.start = off * vh;
      off += s.w;
      s.end = off * vh;
    });
    totalW = off;

    track.style.height = (totalW * vh + vh) + 'px';
    read();
  }

  function jumpTo(i) {
    if (!container) return;
    const seg = SECTIONS[i]._seg;
    const containerTop = container.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({
      top: containerTop + seg.start + (seg.end - seg.start) * 0.45,
      behavior: reduce ? 'auto' : 'smooth'
    });
  }

  function loadClip(s) {
    if (JOURNEY_MODE || reduce || s.loading || !s.clip) return;
    s.loading = true;

    const url = (isMobile() && s.clipM) ? s.clipM : s.clip;

    fetch(url)
      .then(r => r.ok ? r.blob() : Promise.reject(new Error('404')))
      .then(blob => {
        const v = document.createElement('video');
        v.className = 'sw-scene__video';
        v.muted = true;
        v.playsInline = true;
        v.preload = 'auto';
        v.setAttribute('muted', '');
        v.setAttribute('playsinline', '');
        v.src = URL.createObjectURL(blob);

        v.addEventListener('loadedmetadata', () => { s.ready = true; read(); });

        v.addEventListener('seeked', () => {
          s.el.classList.add('has-clip');
          if (s.img) { s.img.remove(); s.img = null; }
        }, { once: true });

        v.addEventListener('loadeddata', () => {
          try { v.pause(); } catch (e) {}
          if (userReady) primeVideo(v);
        });

        s.el.appendChild(v);
        s.video = v;
        s.hasClip = true;
      })
      .catch((err) => {
        console.warn('Failed to load clip:', url, err);
        s.loading = false;
      });
  }

  function getSegmentLocal(y) {
    let ci = 0;
    for (let i = 0; i < NSEG; i++) {
      if (y >= SEGMENTS[i].start) ci = i;
    }
    const s = SEGMENTS[ci];
    const local = clamp((y - s.start) / (s.end - s.start), 0, 1);
    return { seg: s, local: s.linger ? lingerEase(local, s.linger) : local, ci: ci };
  }

  function read() {
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const y = -rect.top;
    const fade = CROSSFADE * vh;

    const { seg: curSeg, local: curLocal, ci } = getSegmentLocal(y);

    // 1. Calculate Scene Transforms & Video Lazy Loading
    for (let i = 0; i < NSEG; i++) {
      const s = SEGMENTS[i];

      if (!JOURNEY_MODE && y > s.start - 1.6 * vh && y < s.end + 1.6 * vh) {
        loadClip(s);
      }

      const local = clamp((y - s.start) / (s.end - s.start), 0, 1);
      s.target = s.linger ? lingerEase(local, s.linger) : local;

      let opacity = 0;
      if (y >= s.start && y <= s.end) {
        opacity = 1.0;
      } else if (y < s.start && y >= s.start - fade) {
        opacity = clamp((y - (s.start - fade)) / fade, 0, 1);
      } else if (y > s.end && y <= s.end + fade) {
        opacity = clamp(((s.end + fade) - y) / fade, 0, 1);
      }

      const op = smooth(opacity);
      s.el.style.opacity = op;
      
      // In single journey mode the background video lives in the first scene
      // and must remain visible for the entire scroll-world duration.
      if (JOURNEY_MODE && i === 0) {
        s.el.style.opacity = '1';
        s.el.classList.add('is-visible');
      }
      
      const isVisible = op > 0.001 || (JOURNEY_MODE && i === 0);
      s.visible = isVisible;
      s.el.classList.toggle('is-visible', isVisible);
      s.el.style.zIndex = (JOURNEY_MODE && i === 0) ? '200' : ((i === ci) ? '120' : String(100 + Math.round(op * 10)));

      if ((!s.hasClip || !s.ready) && s.img) {
        const sc = reduce ? 1.0 : 0.9 + local * 1.5;
        s.img.style.transform = `scale(${sc.toFixed(3)})`;
        s.img.style.filter = `drop-shadow(0 20px 45px rgba(0, 0, 0, 0.08))`;
      }

      if (s.video) {
        const sc = reduce ? 1.0 : 1.0 + local * 0.2;
        s.video.style.transform = `scale(${sc.toFixed(3)})`;
      }
    }

    // 2. Calculate Content Copy Fades
    for (let i = 0; i < N; i++) {
      const seg = SECTIONS[i]._seg;
      const pr = clamp((y - seg.start) / (seg.end - seg.start), 0, 1);

      let cop = 0;
      if (y >= seg.start && y <= seg.end) {
        if (pr < 0.25) {
          cop = pr / 0.25;
        } else if (pr > 0.75) {
          cop = (1.0 - pr) / 0.25;
        } else {
          cop = 1.0;
        }
      }

      const smoothCop = smooth(cop);
      const c = copies[i];
      c.style.opacity = smoothCop;
      c.style.transform = reduce ? 'none' : `translateY(${(0.5 - pr) * 8}vh)`;
      c.style.pointerEvents = smoothCop > 0.5 ? 'auto' : 'none';
      c.classList.toggle('is-active', smoothCop > 0.5);
    }

    // 3. Update active indices, scrollbar, topbar context
    const near = clamp(
      curSeg.kind === 'dive' ? curSeg.si
        : (((y - curSeg.start) / (curSeg.end - curSeg.start)) > 0.5 ? curSeg.si + 1 : curSeg.si),
      0, N - 1
    );

    if (near !== activeIndex) {
      activeIndex = near;
      dots.forEach((d, k) => d.classList.toggle('is-active', k === near));
      nav.querySelectorAll('.sw-nav__item').forEach((n, k) => n.classList.toggle('is-active', k === near));
      container.style.setProperty('--sw-accent', SECTIONS[near].accent || '');
    }

    scrollbarFill.style.transform = `scaleX(${clamp(y / (totalW * vh))})`;
    hint.style.opacity = clamp(1 - y / (0.3 * vh));

    if (particles && !reduce) {
      particles.style.transform = `translate3d(0, ${-y * 0.08}px, 0)`;
    }

    // 4. Journey video scrub
    if (JOURNEY_MODE && journeyReady && journeyVideo) {
      const eps = isMobile() ? 0.04 : 0.015;
      const ts = curSeg.timeStart;
      const te = curSeg.timeEnd;
      let t;
      if (ts != null && te != null) {
        t = ts + curLocal * (te - ts);
      } else {
        t = (y / (totalW * vh)) * journeyDuration;
      }
      t = clamp(t, 0, journeyDuration - 0.001);
      if (Math.abs(journeyVideo.currentTime - t) > eps && !journeyVideo.seeking) {
        try { journeyVideo.currentTime = t; } catch (e) {}
      }
    }

    ticking = false;
  }

  // Animation frame loop for smoother rendering transitions and legacy video scrubbing
  function raf() {
    const eps = isMobile() ? 0.02 : 0.008;

    for (let i = 0; i < NSEG; i++) {
      const s = SEGMENTS[i];

      if (!JOURNEY_MODE && s.hasClip && s.ready && s.video) {
        if (s.video.seeking) continue;
        if (!s.visible && Math.abs(s.cur - s.target) < 0.002) continue;

        s.cur += (s.target - s.cur) * (reduce ? 1.0 : 0.23);
        const dur = s.video.duration || 1;
        const t = clamp(s.cur, 0, 0.999) * dur;

        if (Math.abs(s.video.currentTime - t) > eps) {
          try { s.video.currentTime = t; } catch (e) {}
        }
      } else {
        if (s.img && Math.abs(s.cur - s.target) > 0.001) {
          s.cur += (s.target - s.cur) * (reduce ? 1.0 : 0.15);
        }
      }
    }

    requestAnimationFrame(raf);
  }

  // iOS needs a user gesture before muted videos will decode/paint reliably.
  let userReady = false;
  function primeVideo(v) {
    if (!isMobile() || !v) return;
    try {
      const p = v.play();
      if (p && p.then) {
        p.then(() => { try { v.pause(); } catch (e) {} }).catch(() => {});
      }
    } catch (e) {}
  }

  function onFirstGesture() {
    if (userReady) return;
    userReady = true;
    if (JOURNEY_MODE && journeyVideo) primeVideo(journeyVideo);
    else SEGMENTS.forEach(s => { if (s.video) primeVideo(s.video); });
  }

  window.addEventListener('pointerdown', onFirstGesture, { once: true, passive: true });
  window.addEventListener('touchstart', onFirstGesture, { once: true, passive: true });

  seedParticles(particles, reduce || coarse);

  window.addEventListener('scroll', () => {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(read);
    }
  }, { passive: true });

  function onResize() {
    if (coarse && window.innerWidth === laidOutW) return;
    layout();
  }

  window.addEventListener('resize', onResize);
  window.addEventListener('orientationchange', layout);
  window.addEventListener('load', layout);

  layout();
  requestAnimationFrame(raf);

  // ---- Helper Functions ----
  function el(tag, cls) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    return n;
  }

  function pad(n) {
    return String(n).padStart(2, '0');
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'
    }[c]));
  }

  function ctaBtns(cta) {
    let h = '';
    if (cta.primary) {
      h += `<a class="sw-btn sw-btn--primary" href="${esc(cta.primary.href || '#')}">${esc(cta.primary.label)}</a>`;
    }
    if (cta.secondary) {
      h += `<a class="sw-btn sw-btn--ghost" href="${esc(cta.secondary.href || '#')}">${esc(cta.secondary.label)}</a>`;
    }
    return h;
  }
}

function seedParticles(host, reduce) {
  if (!host || reduce) return;
  const kinds = ['dot', 'dot', 'ring'];
  const seeds = [7, 23, 41, 58, 71, 88, 12, 34, 52, 66, 83, 95, 18, 29, 47, 63, 77, 91, 5, 38, 55, 69, 82, 97];

  for (let k = 0; k < 25; k++) {
    const s = document.createElement('span');
    s.className = 'sw-pt sw-pt--' + kinds[k % kinds.length];
    s.style.left = seeds[k % seeds.length] + 'vw';
    s.style.top = ((seeds[(k * 3) % seeds.length] * 1.3) % 100) + 'vh';
    s.style.setProperty('--sw-sc', (0.5 + ((seeds[(k * 5) % seeds.length] % 60) / 60) * 1.1).toFixed(2));

    const dur = 14 + (seeds[(k * 7) % seeds.length] % 22);
    s.style.animationDuration = dur + 's';
    s.style.animationDelay = (-(seeds[(k * 2) % seeds.length] % dur)) + 's';

    host.appendChild(s);
  }
}

if (typeof window !== 'undefined') {
  window.mountScrollWorld = mountScrollWorld;
}
