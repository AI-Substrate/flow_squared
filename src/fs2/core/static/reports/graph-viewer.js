/**
 * graph-viewer.js - D3.js Canvas codebase explorer for fs2 reports
 * Uses D3 Canvas rendering (not WebGL) for reliable 5000+ node graphs.
 */
(function () {
  'use strict';
  var state = { mode: 'overview', selectedNode: null, selectedFile: null };
  var allNodes = [], allEdges = [], nodeMap = {};
  var visibleNodes = [], visibleEdges = [];
  var highlightId = null;
  var _focusNeighbors = null; // Set of node_ids connected to highlightId
  var transform = d3.zoomIdentity;
  var canvas, ctx, width, height, searchTimer, zoomBehavior;
  var catColors = {};
  function fmt(n) { return (n || 0).toLocaleString(); }
  function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function $(id) { return document.getElementById(id); }
  function showLoadingScreen() {
    var screen = $('loading-screen');
    if (!screen || typeof METADATA === 'undefined') return;
    var m = METADATA, e;
    e = screen.querySelector('.loading-title .name'); if (e) e.textContent = m.project_name || 'unknown';
    e = screen.querySelector('.loading-subtitle'); if (e) e.textContent = 'Generated ' + new Date(m.generated_at).toLocaleString() + ' - fs2 ' + (m.fs2_version || '');
    var stats = screen.querySelectorAll('.loading-stat');
    if (stats.length >= 3) { stats[0].querySelector('.value').textContent = fmt(m.node_count); stats[1].querySelector('.value').textContent = fmt(m.reference_edge_count); stats[2].querySelector('.value').textContent = fmt(m.containment_edge_count); }
  }
  function hideLoadingScreen() { var s = $('loading-screen'); if (!s) return; s.classList.add('fade-out'); setTimeout(function () { s.style.display = 'none'; }, 500); }
  function buildCategoryLegend() {
    var container = $('category-legend'); if (!container || typeof METADATA === 'undefined') return;
    var cats = METADATA.categories || {};
    GRAPH_DATA.nodes.forEach(function (n) { if (n.category && n.color && !catColors[n.category]) catColors[n.category] = n.color; });
    Object.entries(cats).sort(function (a, b) { return b[1] - a[1]; }).forEach(function (e) {
      var badge = document.createElement('span'); badge.className = 'cat-badge';
      badge.innerHTML = '<span class="cat-dot" style="background:' + (catColors[e[0]] || '#9ca3af') + '"></span>' + e[0] + '<span class="cat-count">' + fmt(e[1]) + '</span>';
      container.appendChild(badge);
    });
  }
  function populateStatusBar() { if (typeof METADATA === 'undefined') return; var m = METADATA, e; if ((e = $('status-nodes'))) e.textContent = fmt(m.node_count) + ' nodes'; if ((e = $('status-refs'))) e.textContent = fmt(m.reference_edge_count) + ' refs'; if ((e = $('status-version'))) e.textContent = 'fs2 ' + (m.fs2_version || ''); }
  function updateStatus(label, count) { var e; if ((e = $('status-view'))) e.textContent = label; if ((e = $('status-showing'))) e.textContent = 'Showing ' + fmt(count); }
  function updateHelpHint(text) { var e = $('help-hint'); if (e) e.textContent = text; }
  function showInfoPanel(nodeId) {
    var panel = $('info-panel'); if (!panel || !nodeId) { if (panel) panel.style.display = 'none'; return; }
    var n = nodeMap[nodeId]; if (!n) return; panel.style.display = 'block'; var e;
    if ((e = $('info-name'))) e.textContent = n.label || nodeId;
    if ((e = $('info-category'))) { e.textContent = n.category || ''; e.style.color = n.color || '#9ca3af'; }
    if ((e = $('info-path'))) e.textContent = n.file_path || '';
    if ((e = $('info-signature'))) { e.textContent = n.signature || ''; e.parentElement.style.display = n.signature ? 'block' : 'none'; }
    if ((e = $('info-degree'))) e.textContent = (n.in_degree || 0) + ' callers / ' + (n.out_degree || 0) + ' calls';
    var ce = $('info-callers'), co = $('info-calls');
    if (ce) { var h = ''; allEdges.forEach(function (e) { if (e.target === nodeId && !e._containment) { var src = nodeMap[e.source]; h += '<div class="info-link" data-node="' + esc(e.source) + '"><- ' + esc(src ? src.label : e.source) + '</div>'; } }); ce.innerHTML = h || '<span class="info-empty">none</span>'; }
    if (co) { var h2 = ''; allEdges.forEach(function (e) { if (e.source === nodeId && !e._containment) { var tgt = nodeMap[e.target]; h2 += '<div class="info-link" data-node="' + esc(e.target) + '">-> ' + esc(tgt ? tgt.label : e.target) + '</div>'; } }); co.innerHTML = h2 || '<span class="info-empty">none</span>'; }
    var se = $('info-summary'); if (se) { se.textContent = n.smart_content || ''; se.parentElement.style.display = n.smart_content ? 'block' : 'none'; }
    panel.querySelectorAll('.info-link').forEach(function (link) { link.addEventListener('click', function () { var t = this.getAttribute('data-node'); if (t && nodeMap[t]) enterFocus(t); }); });
  }
  function render() {
    ctx.save(); ctx.clearRect(0, 0, width, height);
    ctx.translate(transform.x, transform.y); ctx.scale(transform.k, transform.k);
    var invK = 1 / transform.k;
    // Edges — resolve endpoints to visible parent when endpoint not visible
    if (visibleEdges.length > 0) {
      ctx.lineWidth = 1 * invK;
      var baseAlpha = visibleEdges.length > 500 ? 0.2 : (visibleEdges.length > 50 ? 0.5 : 0.8);
      var visSet = new Set(); visibleNodes.forEach(function (n) { if (!n._dimmed) visSet.add(n.node_id); });
      visibleEdges.forEach(function (e) {
        var s = nodeMap[e.source], t = nodeMap[e.target];
        if (!s || !t) return;
        // Resolve source: if not visible, try parent; if parent not visible, skip
        var sVis = visSet.has(e.source);
        var tVis = visSet.has(e.target);
        var sx, sy, tx, ty;
        if (sVis) { sx = s.x; sy = s.y; }
        else if (s.parent_node_id && visSet.has(s.parent_node_id)) { var p = nodeMap[s.parent_node_id]; sx = p.x; sy = p.y; }
        else return; // neither source nor its parent visible — skip
        if (tVis) { tx = t.x; ty = t.y; }
        else if (t.parent_node_id && visSet.has(t.parent_node_id)) { var p2 = nodeMap[t.parent_node_id]; tx = p2.x; ty = p2.y; }
        else return; // neither target nor its parent visible — skip
        if (sx === tx && sy === ty) return;
        // Highlight edges connected to focused node, fade others
        var connected = highlightId && (e.source === highlightId || e.target === highlightId ||
          (s.parent_node_id === highlightId) || (t.parent_node_id === highlightId));
        ctx.globalAlpha = highlightId ? (connected ? 0.9 : 0.04) : baseAlpha;
        ctx.strokeStyle = connected ? '#fbbf24' : '#fbbf24';
        ctx.lineWidth = (connected ? 2 : 1) * invK;
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(tx, ty); ctx.stroke();
      }); ctx.globalAlpha = 1; ctx.lineWidth = 1 * invK;
    }
    // Node glow halos (only when zoomed enough to see them)
    if (transform.k > 0.15) {
      visibleNodes.forEach(function (n) {
        if (n._dimmed) return;
        var r = (n._r || 4);
        var glowR = r * 3;
        var grad = ctx.createRadialGradient(n.x, n.y, r * 0.5, n.x, n.y, glowR);
        var col = n.node_id === highlightId ? '#38bdf8' : (n.color || '#60a5fa');
        grad.addColorStop(0, col + '40'); // 25% alpha at center
        grad.addColorStop(1, col + '00'); // transparent at edge
        ctx.fillStyle = grad;
        ctx.beginPath(); ctx.arc(n.x, n.y, glowR, 0, 2 * Math.PI); ctx.fill();
      });
    }
    // Node cores
    visibleNodes.forEach(function (n) {
      var isFocused = n.node_id === highlightId;
      var isConnected = highlightId && _focusNeighbors && _focusNeighbors.has(n.node_id);
      var faded = highlightId && !isFocused && !isConnected;
      ctx.globalAlpha = faded ? 0.12 : 1;
      var col = isFocused ? '#38bdf8' : (n._dimmed ? '#1e293b' : (n.color || '#60a5fa'));
      ctx.fillStyle = col;
      ctx.beginPath(); ctx.arc(n.x, n.y, n._r || 4, 0, 2 * Math.PI); ctx.fill();
      if (isFocused) { ctx.strokeStyle = '#7dd3fc'; ctx.lineWidth = 2 * invK; ctx.stroke(); }
      ctx.globalAlpha = 1;
    });
    // Labels
    if (transform.k > 0.3) {
      ctx.font = Math.max(9, 12 * invK) + 'px Inter, sans-serif'; ctx.textBaseline = 'middle';
      visibleNodes.forEach(function (n) {
        if (n._dimmed || !n.label) return;
        var isFocused = n.node_id === highlightId;
        var isConnected = highlightId && _focusNeighbors && _focusNeighbors.has(n.node_id);
        var faded = highlightId && !isFocused && !isConnected;
        if (faded) return; // hide labels for faded nodes
        if ((n._r || 4) * transform.k > 2.5) {
          ctx.fillStyle = isFocused ? '#7dd3fc' : 'rgba(226,232,240,0.85)';
          ctx.fillText(n.label, n.x + (n._r || 4) + 3, n.y);
        }
      });
    }
    ctx.restore();
  }
  function findNodeAt(sx, sy) {
    var pt = transform.invert([sx, sy]), px = pt[0], py = pt[1], best = null, bestDist = Infinity;
    visibleNodes.forEach(function (n) { if (n._dimmed) return; var dx = px - n.x, dy = py - n.y, d2 = dx * dx + dy * dy, r = (n._r || 4) + 4; if (d2 < r * r && d2 < bestDist) { bestDist = d2; best = n; } });
    return best;
  }
  // Build reference edges list (non-containment) — shared across modes
  function getRefEdges() {
    return allEdges.filter(function (e) { return !e._containment; });
  }
  // Build neighbor set for a node (file-level: includes children's connections)
  function buildNeighbors(nodeId) {
    var neighbors = new Set();
    var n = nodeMap[nodeId];
    if (!n) return neighbors;
    // Direct connections
    allEdges.forEach(function (e) {
      if (e._containment) return;
      if (e.source === nodeId) neighbors.add(e.target);
      if (e.target === nodeId) neighbors.add(e.source);
    });
    // If it's a file, also include connections of its children
    if (n.category === 'file') {
      allNodes.forEach(function (child) {
        if (child.parent_node_id !== nodeId) return;
        allEdges.forEach(function (e) {
          if (e._containment) return;
          if (e.source === child.node_id) { neighbors.add(e.target); var tp = nodeMap[e.target]; if (tp && tp.parent_node_id) neighbors.add(tp.parent_node_id); }
          if (e.target === child.node_id) { neighbors.add(e.source); var sp = nodeMap[e.source]; if (sp && sp.parent_node_id) neighbors.add(sp.parent_node_id); }
        });
      });
    }
    return neighbors;
  }
  function enterOverview() {
    state.mode = 'overview'; state.selectedNode = null; state.selectedFile = null;
    highlightId = null; _focusNeighbors = null;
    visibleNodes = allNodes.filter(function (n) { return n.category === 'file'; });
    visibleNodes.forEach(function (n) { n._dimmed = false; });
    visibleEdges = getRefEdges();
    updateStatus('Overview - click a file to explore', visibleNodes.length); showInfoPanel(null);
    updateHelpHint('Click a file node - Scroll to zoom - Drag to pan - / to search - Esc to reset'); render();
  }
  function enterContents(fileNodeId) {
    state.mode = 'contents'; state.selectedFile = fileNodeId; state.selectedNode = null;
    highlightId = fileNodeId; _focusNeighbors = buildNeighbors(fileNodeId);
    var children = [nodeMap[fileNodeId]];
    allNodes.forEach(function (n) { if (n.parent_node_id === fileNodeId) children.push(n); });
    var bg = allNodes.filter(function (n) { return n.category === 'file' && n.node_id !== fileNodeId; });
    bg.forEach(function (n) { n._dimmed = true; }); children.forEach(function (n) { n._dimmed = false; });
    visibleNodes = children.concat(bg);
    var childSet = new Set(); children.forEach(function (c) { childSet.add(c.node_id); });
    visibleEdges = allEdges.filter(function (e) { return !e._containment && (childSet.has(e.source) || childSet.has(e.target)); });
    updateStatus('File: ' + ((nodeMap[fileNodeId] || {}).label || fileNodeId), children.length);
    showInfoPanel(fileNodeId); updateHelpHint('Click a symbol for connections - Click background to go back');
    var fn = nodeMap[fileNodeId]; if (fn) zoomTo(fn.x, fn.y, 2.5); render();
  }
  function enterFocus(nodeId) {
    state.mode = 'focus'; state.selectedNode = nodeId;
    highlightId = nodeId; _focusNeighbors = buildNeighbors(nodeId);
    var neighborSet = new Set(); neighborSet.add(nodeId); visibleEdges = [];
    allEdges.forEach(function (e) { if (e._containment) return; if (e.source === nodeId) { neighborSet.add(e.target); visibleEdges.push(e); } if (e.target === nodeId) { neighborSet.add(e.source); visibleEdges.push(e); } });
    visibleNodes = allNodes.filter(function (n) { return neighborSet.has(n.node_id); });
    visibleNodes.forEach(function (n) { n._dimmed = false; });
    var n = nodeMap[nodeId] || {};
    updateStatus('Focus: ' + (n.label || nodeId) + ' (in:' + (n.in_degree || 0) + ' out:' + (n.out_degree || 0) + ')', visibleNodes.length);
    showInfoPanel(nodeId); updateHelpHint('Click a neighbor to walk - Click background to go back - Esc to reset');
    if (n.x !== undefined) zoomTo(n.x, n.y, 3); render();
  }
  function doSearch(query) {
    if (!query) { enterOverview(); return; } state.mode = 'search'; highlightId = null;
    var q = query.toLowerCase();
    visibleNodes = allNodes.filter(function (n) { return (n.label || '').toLowerCase().indexOf(q) >= 0 || (n.file_path || '').toLowerCase().indexOf(q) >= 0 || n.node_id.toLowerCase().indexOf(q) >= 0; });
    visibleNodes.forEach(function (n) { n._dimmed = false; }); visibleEdges = [];
    updateStatus('Search: "' + query + '"', visibleNodes.length); showInfoPanel(null); render();
  }
  function showEntryPoints() {
    state.mode = 'search'; highlightId = null;
    visibleNodes = allNodes.filter(function (n) { return n.is_entry_point; });
    visibleNodes.forEach(function (n) { n._dimmed = false; }); visibleEdges = [];
    updateStatus('Entry Points (no callers, has calls)', visibleNodes.length); showInfoPanel(null);
    updateHelpHint('Showing entry points - Click one to explore - Esc to reset'); render();
  }
  function zoomTo(x, y, k) { var tx = width / 2 - x * k, ty = height / 2 - y * k; transform = d3.zoomIdentity.translate(tx, ty).scale(k); canvas.call(zoomBehavior.transform, transform); }
  function zoomFit() { fitGraph(); render(); }
  function zoomIn() { transform = transform.scale(1.5); canvas.call(zoomBehavior.transform, transform); render(); }
  function zoomOut() { transform = transform.scale(1 / 1.5); canvas.call(zoomBehavior.transform, transform); render(); }
  function fitGraph() {
    var xs = allNodes.map(function (n) { return n.x; }), ys = allNodes.map(function (n) { return n.y; });
    var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs), minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
    var gW = maxX - minX || 1, gH = maxY - minY || 1;
    var scale = Math.min(width / gW, height / gH) * 0.85;
    transform = d3.zoomIdentity.translate(width / 2 - (minX + gW / 2) * scale, height / 2 - (minY + gH / 2) * scale).scale(scale);
    canvas.call(zoomBehavior.transform, transform);
  }
  function onClickNode(n) {
    // First click: highlight in place (fade others, show connections)
    // Second click on same node: drill into contents/focus
    if (highlightId === n.node_id) {
      // Already highlighted — drill in
      if (n.category === 'file') enterContents(n.node_id);
      else enterFocus(n.node_id);
      return;
    }
    // Highlight this node — keep current view but fade non-connected
    highlightId = n.node_id;
    _focusNeighbors = buildNeighbors(n.node_id);
    showInfoPanel(n.node_id);
    var name = n.label || n.node_id;
    updateStatus(state.mode.charAt(0).toUpperCase() + state.mode.slice(1) + ' - selected: ' + name, visibleNodes.length);
    updateHelpHint('Click again to drill in - Click background to deselect - Esc to reset');
    render();
  }
  function onClickStage() {
    if (highlightId) {
      // Deselect — clear highlight, keep current mode
      highlightId = null; _focusNeighbors = null;
      showInfoPanel(null); render();
      return;
    }
    if (state.mode === 'focus') state.selectedFile ? enterContents(state.selectedFile) : enterOverview();
    else if (state.mode === 'contents') enterOverview();
  }
  function initGraph() {
    if (typeof GRAPH_DATA === 'undefined' || typeof d3 === 'undefined') throw new Error('Missing GRAPH_DATA or d3');
    GRAPH_DATA.nodes.forEach(function (n) { n.label = n.label || n.name || ''; n._r = n.size || 4; nodeMap[n.node_id] = n; allNodes.push(n); });
    GRAPH_DATA.edges.forEach(function (e) { e._containment = e.hidden; allEdges.push(e); });
    var container = $('sigma-container'); width = container.offsetWidth; height = container.offsetHeight;
    canvas = d3.select(container).append('canvas').attr('width', width).attr('height', height).style('width', '100%').style('height', '100%');
    ctx = canvas.node().getContext('2d');
    zoomBehavior = d3.zoom().scaleExtent([0.05, 20]).on('zoom', function (event) { transform = event.transform; render(); });
    canvas.call(zoomBehavior);
    canvas.on('click', function (event) { var rect = canvas.node().getBoundingClientRect(); var n = findNodeAt(event.clientX - rect.left, event.clientY - rect.top); n ? onClickNode(n) : onClickStage(); });
    canvas.on('mousemove', function (event) { var rect = canvas.node().getBoundingClientRect(); var n = findNodeAt(event.clientX - rect.left, event.clientY - rect.top); canvas.node().style.cursor = n && !n._dimmed ? 'pointer' : 'default'; });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { var s = $('search-input'); if (s) s.value = ''; enterOverview(); }
      if (e.key === '/' && e.target === document.body) { e.preventDefault(); $('search-input').focus(); }
      if (e.key === 'f' && !e.ctrlKey && !e.metaKey && e.target === document.body) zoomFit();
    });
    var e;
    if ((e = $('btn-overview'))) e.addEventListener('click', function () { $('search-input').value = ''; enterOverview(); });
    if ((e = $('btn-zoom-fit'))) e.addEventListener('click', zoomFit);
    if ((e = $('btn-zoom-in'))) e.addEventListener('click', zoomIn);
    if ((e = $('btn-zoom-out'))) e.addEventListener('click', zoomOut);
    if ((e = $('btn-entry-points'))) e.addEventListener('click', function () { $('search-input').value = ''; showEntryPoints(); });
    var si = $('search-input');
    if (si) si.addEventListener('input', function () { clearTimeout(searchTimer); var q = this.value.trim(); searchTimer = setTimeout(function () { doSearch(q); }, 200); });
    if ((e = $('info-close'))) e.addEventListener('click', function () { $('info-panel').style.display = 'none'; });
    window.__fs2 = { allNodes: allNodes, allEdges: allEdges, nodeMap: nodeMap, enterOverview: enterOverview, enterContents: enterContents, enterFocus: enterFocus, showEntryPoints: showEntryPoints, doSearch: doSearch, state: state };
    fitGraph(); enterOverview();
  }
  function boot() {
    showLoadingScreen(); buildCategoryLegend(); populateStatusBar();
    setTimeout(function () { try { initGraph(); } catch (e) { var x = $('error-display'); if (x) { x.textContent = 'Init: ' + e.message; x.style.display = 'block'; } console.error(e); } hideLoadingScreen(); }, 150);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
