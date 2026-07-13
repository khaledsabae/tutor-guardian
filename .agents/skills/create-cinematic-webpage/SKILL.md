---
name: create-cinematic-webpage
description: >-
  Detailed guide for creating interactive, full-screen cinematic web pages using scroll-scrubbed videos/images, generating assets via Gemini, resolving mobile viewport and Tailwind CSS conflicts, and deploying via Docker.
---

# Creating a Cinematic Interactive Web Page (إنشاء صفحة ويب سينمائية تفاعلية)

This skill provides step-by-step instructions for creating a cinematic, scroll-driven interactive web page from scratch. It explains how to generate the visual assets (using Gemini), set up the Scroll-World JS engine, resolve critical mobile Safari and Tailwind CSS layout issues, and deploy the application.

## Overview
A cinematic interactive web page uses high-quality video or image scrubbing linked to the user's scroll depth to create a fluid, storytelling experience (similar to the Apple product showcase pages). This skill ensures another agent can build and deploy this entire setup successfully from scratch.

---

## Workflow Steps

### 1. Cinematic Asset Generation (Gemini)
To make the page feel premium and "wowed at first glance", generate all visual assets using Gemini (or Higgsfield tools when available):
* **Video Clips (Scrubbing)**: Generate short, high-fidelity 3D-rendered loops (H.264 MP4, 30fps) representing each section or concept of the app (e.g., interactive house dome, support avatars).
  * *Constraint*: Compress video clips to remain under 3MB to prevent load stutter on mobile networks.
  * *Required attributes*: Always use `<video muted playsinline preload="auto">` to allow programmatically scrubbing the video frames on iOS Safari without launching the native OS full-screen player.
* **Fallback Images**: Generate corresponding static images (JPEG/PNG) to serve as fallbacks for devices with reduced motion preferences or slow connections.

### 2. Core HTML Structure
Create a section container for the scroll world (e.g., `<div id="world"></div>`) and load GSAP, ScrollTrigger, Lenis (for smooth scrolling), and your CSS/JS engine files.
```html
<section id="tutor-journey">
  <div id="world"></div>
</section>

<!-- Smooth scrolling & animation libraries -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@studio-freight/lenis@1.0.42/dist/lenis.min.js"></script>

<!-- CSS & JS Scroll-World Engine (with cache-busting query strings) -->
<link rel="stylesheet" href="/ui/style.css?v=4" />
<script src="/ui/engine.js?v=4"></script>
```

### 3. Scroll-World Engine Configuration (`engine.js`)
Initialize the engine by mapping each generated video/image asset to its corresponding text copies, tags, and accent colors:
```javascript
document.addEventListener('DOMContentLoaded', () => {
  mountScrollWorld(document.getElementById('world'), {
    diveScroll: 1.6, // scroll speed factor per scene
    connScroll: 1.0,
    crossfade: 0.28,
    nav: true,
    sections: [
      {
        id: 'hero',
        label: 'البداية',
        clip: '/ui/assets/hero_clip.mp4',
        accent: '#8B7BB5',
        linger: 0.4,
        eyebrow: 'الذكاء التربوي الحارس',
        title: 'حماية ذكية وتوجيه سليم',
        body: 'مساعد تربوي ذكي يدمج بين الطب النفسي للطفل والتربية الإسلامية...',
        tags: ['ذكاء اصطناعي', 'حماية']
      },
      {
        id: 'medical',
        label: 'التوجيه النفسي',
        clip: '/ui/assets/medical_clip.mp4',
        accent: '#76A5AF',
        linger: 0.45,
        eyebrow: 'الرعاية النفسية والسلوكية',
        title: 'افهم سلوك أطفالك بحكمة وعلم',
        body: 'إرشادات فورية للتعامل مع تحديات السلوك والغضب...',
        tags: ['تعديل سلوكي', 'دعم نفسي']
      }
    ]
  });
});
```

### 4. Layout & Viewport Bug Mitigation (CSS Guidelines)
Apply the following strict styles in your CSS to prevent common rendering bugs on mobile devices:

#### A. Overriding Tailwind CSS Resets
Tailwind Preflight automatically sets `height: auto` on all video/img tags, which collapes full-screen video containers. Force sizing via `!important`:
```css
.sw-scene__video {
  position: absolute;
  top: 0;
  left: 0;
  width: 100% !important;
  height: 100% !important;
  display: block !important;
  object-fit: cover !important;
  object-position: center center;
  z-index: 5;
}
```

#### B. Dynamic Viewport Fallbacks
Mobile Safari drops `height: 100svh` on older versions, collapsing the layout. Always declare `100vh` first as a fallback:
```css
.sw-sticky-wrap {
  position: sticky;
  top: 0;
  width: 100%;
  height: 100vh;
  height: 100svh;
  overflow: hidden;
}
```

#### C. Absolute Positioning coordinates
Always specify `top: 0; left: 0;` for absolutely positioned elements inside flex or transformed containers:
```css
.sw-stage, .sw-scene, .sw-sky, .sw-copylayer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}
```

### 5. Deployment & Cache-Busting
* **Cache Busting**: Every time the stylesheet or JS engine files are updated, increment the version query parameter in the HTML file (e.g. change `?v=4` to `?v=5`) to force Cloudflare and mobile device browsers to bypass the cache.
* **VPS Deploy**: Pull changes and rebuild the Docker backend using Compose:
  ```bash
  ssh root@<VPS_IP> 'cd /root/tutor-guardian && \
    git fetch origin main && \
    git reset --hard origin/main && \
    docker compose -f docker-compose.production.yml stop backend && \
    docker compose -f docker-compose.production.yml build backend && \
    docker compose -f docker-compose.production.yml rm -f backend && \
    docker compose -f docker-compose.production.yml up -d backend'
  ```

---

## Troubleshooting Checklist
1. **Video cropped/collapsed in portrait mode?** Verify Tailwind CSS Preflight is loaded and add `!important` to `.sw-scene__video` layout styles.
2. **Blank space at the bottom on mobile?** Ensure `height: 100vh` fallback is declared before `height: 100svh`.
3. **Changes not appearing on mobile?** Increment the `?v=N` query string inside the main HTML file.
