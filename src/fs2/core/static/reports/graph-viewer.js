/**
 * graph-viewer.js - D3.js Canvas codebase explorer for fs2 reports
 * V3: Semantic clustering layout — nodes positioned by embedding similarity.
 */
(function () {
  'use strict';
  var state = { mode: 'overview', selectedNode: null, selectedFile: null };
  var allNodes = [], allEdges = [], nodeMap = {};
  var clusters = []; // cluster hull data from Python
  var visibleNodes = [], visibleEdges = [];
  var highlightId = null;
  var _focusNeighbors = null;
  var hoverClusterId = -1;  // cluster id under mouse cursor
  var activeClusterId = -1; // cluster id selected via panel click
  var transform = d3.zoomIdentity;
  var canvas, ctx, width, height, searchTimer, zoomBehavior;
  var catColors = {};
  var stars = [];
  var starTimer = null;
  function initStars(count) {
    stars = [];
    for (var i = 0; i < count; i++) {
      stars.push({
        x: Math.random(), y: Math.random(),
        r: 0.3 + Math.random() * 1.2,
        phase: Math.random() * Math.PI * 2,
        speed: 0.3 + Math.random() * 0.8,
        base: 0.15 + Math.random() * 0.4
      });
    }
  }
  function renderStars(now) {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    for (var i = 0; i < stars.length; i++) {
      var s = stars[i];
      var alpha = s.base + Math.sin(now * 0.001 * s.speed + s.phase) * 0.3;
      if (alpha < 0.02) continue;
      ctx.globalAlpha = Math.min(alpha, 0.85);
      ctx.fillStyle = '#c8d6e5';
      ctx.beginPath(); ctx.arc(s.x * width, s.y * height, s.r, 0, 2 * Math.PI); ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }
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

  // --- Cluster hull rendering ---
  function renderClusterHulls() {
    if (!clusters || clusters.length === 0) return;
    var invK = 1 / transform.k;
    clusters.forEach(function (cl) {
      if (!cl.polygon || cl.polygon.length < 3) return;
      var isHover = cl.id === hoverClusterId;
      var isActive = cl.id === activeClusterId;
      var emphasized = isHover || isActive;
      ctx.beginPath();
      var cx = cl.centroid[0], cy = cl.centroid[1];
      var pad = 80;
      var pts = cl.polygon;
      for (var i = 0; i < pts.length; i++) {
        var dx = pts[i][0] - cx, dy = pts[i][1] - cy;
        var dist = Math.sqrt(dx * dx + dy * dy) || 1;
        var px = pts[i][0] + (dx / dist) * pad;
        var py = pts[i][1] + (dy / dist) * pad;
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.closePath();
      // Fill only on hover/active
      if (emphasized) {
        ctx.globalAlpha = 0.15;
        ctx.fillStyle = cl.color;
        ctx.fill();
      }
      // Outline always visible
      ctx.globalAlpha = emphasized ? 0.6 : 0.2;
      ctx.strokeStyle = cl.color;
      ctx.lineWidth = (emphasized ? 2.5 : 1.2) * invK;
      ctx.stroke();
      ctx.globalAlpha = 1;
    });
  }

  function pointInHull(px, py, polygon) {
    // Ray-casting point-in-polygon test
    var inside = false;
    for (var i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      var xi = polygon[i][0], yi = polygon[i][1];
      var xj = polygon[j][0], yj = polygon[j][1];
      if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) {
        inside = !inside;
      }
    }
    return inside;
  }

  function findClusterAt(graphX, graphY) {
    // Check expanded hulls (with padding)
    for (var i = 0; i < clusters.length; i++) {
      var cl = clusters[i];
      if (!cl.polygon || cl.polygon.length < 3) continue;
      // Build padded polygon
      var cx = cl.centroid[0], cy = cl.centroid[1], pad = 80;
      var padded = cl.polygon.map(function (pt) {
        var dx = pt[0] - cx, dy = pt[1] - cy;
        var dist = Math.sqrt(dx * dx + dy * dy) || 1;
        return [pt[0] + (dx / dist) * pad, pt[1] + (dy / dist) * pad];
      });
      if (pointInHull(graphX, graphY, padded)) return cl.id;
    }
    return -1;
  }

  function renderClusterLabels() {
    if (!clusters || clusters.length === 0) return;
    var invK = 1 / transform.k;
    var fontSize = 16 / transform.k;
    ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    clusters.forEach(function (cl) {
      if (!cl.label) return;
      var isHover = cl.id === hoverClusterId;
      var isActive = cl.id === activeClusterId;
      // Show labels at overview zoom OR when hovered/active
      if (transform.k > 0.5 && !isHover && !isActive) return;
      var cx = cl.centroid[0], cy = cl.centroid[1];
      ctx.globalAlpha = (isHover || isActive) ? 0.7 : 0.35;
      ctx.strokeStyle = 'rgba(0,0,0,0.8)';
      ctx.lineWidth = 4 * invK;
      ctx.lineJoin = 'round';
      ctx.strokeText(cl.label, cx, cy);
      ctx.fillStyle = cl.color;
      ctx.fillText(cl.label, cx, cy);
      var smallFont = 11 / transform.k;
      ctx.font = smallFont + 'px Inter, sans-serif';
      ctx.globalAlpha = (isHover || isActive) ? 0.5 : 0.25;
      ctx.fillStyle = '#94a3b8';
      ctx.fillText(cl.count + ' nodes', cx, cy + fontSize * 0.8);
      ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif';
    });
    ctx.textAlign = 'start';
    ctx.globalAlpha = 1;
  }

  function render() {
    var now = performance.now();
    ctx.save(); ctx.clearRect(0, 0, width, height);
    renderStars(now);
    ctx.translate(transform.x, transform.y); ctx.scale(transform.k, transform.k);
    var invK = 1 / transform.k;

    // Cluster background hulls (behind everything)
    renderClusterHulls();

    // Edges
    if (visibleEdges.length > 0) {
      ctx.lineWidth = 1 * invK;
      var baseAlpha = visibleEdges.length > 500 ? 0.7 : (visibleEdges.length > 50 ? 0.8 : 0.9);
      visibleEdges.forEach(function (e) {
        var s = nodeMap[e.source], t = nodeMap[e.target];
        if (!s || !t) return;
        var sx = s.x, sy = s.y, tx = t.x, ty = t.y;
        if (sx === tx && sy === ty) return;
        if (e._containment) {
          ctx.globalAlpha = 0.2;
          ctx.strokeStyle = '#94a3b8';
          ctx.lineWidth = 1 * invK;
          ctx.setLineDash([4 * invK, 4 * invK]);
          ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(tx, ty); ctx.stroke();
          ctx.setLineDash([]);
          return;
        }
        var isIncoming = highlightId && (e.target === highlightId);
        var isOutgoing = highlightId && (e.source === highlightId);
        var connected = isIncoming || isOutgoing;
        ctx.globalAlpha = highlightId ? (connected ? 0.9 : 0.06) : baseAlpha;
        ctx.strokeStyle = !highlightId ? '#fbbf24' : (isIncoming ? '#22d3ee' : (isOutgoing ? '#fb923c' : '#fbbf24'));
        ctx.lineWidth = (connected ? 2.5 : 0.8) * invK;
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(tx, ty); ctx.stroke();
      }); ctx.globalAlpha = 1; ctx.lineWidth = 1 * invK;
    }

    // Node glow halos
    if (transform.k > 0.05) {
      visibleNodes.forEach(function (n) {
        if (n._dimmed) return;
        var isFocused = n.node_id === highlightId;
        var isConnected = highlightId && _focusNeighbors && _focusNeighbors.has(n.node_id);
        var faded = highlightId && !isFocused && !isConnected;
        if (faded) return;
        var r = (n._r || 4);
        var glowR = r * 3;
        var grad = ctx.createRadialGradient(n.x, n.y, r * 0.3, n.x, n.y, glowR);
        var col = isFocused ? '#38bdf8' : (n.color || '#60a5fa');
        grad.addColorStop(0, col + '40');
        grad.addColorStop(1, col + '00');
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
      ctx.strokeStyle = isFocused ? '#7dd3fc' : 'rgba(0,0,0,0.6)';
      ctx.lineWidth = (isFocused ? 2 : 1) * invK;
      ctx.stroke();
      ctx.globalAlpha = 1;
    });

    // Cluster labels (at overview zoom)
    renderClusterLabels();

    // Node labels — constant screen size + declutter
    if (transform.k > 0.08) {
      var fontSize = 11 / transform.k;
      ctx.font = fontSize + 'px Inter, sans-serif'; ctx.textBaseline = 'middle'; ctx.textAlign = 'start';
      var candidates = [];
      visibleNodes.forEach(function (n) {
        if (n._dimmed || !n.label) return;
        var isFocused = n.node_id === highlightId;
        var isConnected = highlightId && _focusNeighbors && _focusNeighbors.has(n.node_id);
        var faded = highlightId && !isFocused && !isConnected;
        if (faded) return;
        var catPri = n.category === 'file' ? 100 : (n.category === 'type' ? 50 : 0);
        if ((n._r || 4) * transform.k > 0.8) {
          candidates.push({ n: n, focused: isFocused, priority: isFocused ? 9999 : (catPri + (n._r || 4)) });
        }
      });
      candidates.sort(function (a, b) { return b.priority - a.priority; });
      var placed = [];
      var labelH = fontSize;
      candidates.forEach(function (c) {
        var n = c.n;
        var lx = (n.x + (n._r || 4) + 3) * transform.k + transform.x;
        var ly = n.y * transform.k + transform.y;
        var lw = ctx.measureText(n.label).width * transform.k;
        var ok = true;
        for (var i = 0; i < placed.length; i++) {
          var p = placed[i];
          if (lx < p.x + p.w + 4 && lx + lw + 4 > p.x && ly - labelH < p.y + labelH && ly + labelH > p.y - labelH) {
            ok = false; break;
          }
        }
        if (ok) {
          var tx = n.x + (n._r || 4) + 3, ty = n.y;
          ctx.strokeStyle = 'rgba(0,0,0,0.7)';
          ctx.lineWidth = 3 * invK;
          ctx.lineJoin = 'round';
          ctx.strokeText(n.label, tx, ty);
          ctx.fillStyle = c.focused ? '#7dd3fc' : 'rgba(226,232,240,0.92)';
          ctx.fillText(n.label, tx, ty);
          placed.push({ x: lx, y: ly, w: lw });
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
  function getRefEdges() {
    return allEdges.filter(function (e) { return !e._containment; });
  }
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
          if (e.source === child.node_id) { neighbors.add(e.target); }
          if (e.target === child.node_id) { neighbors.add(e.source); }
        });
      });
    }
    return neighbors;
  }
  function savePositions(nodes) {
    nodes.forEach(function (n) { n._ox = n.x; n._oy = n.y; });
  }
  function restorePositions() {
    allNodes.forEach(function (n) {
      if (n._ox !== undefined) { n.x = n._ox; n.y = n._oy; delete n._ox; delete n._oy; }
    });
  }
  function spreadNodes(centerNode, nodes, edges) {
    if (nodes.length < 2) return;
    var cx = centerNode.x, cy = centerNode.y;
    var radius = Math.min(600, Math.max(200, nodes.length * 20));
    nodes.forEach(function (n, i) {
      if (n.node_id === centerNode.node_id) return;
      var angle = (2 * Math.PI * i) / (nodes.length - 1);
      n.x = cx + Math.cos(angle) * radius * 0.15 + (Math.random() - 0.5) * 10;
      n.y = cy + Math.sin(angle) * radius * 0.15 + (Math.random() - 0.5) * 10;
    });
    var nodeIndex = {}; nodes.forEach(function (n, i) { nodeIndex[n.node_id] = i; });
    var links = [];
    edges.forEach(function (e) {
      if (e._containment) return;
      if (nodeIndex[e.source] !== undefined && nodeIndex[e.target] !== undefined) {
        links.push({ source: nodeIndex[e.source], target: nodeIndex[e.target] });
      }
    });
    var sim = d3.forceSimulation(nodes)
      .alpha(1).alphaDecay(0.03).velocityDecay(0.35)
      .force('center', d3.forceCenter(cx, cy))
      .force('charge', d3.forceManyBody().strength(-800))
      .force('collide', d3.forceCollide().radius(function (n) { return (n._r || 4) + 50; }))
      .force('link', d3.forceLink(links).distance(200).strength(0.2))
      .stop();
    for (var i = 0; i < 300; i++) {
      sim.tick();
      centerNode.x = cx; centerNode.y = cy;
      nodes.forEach(function (nd) {
        if (nd === centerNode) return;
        var dx = nd.x - cx, dy = nd.y - cy;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > radius) { nd.x = cx + dx * (radius / dist); nd.y = cy + dy * (radius / dist); }
      });
      if (sim.alpha() <= sim.alphaMin()) break;
    }
  }
  function buildClusterPanel() {
    var body = $('cluster-panel-body');
    if (!body || !clusters.length) return;
    body.innerHTML = '';
    // Sort clusters by count (largest first)
    var sorted = clusters.slice().sort(function (a, b) { return b.count - a.count; });
    sorted.forEach(function (cl) {
      var item = document.createElement('div');
      item.className = 'cluster-item';
      item.setAttribute('data-cluster-id', cl.id);
      item.innerHTML = '<span class="cluster-dot" style="background:' + cl.color + '"></span>' +
        '<span class="cluster-label" title="' + esc(cl.label) + '">' + esc(cl.label) + '</span>' +
        '<span class="cluster-count">' + cl.count + '</span>';
      item.addEventListener('click', function () {
        var cid = parseInt(this.getAttribute('data-cluster-id'));
        if (activeClusterId === cid) {
          // Deselect — show all
          activeClusterId = -1;
          enterOverview();
        } else {
          filterToCluster(cid);
        }
        updateClusterPanelActive();
      });
      body.appendChild(item);
    });
    // Toggle collapse
    var header = $('cluster-panel-toggle');
    if (header) {
      header.addEventListener('click', function (e) {
        e.stopPropagation();
        body.classList.toggle('collapsed');
        this.textContent = body.classList.contains('collapsed') ? '▸' : '▾';
      });
    }
    $('cluster-panel').querySelector('.cluster-panel-header').addEventListener('click', function () {
      body.classList.toggle('collapsed');
      var btn = $('cluster-panel-toggle');
      if (btn) btn.textContent = body.classList.contains('collapsed') ? '▸' : '▾';
    });
  }
  function updateClusterPanelActive() {
    var items = document.querySelectorAll('.cluster-item');
    items.forEach(function (item) {
      var cid = parseInt(item.getAttribute('data-cluster-id'));
      item.classList.toggle('active', cid === activeClusterId);
    });
  }
  function filterToCluster(clusterId) {
    state.mode = 'overview'; state.selectedNode = null; state.selectedFile = null;
    highlightId = null; _focusNeighbors = null;
    activeClusterId = clusterId;
    restorePositions();
    visibleNodes = allNodes.filter(function (n) { return n.cluster_id === clusterId; });
    visibleNodes.forEach(function (n) { n._dimmed = false; });
    // Show edges within this cluster
    var clusterIds = new Set(); visibleNodes.forEach(function (n) { clusterIds.add(n.node_id); });
    visibleEdges = allEdges.filter(function (e) {
      return !e._containment && (clusterIds.has(e.source) || clusterIds.has(e.target));
    });
    var cl = clusters.find(function (c) { return c.id === clusterId; });
    var label = cl ? cl.label : 'Cluster ' + clusterId;
    updateStatus('Cluster: ' + label, visibleNodes.length);
    showInfoPanel(null);
    updateHelpHint('Showing cluster "' + label + '" — Click a cluster in panel to switch — Esc to reset');
    render();
  }
  function enterOverview() {
    state.mode = 'overview'; state.selectedNode = null; state.selectedFile = null;
    highlightId = null; _focusNeighbors = null;
    activeClusterId = -1;
    restorePositions();
    visibleNodes = allNodes.slice();
    visibleNodes.forEach(function (n) { n._dimmed = false; });
    visibleEdges = getRefEdges();
    updateStatus('Semantic Clusters — click to explore', visibleNodes.length); showInfoPanel(null);
    updateHelpHint('Click a node — Scroll to zoom — Drag to pan — / to search — Esc to reset');
    updateClusterPanelActive();
    render();
  }
  function enterContents(fileNodeId) {
    state.mode = 'contents'; state.selectedFile = fileNodeId; state.selectedNode = null;
    highlightId = fileNodeId; _focusNeighbors = buildNeighbors(fileNodeId);
    restorePositions();
    var children = [nodeMap[fileNodeId]];
    allNodes.forEach(function (n) { if (n.parent_node_id === fileNodeId) children.push(n); });
    var bg = allNodes.filter(function (n) { return n.category === 'file' && n.node_id !== fileNodeId; });
    bg.forEach(function (n) { n._dimmed = true; }); children.forEach(function (n) { n._dimmed = false; });
    visibleNodes = children.concat(bg);
    var childSet = new Set(); children.forEach(function (c) { childSet.add(c.node_id); });
    visibleEdges = allEdges.filter(function (e) {
      if (e._containment && e.source === fileNodeId && childSet.has(e.target)) return true;
      return !e._containment && (childSet.has(e.source) || childSet.has(e.target));
    });
    savePositions(children);
    spreadNodes(nodeMap[fileNodeId], children, visibleEdges);
    updateStatus('File: ' + ((nodeMap[fileNodeId] || {}).label || fileNodeId), children.length);
    showInfoPanel(fileNodeId); updateHelpHint('Click a symbol for connections — Click background to go back');
    render();
  }
  function enterFocus(nodeId) {
    state.mode = 'focus'; state.selectedNode = nodeId;
    highlightId = nodeId; _focusNeighbors = buildNeighbors(nodeId);
    restorePositions();
    var neighborSet = new Set(); neighborSet.add(nodeId); visibleEdges = [];
    allEdges.forEach(function (e) { if (e._containment) return; if (e.source === nodeId) { neighborSet.add(e.target); visibleEdges.push(e); } if (e.target === nodeId) { neighborSet.add(e.source); visibleEdges.push(e); } });
    visibleNodes = allNodes.filter(function (n) { return neighborSet.has(n.node_id); });
    visibleNodes.forEach(function (n) { n._dimmed = false; });
    savePositions(visibleNodes);
    spreadNodes(nodeMap[nodeId], visibleNodes, visibleEdges);
    var n = nodeMap[nodeId] || {};
    updateStatus('Focus: ' + (n.label || nodeId) + ' (in:' + (n.in_degree || 0) + ' out:' + (n.out_degree || 0) + ')', visibleNodes.length);
    showInfoPanel(nodeId); updateHelpHint('Click a neighbor to walk — Click background to go back — Esc to reset');
    render();
  }
  function doSearch(query) {
    if (!query) { enterOverview(); return; } state.mode = 'search'; highlightId = null;
    restorePositions();
    var q = query.toLowerCase();
    visibleNodes = allNodes.filter(function (n) { return (n.label || '').toLowerCase().indexOf(q) >= 0 || (n.file_path || '').toLowerCase().indexOf(q) >= 0 || n.node_id.toLowerCase().indexOf(q) >= 0; });
    visibleNodes.forEach(function (n) { n._dimmed = false; }); visibleEdges = [];
    updateStatus('Search: "' + query + '"', visibleNodes.length); showInfoPanel(null); render();
  }
  function showEntryPoints() {
    state.mode = 'search'; highlightId = null;
    restorePositions();
    visibleNodes = allNodes.filter(function (n) { return n.is_entry_point; });
    visibleNodes.forEach(function (n) { n._dimmed = false; }); visibleEdges = [];
    updateStatus('Entry Points (no callers, has calls)', visibleNodes.length); showInfoPanel(null);
    updateHelpHint('Showing entry points — Click one to explore — Esc to reset'); render();
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
    if (highlightId === n.node_id) {
      if (n.category === 'file') enterContents(n.node_id);
      else enterFocus(n.node_id);
      return;
    }
    restorePositions();
    highlightId = n.node_id;
    _focusNeighbors = buildNeighbors(n.node_id);
    // Keep ALL nodes and ALL ref edges visible — render() handles fading
    visibleNodes = allNodes.slice();
    visibleNodes.forEach(function (nd) { nd._dimmed = false; });
    visibleEdges = getRefEdges();
    showInfoPanel(n.node_id);
    var name = n.label || n.node_id;
    updateStatus(state.mode.charAt(0).toUpperCase() + state.mode.slice(1) + ' — selected: ' + name, visibleNodes.length);
    updateHelpHint('Click again to drill in — Click background to deselect — Esc to reset');
    render();
  }
  function onClickStage() {
    if (highlightId) {
      highlightId = null; _focusNeighbors = null;
      restorePositions();
      if (state.mode === 'overview') {
        visibleNodes = allNodes.slice();
        visibleNodes.forEach(function (n) { n._dimmed = false; });
        visibleEdges = getRefEdges();
      }
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
    clusters = GRAPH_DATA.clusters || [];
    var container = $('sigma-container'); width = container.offsetWidth; height = container.offsetHeight;
    canvas = d3.select(container).append('canvas').attr('width', width).attr('height', height).style('width', '100%').style('height', '100%');
    ctx = canvas.node().getContext('2d');
    zoomBehavior = d3.zoom().scaleExtent([0.01, 20]).on('zoom', function (event) { transform = event.transform; render(); });
    canvas.call(zoomBehavior);
    canvas.on('click', function (event) { var rect = canvas.node().getBoundingClientRect(); var n = findNodeAt(event.clientX - rect.left, event.clientY - rect.top); n ? onClickNode(n) : onClickStage(); });
    canvas.on('mousemove', function (event) {
      var rect = canvas.node().getBoundingClientRect();
      var sx = event.clientX - rect.left, sy = event.clientY - rect.top;
      var n = findNodeAt(sx, sy);
      canvas.node().style.cursor = n && !n._dimmed ? 'pointer' : 'default';
      // Cluster hover detection
      var pt = transform.invert([sx, sy]);
      var newHover = findClusterAt(pt[0], pt[1]);
      if (newHover !== hoverClusterId) {
        hoverClusterId = newHover;
        render();
      }
    });
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
    window.__fs2 = { allNodes: allNodes, allEdges: allEdges, nodeMap: nodeMap, clusters: clusters, enterOverview: enterOverview, enterContents: enterContents, enterFocus: enterFocus, showEntryPoints: showEntryPoints, doSearch: doSearch, state: state };
    // Populate cluster panel
    buildClusterPanel();
    initStars(300);
    fitGraph(); enterOverview();
    function tick() { render(); starTimer = requestAnimationFrame(tick); }
    tick();
  }
  function boot() {
    showLoadingScreen(); buildCategoryLegend(); populateStatusBar();
    setTimeout(function () { try { initGraph(); } catch (e) { var x = $('error-display'); if (x) { x.textContent = 'Init: ' + e.message; x.style.display = 'block'; } console.error(e); } hideLoadingScreen(); }, 150);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
