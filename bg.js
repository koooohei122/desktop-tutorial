// ─── BACKGROUND CANVAS ───
const bgCanvas = document.getElementById('bg-canvas');
const bgCtx = bgCanvas.getContext('2d');

function resizeBg() {
  bgCanvas.width = window.innerWidth;
  bgCanvas.height = window.innerHeight;
}
resizeBg();
window.addEventListener('resize', resizeBg);

const particles = [];
for (let i = 0; i < 100; i++) {
  particles.push({
    x: Math.random() * window.innerWidth,
    y: Math.random() * window.innerHeight,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
    r: Math.random() * 1.5 + 0.5,
    alpha: Math.random() * 0.4 + 0.1,
    color: Math.random() > 0.5 ? '0, 245, 255' : '0, 102, 255',
  });
}

function drawGrid(ctx, w, h, t) {
  ctx.strokeStyle = 'rgba(0, 245, 255, 0.025)';
  ctx.lineWidth = 1;
  const spacing = 80;
  const ox = (t * 0.02) % spacing, oy = (t * 0.015) % spacing;
  for (let x = -spacing + ox; x < w + spacing; x += spacing) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
  }
  for (let y = -spacing + oy; y < h + spacing; y += spacing) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }
}

let bgT = 0;
function animateBg() {
  bgT++;
  const w = bgCanvas.width, h = bgCanvas.height;
  bgCtx.clearRect(0, 0, w, h);
  const grad = bgCtx.createRadialGradient(w*0.3, h*0.3, 0, w*0.5, h*0.5, w*0.8);
  grad.addColorStop(0, 'rgba(0,20,50,0.4)');
  grad.addColorStop(1, 'rgba(2,8,16,0)');
  bgCtx.fillStyle = grad;
  bgCtx.fillRect(0, 0, w, h);
  drawGrid(bgCtx, w, h, bgT);
  particles.forEach(p => {
    p.x += p.vx; p.y += p.vy;
    if (p.x < 0) p.x = w; if (p.x > w) p.x = 0;
    if (p.y < 0) p.y = h; if (p.y > h) p.y = 0;
    bgCtx.beginPath();
    bgCtx.arc(p.x, p.y, p.r, 0, Math.PI*2);
    bgCtx.fillStyle = `rgba(${p.color},${p.alpha})`;
    bgCtx.fill();
  });
  for (let i = 0; i < particles.length; i++) {
    for (let j = i+1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x;
      const dy = particles[i].y - particles[j].y;
      const dist = Math.sqrt(dx*dx + dy*dy);
      if (dist < 100) {
        bgCtx.beginPath();
        bgCtx.moveTo(particles[i].x, particles[i].y);
        bgCtx.lineTo(particles[j].x, particles[j].y);
        bgCtx.strokeStyle = `rgba(0,245,255,${0.06*(1-dist/100)})`;
        bgCtx.lineWidth = 0.5; bgCtx.stroke();
      }
    }
  }
  requestAnimationFrame(animateBg);
}
animateBg();

// ─── CITY MAP CANVAS (metaverse page only) ───
const cityCanvas = document.getElementById('city-canvas');
if (cityCanvas) {
  const cityCtx = cityCanvas.getContext('2d');
  function resizeCity() {
    const rect = cityCanvas.parentElement.getBoundingClientRect();
    cityCanvas.width = rect.width || 360;
    cityCanvas.height = rect.height || 360;
  }
  resizeCity();
  window.addEventListener('resize', resizeCity);

  const buildings = [];
  function initBuildings() {
    buildings.length = 0;
    const w = cityCanvas.width, h = cityCanvas.height;
    const rows = 8, cols = 8;
    const cw = w/cols, ch = h/rows;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (Math.random() > 0.3) {
          buildings.push({
            x: c*cw+cw*0.15, y: r*ch+ch*0.15,
            w: cw*0.7*(0.6+Math.random()*0.4),
            h: ch*0.7*(0.6+Math.random()*0.4),
            pulse: Math.random()*Math.PI*2,
            speed: 0.01+Math.random()*0.02,
          });
        }
      }
    }
  }
  initBuildings();

  let cityT = 0;
  function animateCity() {
    cityT += 0.02;
    const w = cityCanvas.width, h = cityCanvas.height;
    cityCtx.clearRect(0, 0, w, h);
    cityCtx.fillStyle = '#04091a';
    cityCtx.fillRect(0, 0, w, h);
    cityCtx.strokeStyle = 'rgba(0,245,255,0.08)';
    cityCtx.lineWidth = 1;
    const gw = w/8, gh = h/8;
    for (let i = 0; i <= 8; i++) {
      cityCtx.beginPath(); cityCtx.moveTo(i*gw,0); cityCtx.lineTo(i*gw,h); cityCtx.stroke();
      cityCtx.beginPath(); cityCtx.moveTo(0,i*gh); cityCtx.lineTo(w,i*gh); cityCtx.stroke();
    }
    buildings.forEach(b => {
      b.pulse += b.speed;
      const glow = (Math.sin(b.pulse)+1)/2;
      cityCtx.fillStyle = 'rgba(0,40,80,0.8)';
      cityCtx.fillRect(b.x, b.y, b.w, b.h);
      cityCtx.strokeStyle = `rgba(0,245,255,${(0.3+glow*0.5)*0.6})`;
      cityCtx.lineWidth = 0.5;
      cityCtx.strokeRect(b.x, b.y, b.w, b.h);
      const wR = Math.floor(b.h/8), wC = Math.floor(b.w/8);
      for (let r = 0; r < wR; r++) {
        for (let c = 0; c < wC; c++) {
          if (Math.random() > 0.4) {
            const wa = (Math.sin(b.pulse+r*0.5+c*0.3)+1)/2;
            cityCtx.fillStyle = `rgba(0,200,255,${wa*0.6})`;
            cityCtx.fillRect(b.x+c*8+1, b.y+r*8+1, 4, 4);
          }
        }
      }
    });
    const scanY = (cityT*30)%(h+20)-10;
    const sg = cityCtx.createLinearGradient(0,scanY-5,0,scanY+5);
    sg.addColorStop(0,'transparent'); sg.addColorStop(0.5,'rgba(0,245,255,0.25)'); sg.addColorStop(1,'transparent');
    cityCtx.fillStyle = sg; cityCtx.fillRect(0,scanY-5,w,10);
    cityCtx.fillStyle = 'rgba(0,245,255,0.4)';
    cityCtx.font = '9px Orbitron, monospace';
    cityCtx.fillText('HITACHI CITY — METACHI', 10, h-10);
    requestAnimationFrame(animateCity);
  }
  animateCity();
}

// ─── SCROLL REVEAL ───
const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
}, { threshold: 0.08 });
document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

// ─── HAMBURGER MENU ───
const hamburger = document.getElementById('hamburger');
const mobileMenu = document.getElementById('mobile-menu');
hamburger.addEventListener('click', () => {
  hamburger.classList.toggle('open');
  mobileMenu.classList.toggle('open');
});

// モバイル SERVICES アコーディオン
const svcToggle = document.getElementById('mobile-services-toggle');
const mobileSub = document.getElementById('mobile-sub');
if (svcToggle && mobileSub) {
  svcToggle.addEventListener('click', () => {
    svcToggle.classList.toggle('open');
    mobileSub.classList.toggle('open');
  });
}

// メニュー項目クリックで閉じる
document.querySelectorAll('.mobile-link, .mobile-sub a').forEach(link => {
  link.addEventListener('click', () => {
    hamburger.classList.remove('open');
    mobileMenu.classList.remove('open');
    if (mobileSub) mobileSub.classList.remove('open');
    if (svcToggle) svcToggle.classList.remove('open');
  });
});
