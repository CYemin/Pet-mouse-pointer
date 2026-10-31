/* Original cursor pixels and ANI timelines; all interactions stay in this page. */
(() => {
  'use strict';
  const themes = window.PET_THEMES;
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const byRole = (t, role) => t.states.find(s => s.role === role) || t.states[0];
  const imageCache = new Map();
  let theme = themes[0], size = 48, atlas = null, galleryAtlas = null;
  let mode = 'auto', lockedRole = 'Arrow', hoverRole = 'Arrow', lastRole = '', scene = 'click';
  let request = 0, paused = matchMedia('(prefers-reduced-motion: reduce)').matches, speed = 1;
  let progress = 0, anchorTime = performance.now(), paintVersion = 0, busy = false;
  let pointer = { x: 0, y: 0, visible: false }, cursorKey = '', inspectorKey = '';
  let stateCanvases = [], colorCanvases = [], colorVersion = 0, colorFamily = '', toastTimer, gesture = null;
  const familySelection = new Map();
  const cursor = $('#pet-cursor'), inspector = $('#inspector-art');
  const getElapsed = now => progress + (paused ? 0 : (now - anchorTime) * speed);
  const getRole = () => theme.previewOnly ? 'Arrow' : mode === 'lock' ? lockedRole : (busy && pointer.visible && pointer.area === 'experience' ? 'Wait' : hoverRole);
  const getState = () => byRole(theme, getRole());
  const clamp = (v, min, max) => Math.min(max, Math.max(min, v));

  function loadImage(url) {
    if (imageCache.has(url)) { const p=imageCache.get(url);imageCache.delete(url);imageCache.set(url,p);return p; }
    const p = new Promise((resolve, reject) => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => { imageCache.delete(url); reject(new Error('图片未能加载')); };
      im.src = url;
    });
    imageCache.set(url, p);
    const largeKeys=[...imageCache.keys()].filter(k=>/\/(32|64|96|128)\.png$/.test(k));
    while(largeKeys.length>8)imageCache.delete(largeKeys.shift());
    return p;
  }
  function frameAt(s, elapsed) {
    if (!s.animated) return s.sequence[0];
    let tick = elapsed * 60 / 1000 % s.ticks.reduce((a, b) => a + b, 0);
    for (let i = 0; i < s.sequence.length; i++) {
      if (tick < s.ticks[i]) return s.sequence[i];
      tick -= s.ticks[i];
    }
    return s.sequence[0];
  }
  function toast(message) {
    clearTimeout(toastTimer); $('#toast').textContent = message;
    $('#toast').classList.add('visible');
    toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 2100);
  }
  function renderThemes(filter = '全部') {
    const rail = $('#themes'); rail.replaceChildren();
    const seen=new Set();
    for (const t of themes) {
      if (filter !== '全部' && t.group !== filter) continue;
      const family=t.family||t.id;if(seen.has(family))continue;seen.add(family);
      const remembered=familySelection.get(family);
      const shown=themes.find(x=>x.id===remembered)||(theme.family===family?theme:t);
      const button = document.createElement('button');
      button.className = 'theme-card' + (t.pixel ? ' pixel' : '');
      button.dataset.theme = shown.id;button.dataset.family=family;button.setAttribute('aria-pressed', String(family===(theme.family||theme.id)));
      button.setAttribute('aria-label', `${t.familyName||t.name}，${shown.description}`);
      const image = new Image(); image.src = `assets/${shown.id}/avatar.png`; image.alt = ''; image.loading = 'lazy';
      const name = document.createElement('strong'); name.textContent = t.familyName||t.name;
      button.append(image, name);
      if (t.family) { const tag = document.createElement('span'); tag.className = 'new-tag'; tag.textContent = `${themes.filter(x=>x.family===t.family).length} 配色`; button.append(tag); }
      const check = document.createElement('span'); check.className = 'selected-check'; check.textContent = '✓'; button.append(check);
      button.onclick = () => selectTheme(familySelection.get(family)||shown.id);
      rail.append(button);
    }
  }
  for (const label of ['全部', '泰迪', '比熊', '柯基', '二哈', '瑞牧', '西高地', '金毛', '喜乐蒂']) {
    const b = document.createElement('button'); b.textContent = label; b.setAttribute('aria-pressed', String(label === '全部'));
    b.onclick = () => {
      $$('#filters button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));renderThemes(label);
      if(label!=='全部'&&theme.group!==label){const first=themes.find(t=>t.group===label);if(first)selectTheme(familySelection.get(first.family)||first.id);}
    };
    $('#filters').append(b);
  }
  $('#theme-prev').onclick = () => $('#themes').scrollBy({ left: -420, behavior: 'smooth' });
  $('#theme-next').onclick = () => $('#themes').scrollBy({ left: 420, behavior: 'smooth' });

  async function selectTheme(id, nextSize = size) {
    const t = themes.find(x => x.id === id); if (!t) return;
    const version = ++request;
    $('#loading-status').textContent = `正在迎接${t.name}…`;
    $('#playground').setAttribute('aria-busy', 'true');
    try {
      const [nextAtlas, nextGallery] = await Promise.all([loadImage(t.atlases[nextSize]), loadImage(t.atlases[48])]);
      if (version !== request) return;
      const changed = theme.id !== t.id || !galleryAtlas;
      theme = t; size = nextSize; atlas = nextAtlas; galleryAtlas = nextGallery;
      if(!t.states.some(s=>s.role===lockedRole))lockedRole='Arrow';
      if(t.previewOnly){hoverRole='Arrow';if(scene!=='click')switchScene('click');}
      $$('[data-scene]').forEach(b=>{b.disabled=!!t.previewOnly&&b.dataset.scene!=='click';b.title=b.disabled?'本配色暂含普通指针，请选照片参考款体验其他动作':'';});
      $('#cursor-size').value = String(size);
      $('#active-pet-name').textContent = t.name;
      $('#active-pet-desc').textContent = t.description;
      $('#pet-style').textContent = t.pixel ? '像素动画' : (t.states.some(s => s.animated) ? '手绘动画' : '圆润插画');
      for(const link of [$('#download-theme'),$('#nav-download')]){
        if(t.download){link.href=t.download;link.removeAttribute('aria-disabled');link.tabIndex=0;}
        else{link.removeAttribute('href');link.setAttribute('aria-disabled','true');link.tabIndex=-1;}
      }
      $('#download-theme span').textContent=t.previewOnly?'完整主题待补齐':'带它回桌面';
      $('.download-note').textContent=t.previewOnly?'当前为普通指针动画预览':'Windows 主题 · 也附恢复入口';
      $('#all-states .section-caption').textContent=t.previewOnly?'当前配色仅普通指针动画':'悬停体验 · 点击锁定';
      $('#nav-download').textContent=t.previewOnly?'完整主题待补齐':'下载主题 ↓';
      const limitedFamily=!!t.family&&themes.some(x=>x.family===t.family&&x.previewOnly);
      $('#theme-availability').hidden=!limitedFamily;
      $('#theme-availability').textContent=limitedFamily?'本组额外配色暂为普通指针动画预览；完整动作可选照片参考款体验。':'';
      familySelection.set(t.family||t.id,t.id);
      $$('[data-theme]').forEach(b => {
        const active=b.dataset.family===(t.family||t.id);b.setAttribute('aria-pressed',String(active));
        if(active){b.dataset.theme=t.id;b.querySelector('img').src=`assets/${t.id}/avatar.png`;b.setAttribute('aria-label',`${t.familyName||t.name}，${t.description}`);}
      });
      if (changed) renderStates();
      renderColors(t);
      $('#loading-status').textContent = '准备好啦，移进左侧试试看。';
      document.body.classList.add('cursor-ready');
      ++paintVersion; lastRole = ''; inspectorKey = ''; cursorKey = '';
      cursor.style.imageRendering = inspector.style.imageRendering = t.pixel ? 'pixelated' : 'auto';
    } catch (e) {
      if (version === request) { $('#loading-status').textContent = '这位小伙伴还没加载好，请再选一次。'; toast('图片加载未完成，请重试'); }
    } finally { if (version === request) $('#playground').removeAttribute('aria-busy'); }
  }
  async function renderColors(t) {
    const lab=$('#color-lab'),grid=$('#color-grid'),version=++colorVersion; colorCanvases=[];
    if(!t.family){lab.hidden=true;grid.replaceChildren();colorFamily='';return;}
    lab.hidden=false;colorFamily=t.family;grid.replaceChildren();
    $('#color-family-title').textContent=`${t.familyName}，换一种颜色看看`;
    const choices=themes.filter(x=>x.family===t.family);
    $('#color-comparison-note').textContent=choices.some(x=>x.previewOnly)?'普通指针对比 · 原色可体验全部动作':choices.length===1?'原版动作预览':`${choices.length} 款同动作对比 · 点击选用`;
    await Promise.all(choices.map(async choice=>{
      const b=document.createElement('button');b.className='color-card';b.dataset.colorTheme=choice.id;
      b.setAttribute('aria-pressed',String(choice.id===t.id));b.setAttribute('aria-label',`选择${choice.familyName} ${choice.colorName}配色`);
      const artBox=document.createElement('span');artBox.className='color-art';
      const fallback=new Image();fallback.src=`assets/${choice.id}/avatar.png`;fallback.alt='';artBox.append(fallback);
      const art=document.createElement('canvas');art.width=96;art.height=96;art.setAttribute('aria-hidden','true');artBox.append(art);
      const info=document.createElement('span');info.className='color-info';
      const title=document.createElement('strong');title.textContent=choice.colorName;
      const tag=document.createElement('small');tag.textContent=choice.previewOnly?'普通指针预览':choice.colorType==='reference'?'照片参考':choice.colorType==='design'?'创意配色':'毛色款式';
      const dots=document.createElement('span');dots.className='color-dots';dots.setAttribute('aria-hidden','true');
      for(const color of choice.swatch||[]){const dot=document.createElement('i');dot.style.backgroundColor=color;dots.append(dot);}
      info.append(title,tag,dots);b.append(artBox,info);b.onclick=()=>selectTheme(choice.id);grid.append(b);
      try{const source=await loadImage(choice.atlases[48]);if(version!==colorVersion)return;fallback.hidden=true;colorCanvases.push({canvas:art,theme:choice,atlas:source,key:'',tag,originalTag:tag.textContent});}
      catch(e){if(version===colorVersion)$('#color-comparison-note').textContent='可点击配色重试加载';}
    }));
  }
  function renderStates() {
    const grid = $('#state-grid'); grid.replaceChildren(); stateCanvases = [];
    for (const [i, s] of theme.states.entries()) {
      const b = document.createElement('button'); b.className = 'state-card'; b.dataset.role = s.role;
      b.setAttribute('aria-label', `锁定${s.label}`); b.setAttribute('aria-pressed', String(mode === 'lock' && lockedRole === s.role));
      const number = document.createElement('span'); number.className = 'state-number'; number.textContent = String(i + 1).padStart(2, '0');
      const art = document.createElement('canvas'); art.width = 96; art.height = 96; art.setAttribute('aria-hidden', 'true'); art.style.imageRendering = theme.pixel ? 'pixelated' : 'auto';
      const label = document.createElement('strong'); label.textContent = s.label;
      b.append(number, art, label); b.onclick = () => setMode('lock', s.role);
      grid.append(b); stateCanvases.push({ canvas: art, state: s, key: '' });
    }
  }
  function setMode(next, role = getRole()) {
    mode = next; if (next === 'lock') lockedRole = role;
    $('#mode-auto').setAttribute('aria-pressed', String(next === 'auto'));
    $('#mode-lock').setAttribute('aria-pressed', String(next === 'lock'));
    $('#mode-description').textContent = next === 'auto' ? '自动跟随场景切换动作' : `已锁定 · ${byRole(theme, lockedRole).label}`;
    $$('.state-card').forEach(b => b.setAttribute('aria-pressed', String(next === 'lock' && b.dataset.role === lockedRole)));
    lastRole = ''; ++paintVersion;
  }
  $('#mode-auto').onclick = $('#return-auto').onclick = () => setMode('auto');
  $('#mode-lock').onclick = () => setMode('lock');
  $('#cursor-size').onchange = e => selectTheme(theme.id, +e.target.value);
  $('#show-hotspot').onchange = () => ++paintVersion;
  $$('[data-background]').filter(b => b.tagName === 'BUTTON').forEach(b => {
    b.onclick = () => {
      $('#experience').dataset.background = $('#specimen').dataset.background = b.dataset.background;
      $('#color-grid').dataset.background=b.dataset.background;
      $$('.swatch').forEach(x => { x.classList.toggle('active', x === b); x.setAttribute('aria-pressed', String(x === b)); });
    };
  });
  function setPaused(value) {
    const now = performance.now(); progress = getElapsed(now); anchorTime = now; paused = value;
    $('#pause-motion').setAttribute('aria-pressed', String(paused)); $('#pause-motion').textContent = paused ? '▷ 播放动画' : 'Ⅱ 暂停动画';
    ++paintVersion;
  }
  $('#pause-motion').onclick = () => setPaused(!paused);
  $('#slow-motion').onclick = () => {
    const now = performance.now(); progress = getElapsed(now); anchorTime = now; speed = speed === 1 ? .25 : 1;
    $('#slow-motion').setAttribute('aria-pressed', String(speed !== 1)); $('#slow-motion').textContent = speed === 1 ? '¼ 慢放' : '1× 正常';
  };
  setPaused(paused);
  function switchScene(id) {
    if(theme.previewOnly&&id!=='click')return;
    scene = id;
    $$('.scene').forEach(s => { const active = s.id === 'scene-' + id; s.hidden = !active; s.classList.toggle('active', active); });
    $$('[data-scene]').forEach(t => t.setAttribute('aria-selected', String(t.dataset.scene === id)));
    hoverRole = { click: 'Arrow', write: 'IBeam', drag: 'SizeAll', resize: 'SizeNWSE', friends: 'Hand' }[id];
    lastRole = ''; if (id === 'write') requestAnimationFrame(setupDrawing); hideCursor();
  }
  $$('[data-scene]').forEach(b => b.onclick = () => switchScene(b.dataset.scene));
  $('#scene-tabs').onkeydown = e => { const tabs=$$('[data-scene]').filter(t=>!t.disabled),i=tabs.indexOf(document.activeElement); if(i<0)return; const next=e.key==='ArrowRight'?(i+1)%tabs.length:e.key==='ArrowLeft'?(i+tabs.length-1)%tabs.length:e.key==='Home'?0:e.key==='End'?tabs.length-1:-1; if(next>=0){e.preventDefault();switchScene(tabs[next].dataset.scene);tabs[next].focus();} };

  function drawSprite(canvas, s, frame, sourceImage, sourceSize, displaySize, marks = false) {
    const dpr = Math.min(devicePixelRatio || 1, 3), pixels = Math.round(displaySize * dpr);
    if (canvas.width !== pixels || canvas.height !== pixels) { canvas.width = pixels; canvas.height = pixels; }
    const c = canvas.getContext('2d'); c.clearRect(0, 0, pixels, pixels); c.imageSmoothingEnabled = !theme.pixel;
    c.drawImage(sourceImage, frame * sourceSize, s.row * sourceSize, sourceSize, sourceSize, 0, 0, pixels, pixels);
    if (marks) {
      const [x, y] = s.hotspots[sourceSize], scale = pixels / sourceSize;
      c.save(); c.strokeStyle = '#1298a0'; c.lineWidth = Math.max(1, dpr); c.beginPath();
      c.moveTo(x * scale - 4 * dpr, y * scale); c.lineTo(x * scale + 4 * dpr, y * scale);
      c.moveTo(x * scale, y * scale - 4 * dpr); c.lineTo(x * scale, y * scale + 4 * dpr); c.stroke(); c.restore();
    }
  }
  function placeCursor() {
    if (!atlas || !pointer.visible) return;
    const s = getState(), [hx, hy] = s.hotspots[size];
    cursor.style.transform = `translate3d(${pointer.x - hx}px,${pointer.y - hy}px,0)`;
    cursor.style.display = 'block'; document.body.classList.add('pointer-active');
  }
  function hideCursor() { pointer.visible = false; cursor.style.display = 'none'; document.body.classList.remove('pointer-active'); }
  document.addEventListener('pointermove', e => {
    const area = e.target.closest?.('[data-play-area]');
    if (!area || e.pointerType === 'touch') { hideCursor(); return; }
    pointer = { x: e.clientX, y: e.clientY, visible: true, area: area.id };
    const roleTarget = e.target.closest('[data-role]');
    hoverRole = roleTarget?.dataset.role || 'Arrow';
    placeCursor();
  }, { passive: true });
  document.addEventListener('pointerover', e => {
    if (e.target.closest?.('[data-play-area]')) hoverRole = e.target.closest('[data-role]')?.dataset.role || 'Arrow';
  });
  document.addEventListener('pointerout', e => { if (!e.relatedTarget) hideCursor(); });
  window.addEventListener('blur', hideCursor);
  window.addEventListener('scroll', hideCursor, { passive: true });
  document.addEventListener('visibilitychange', () => { if (document.hidden) hideCursor(); });
  function animate(now) {
    if (atlas && !document.hidden) {
      const elapsed = getElapsed(now), s = getState(), f = frameAt(s, elapsed), marked = $('#show-hotspot').checked;
      if (lastRole !== s.role) {
        $('#live-state').textContent = $('#active-state-name').textContent = s.label;
        $('#animation-status').textContent = s.animated ? '动画' : '静态';
        $('#active-state-idea').textContent = s.idea; lastRole = s.role;
        if (mode === 'lock') $('#mode-description').textContent = `已锁定 · ${s.label}`;
      }
      const key = `${s.id}:${f}:${paintVersion}`;
      if (inspectorKey !== key) { drawSprite(inspector, s, f, atlas, size, 126, marked); inspectorKey = key; }
      if (pointer.visible) {
        if (cursorKey !== key) { cursor.style.width = cursor.style.height = size + 'px'; drawSprite(cursor, s, f, atlas, size, size, marked); cursorKey = key; }
        placeCursor();
      }
      for (const item of stateCanvases) {
        const k = frameAt(item.state, elapsed), version = `${k}:${paintVersion}`;
        if (item.key !== version) { drawSprite(item.canvas, item.state, k, galleryAtlas, 48, 48); item.key = version; }
      }
      for(const item of colorCanvases){
        const available=item.theme.states.some(s=>s.role===getRole());
        item.canvas.hidden=!available;item.tag.textContent=available?item.originalTag:'此动作待补齐';
        if(!available)continue;
        const state=byRole(item.theme,getRole()),frame=frameAt(state,elapsed),version=`${state.id}:${frame}:${paintVersion}`;
        if(item.key!==version){drawSprite(item.canvas,state,frame,item.atlas,48,96,marked);item.key=version;}
      }
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);

  $$('.treat').forEach(b => b.onclick = () => {
    b.classList.add('eaten'); b.querySelector('span').textContent = '✓'; b.setAttribute('aria-pressed', 'true');
    const n = $$('.treat.eaten').length; $('#treat-score').textContent = n === 3 ? '3 / 3 · 今天的小快乐，集齐啦！' : `已点亮 ${n} / 3`;
    if (n === 3) toast('小饼干都点亮啦 ✦');
  });
  $('#reset-treats').onclick = () => { $$('.treat').forEach(b => { b.classList.remove('eaten'); b.querySelector('span').textContent = '✿'; b.setAttribute('aria-pressed', 'false'); }); $('#treat-score').textContent = '已点亮 0 / 3'; $('.precision-target').classList.remove('hit'); };
  $('.precision-target').onclick = e => { e.currentTarget.classList.add('hit'); toast('正中靶心，眼神真好！'); };

  const drawing = $('#drawing-pad'); let drawingCtx, drawingOn = false;
  function setupDrawing() {
    const r = drawing.getBoundingClientRect(); if (!r.width || !r.height) return;
    const dpr = Math.min(devicePixelRatio || 1, 3), w = Math.round(r.width * dpr), h = Math.round(r.height * dpr);
    if (drawing.width === w && drawing.height === h && drawingCtx) return;
    const backup = document.createElement('canvas'); backup.width = drawing.width; backup.height = drawing.height; backup.getContext('2d').drawImage(drawing, 0, 0);
    drawing.width = w; drawing.height = h; drawingCtx = drawing.getContext('2d'); drawingCtx.drawImage(backup, 0, 0, w, h); drawingCtx.setTransform(dpr, 0, 0, dpr, 0, 0); drawingCtx.strokeStyle = '#a36f45'; drawingCtx.lineWidth = 2; drawingCtx.lineCap = drawingCtx.lineJoin = 'round';
  }
  drawing.onpointerdown = e => { e.preventDefault(); setupDrawing(); drawingOn = true; drawing.setPointerCapture(e.pointerId); const r = drawing.getBoundingClientRect(); drawingCtx.beginPath(); drawingCtx.moveTo(e.clientX - r.left, e.clientY - r.top); };
  drawing.onpointermove = e => { if (!drawingOn) return; const r = drawing.getBoundingClientRect(); drawingCtx.lineTo(e.clientX - r.left, e.clientY - r.top); drawingCtx.stroke(); };
  drawing.onpointerup = drawing.onpointercancel = () => { drawingOn = false; };
  $('#clear-drawing').onclick = () => { setupDrawing(); drawingCtx.save(); drawingCtx.resetTransform(); drawingCtx.clearRect(0, 0, drawing.width, drawing.height); drawingCtx.restore(); };
  window.addEventListener('resize', () => { if (scene === 'write') setupDrawing(); });

  const gift = $('#drag-gift'), home = $('#drop-home'); let drag = null, giftX = 0, giftY = 0;
  function giftPosition(x, y) {
    const field = $('.drag-field').getBoundingClientRect(), base = gift.getBoundingClientRect();
    giftX = clamp(x, -Math.max(0,base.left - giftX - field.left), field.width - 70); giftY = clamp(y, -65, 90);
    gift.style.transform = `translate(${giftX}px,${giftY}px)`;
    const a = gift.getBoundingClientRect(), b = home.getBoundingClientRect();
    const inside = a.left + a.width / 2 > b.left && a.left + a.width / 2 < b.right && a.top + a.height / 2 > b.top && a.top + a.height / 2 < b.bottom;
    home.classList.toggle('over', inside); return inside;
  }
  function finishGift() {
    const inside = giftPosition(giftX, giftY); drag = null; gift.setAttribute('aria-pressed', 'false'); home.classList.remove('over');
    $('#drag-result').textContent = inside ? '送到小窝啦，心意已收到。' : '再试一次，把礼物放到小窝中央。';
    home.classList.toggle('received', inside); if (inside) toast('小礼物到家啦 ✦');
    giftX = giftY = 0; gift.style.transform = ''; gesture = null;
  }
  gift.onpointerdown = e => { e.preventDefault(); drag = { x: e.clientX - giftX, y: e.clientY - giftY }; gesture = 'drag'; gift.setPointerCapture(e.pointerId); gift.setAttribute('aria-pressed', 'true'); };
  gift.onpointermove = e => { if (drag) giftPosition(e.clientX - drag.x, e.clientY - drag.y); };
  gift.onpointerup = () => { if (drag) finishGift(); };
  gift.onpointercancel = () => { drag = null; gesture = null; giftX = giftY = 0; gift.style.transform = ''; gift.setAttribute('aria-pressed','false'); home.classList.remove('over'); };
  gift.onkeydown = e => {
    if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)) { e.preventDefault(); giftPosition(giftX + (e.key==='ArrowRight'?16:e.key==='ArrowLeft'?-16:0),giftY+(e.key==='ArrowDown'?16:e.key==='ArrowUp'?-16:0)); gift.setAttribute('aria-pressed','true'); }
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); finishGift(); }
  };
  const box = $('#resize-box'); let resizing = null;
  function resizeBox(w,h) { const max = Math.max(120, $('.resize-field').clientWidth - 38); box.style.width = clamp(w,115,max)+'px'; box.style.height = clamp(h,75,155)+'px'; $('#resize-value').textContent = `${Math.round(box.getBoundingClientRect().width)} × ${Math.round(box.getBoundingClientRect().height)}`; }
  $$('.resize-handle').forEach(h => {
    h.onpointerdown = e => { e.preventDefault(); const r=box.getBoundingClientRect(); resizing={x:e.clientX,y:e.clientY,w:r.width,h:r.height,kind:h.dataset.resize,left:h.classList.contains('nw')||h.classList.contains('sw'),top:h.classList.contains('nw')||h.classList.contains('ne')}; h.setPointerCapture(e.pointerId); gesture='resize'; };
    h.onpointermove = e => { if (!resizing) return; const r=resizing,dx=(e.clientX-r.x)*(r.left?-1:1),dy=(e.clientY-r.y)*(r.top?-1:1);resizeBox(r.kind==='ns'?r.w:r.w+dx,r.kind==='we'?r.h:r.h+dy); };
    h.onpointerup = h.onpointercancel = () => { resizing=null;gesture=null; };
    h.onkeydown = e => { if (!e.key.startsWith('Arrow')) return;e.preventDefault();const r=box.getBoundingClientRect();resizeBox(r.width+(e.key==='ArrowRight'?10:e.key==='ArrowLeft'?-10:0),r.height+(e.key==='ArrowDown'?10:e.key==='ArrowUp'?-10:0)); };
  });
  $('#reset-resize').onclick = () => resizeBox(240,130);

  $('#friend-link').onclick = () => { $('#friend-message').textContent=`你好呀，我是${theme.name}。今天也一起散散步吧。`; };
  $('#friend-pin').onclick = () => { $('#friend-message').textContent='小窝已经标记好，记得常回来看看。'; };
  $('#friend-person').onclick = () => { $('#friend-message').textContent='是熟悉的朋友！小伙伴开心地认出了你。'; };
  $('#friend-alternate').onclick = () => { $('#friend-message').textContent='抬头看看，上面也有一点小惊喜。'; };
  $('#friend-help').onclick = () => { const open=$('#help-copy').hidden;$('#help-copy').hidden=!open;$('#friend-help').setAttribute('aria-expanded',String(open)); };
  $('#friend-no').onclick = () => { $('#friend-message').textContent='这个按钮正在休息，换一个试试吧。'; };
  $('#friend-loading').onclick = () => {
    if (busy) return; busy=true;$('#friend-message').textContent='小伙伴正在忙，等它一小会儿…';$('#friend-loading').setAttribute('aria-busy','true');
    setTimeout(()=>{busy=false;$('#friend-message').textContent='忙完啦，准备好继续陪你。';$('#friend-loading').removeAttribute('aria-busy');toast('小伙伴回来啦！');},1800);
  };
  renderThemes(); selectTheme(themes[0].id);
  $('.intro').classList.add('page-enter');
})();
