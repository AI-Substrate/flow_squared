/**
 * graph-viewer.js — Interactive codebase explorer for fs2 reports
 *
 * View modes (FX001):
 *   overview  — file nodes only (~500), no edges, orientation
 *   contents  — clicked file's children visible
 *   focus     — clicked node + direct callers/callees, edges shown
 *
 * DYK-07: Straight arrow edges (curved deferred to Phase 3)
 * DYK-08: Node colors come pre-set from Python — no JS color map
 */

(function () {
  'use strict';

  // --- State ---
  var viewMode = 'overview'; // 'overview' | 'contents' | 'focus'
  var focusedNode = null;
  var focusedFile = null;
  var hoveredNode = null;
  var neighborSet = null;
  var renderer = null;
  var graph = null;

  // --- Helpers ---
  function formatNumber(n) {
    return (n || 0).toLocaleString();
  }

  function updateStatus(viewLabel, showingCount) {
    var viewEl = document.getElementById('status-view');
    var showEl = document.getElementById('status-showing');
    if (viewEl) viewEl.textContent = viewLabel;
    if (showEl) showEl.textContent = 'Showing ' + formatNumber(showingCount);
  }

  function showHelpHint(text) {
    var el = document.getElementById('help-hint');
    if (el) el.textContent = text;
  }

  // --- Loading Screen ---
  function showLoadingScreen() {
    var screen = document.getElementById('loading-screen');
    if (!screen || typeof METADATA === 'undefined') return;
    var m = METADATA;
    var titleEl = screen.querySelector('.loading-title .name');
    if (titleEl) titleEl.textContent = m.project_name || 'unknown';
    var subtitleEl = screen.querySelector('.loading-subtitle');
    if (subtitleEl) {
      subtitleEl.textContent = 'Generated ' + new Date(m.generated_at).toLocaleString() +
        ' · fs2 ' + (m.fs2_version || '');
    }
    var statEls = screen.querySelectorAll('.loading-stat');
    if (statEls.length >= 3) {
      statEls[0].querySelector('.value').textContent = formatNumber(m.node_count);
      statEls[1].querySelector('.value').textContent = formatNumber(m.reference_edge_count);
      statEls[2].querySelector('.value').textContent = formatNumber(m.containment_edge_count);
    }
  }

  function hideLoadingScreen() {
    var screen = document.getElementById('loading-screen');
    if (!screen) return;
    screen.classList.add('fade-out');
    setTimeout(function () { screen.style.display = 'none'; }, 500);
  }

  // --- Category Legend ---
  function buildCategoryLegend() {
    var container = document.getElementById('category-legend');
    if (!container || typeof METADATA === 'undefined') return;
    var cats = METADATA.categories || {};
    var catColors = {};
    (GRAPH_DATA.nodes || []).forEach(function (n) {
      if (n.category && n.color && !catColors[n.category]) catColors[n.category] = n.color;
    });
    var sorted = Object.entries(cats).sort(function (a, b) { return b[1] - a[1]; });
    sorted.forEach(function (entry) {
      var cat = entry[0], count = entry[1];
      var badge = document.createElement('span');
      badge.className = 'cat-badge';
      badge.innerHTML = '<span class="cat-dot" style="background:' +
        (catColors[cat] || '#9ca3af') + '"></span>' +
        cat + '<span class="cat-count">' + formatNumber(count) + '</span>';
      container.appendChild(badge);
    });
  }

  // --- Status Bar ---
  function populateStatusBar() {
    if (typeof METADATA === 'undefined') return;
    var m = METADATA;
    var nodeCount = document.getElementById('status-nodes');
    var refCount = document.getElementById('status-refs');
    var version = document.getElementById('status-version');
    if (nodeCount) nodeCount.textContent = formatNumber(m.node_count) + ' nodes';
    if (refCount) refCount.textContent = formatNumber(m.reference_edge_count) + ' refs';
    if (version) version.textContent = 'fs2 ' + (m.fs2_version || '');
  }

  // --- View Mode: Node Reducer ---
  function nodeReducer(node, data) {
    var res = Object.assign({}, data);
    var cat = data.category || graph.getNodeAttribute(node, 'category');

    if (viewMode === 'overview') {
      if (cat !== 'file') {
        res.hidden = true;
        return res;
      }
      if (hoveredNode === node) {
        res.size = (data.size || 6) * 1.8;
        res.zIndex = 1;
        res.highlighted = true;
      }
      return res;
    }

    if (viewMode === 'contents') {
      if (node === focusedFile) {
        res.size = (data.size || 6) * 1.3;
        res.zIndex = 1;
        res.color = '#38bdf8';
        return res;
      }
      var parentId = graph.getNodeAttribute(node, 'parentNodeId');
      if (parentId === focusedFile) {
        if (hoveredNode === node) {
          res.size = (data.size || 6) * 1.5;
          res.zIndex = 1;
        }
        return res;
      }
      if (cat === 'file') {
        res.color = '#1e293b';
        res.label = '';
        res.size = 2;
        return res;
      }
      res.hidden = true;
      return res;
    }

    if (viewMode === 'focus') {
      if (node === focusedNode) {
        res.size = (data.size || 6) * 2;
        res.zIndex = 2;
        res.color = '#38bdf8';
        return res;
      }
      if (neighborSet && neighborSet.has(node)) {
        if (hoveredNode === node) {
          res.size = (data.size || 6) * 1.3;
          res.zIndex = 1;
        }
        return res;
      }
      res.color = '#1a1f2e';
      res.label = '';
      res.size = 1.5;
      return res;
    }

    return res;
  }

  // --- View Mode: Edge Reducer ---
  function edgeReducer(edge, data) {
    var res = Object.assign({}, data);

    if (viewMode !== 'focus' || !focusedNode) {
      res.hidden = true;
      return res;
    }

    var source = graph.source(edge);
    var target = graph.target(edge);
    if (source === focusedNode || target === focusedNode) {
      res.hidden = false;
      res.size = 2;
      res.color = '#f59e0b';
      return res;
    }

    res.hidden = true;
    return res;
  }

  // --- View Mode Transitions ---
  function enterOverview() {
    viewMode = 'overview';
    focusedNode = null;
    focusedFile = null;
    neighborSet = null;
    var fileCount = 0;
    graph.forEachNode(function (n, a) { if (a.category === 'file') fileCount++; });
    updateStatus('Overview · click a file to explore', fileCount);
    showHelpHint('Click a file node · Scroll to zoom · Drag to pan · Esc to reset');
    renderer.refresh();
  }

  function enterContents(fileNodeId) {
    viewMode = 'contents';
    focusedFile = fileNodeId;
    focusedNode = null;
    neighborSet = null;
    var fileName = graph.getNodeAttribute(fileNodeId, 'label') || fileNodeId;
    var count = 1;
    graph.forEachNode(function (n, a) {
      if (a.parentNodeId === fileNodeId) count++;
    });
    updateStatus('File: ' + fileName, count);
    showHelpHint('Click a symbol to see connections · Click background to go back');

    var attrs = graph.getNodeAttributes(fileNodeId);
    renderer.getCamera().animate({ x: attrs.x, y: attrs.y, ratio: 0.15 }, { duration: 400 });
    renderer.refresh();
  }

  function enterFocus(nodeId) {
    viewMode = 'focus';
    focusedNode = nodeId;

    neighborSet = new Set();
    try {
      graph.forEachInNeighbor(nodeId, function (nb) { neighborSet.add(nb); });
      graph.forEachOutNeighbor(nodeId, function (nb) { neighborSet.add(nb); });
    } catch (e) { /* node may not exist */ }

    var nodeName = graph.getNodeAttribute(nodeId, 'label') || nodeId;
    var inDeg = graph.getNodeAttribute(nodeId, 'inDegree') || 0;
    var outDeg = graph.getNodeAttribute(nodeId, 'outDegree') || 0;
    updateStatus('Focus: ' + nodeName + ' (in:' + inDeg + ' out:' + outDeg + ')', neighborSet.size + 1);
    showHelpHint('Click a neighbor to walk · Click background to go back · Esc to reset');

    var attrs = graph.getNodeAttributes(nodeId);
    renderer.getCamera().animate({ x: attrs.x, y: attrs.y, ratio: 0.1 }, { duration: 400 });
    renderer.refresh();
  }

  // --- Main: Initialize Graph ---
  function initGraph() {
    if (typeof GRAPH_DATA === 'undefined' || typeof graphology === 'undefined' || typeof Sigma === 'undefined') {
      console.error('fs2 graph-viewer: Missing GRAPH_DATA, graphology, or Sigma');
      return;
    }

    var data = GRAPH_DATA;
    graph = new graphology.Graph({ multi: true, type: 'directed' });

    // Add nodes with all attributes
    (data.nodes || []).forEach(function (n) {
      try {
        graph.addNode(n.node_id, {
          x: n.x || 0,
          y: n.y || 0,
          size: n.size || 4,
          color: n.color || '#9ca3af',
          label: n.label || n.name || '',
          category: n.category || 'other',
          filePath: n.file_path || '',
          parentNodeId: n.parent_node_id || null,
          inDegree: n.in_degree || 0,
          outDegree: n.out_degree || 0,
          degree: n.degree || 0,
          depth: n.depth || 0,
          isEntryPoint: n.is_entry_point || false,
          sizeByLines: n.size_by_lines || n.size || 4,
          sizeByDegree: n.size_by_degree || 4,
          signature: n.signature || '',
          smartContent: n.smart_content || '',
        });
      } catch (e) { /* skip duplicates */ }
    });

    // Add edges
    (data.edges || []).forEach(function (e) {
      try {
        if (graph.hasNode(e.source) && graph.hasNode(e.target)) {
          graph.addEdgeWithKey(e.id, e.source, e.target, {
            color: e.color || '#f59e0b',
            size: 0.5,
            type: 'arrow',
            hidden: true,
            isReference: !e.hidden,
          });
        }
      } catch (err) { /* skip duplicates */ }
    });

    // Initialize Sigma
    var container = document.getElementById('sigma-container');
    if (!container) return;

    renderer = new Sigma(graph, container, {
      renderLabels: true,
      labelRenderedSizeThreshold: 4,
      labelFont: 'Inter, sans-serif',
      labelSize: 13,
      labelColor: { color: '#e2e8f0' },
      labelWeight: '500',
      defaultNodeType: 'circle',
      defaultEdgeType: 'arrow',
      minCameraRatio: 0.005,
      maxCameraRatio: 20,
      stagePadding: 50,
      zoomDuration: 200,
      allowInvalidContainer: true,
      nodeReducer: nodeReducer,
      edgeReducer: edgeReducer,
    });

    // Hover
    renderer.on('enterNode', function (event) {
      hoveredNode = event.node;
      container.style.cursor = 'pointer';
      renderer.refresh();
    });
    renderer.on('leaveNode', function () {
      hoveredNode = null;
      container.style.cursor = 'default';
      renderer.refresh();
    });

    // Click node
    renderer.on('clickNode', function (event) {
      var nodeId = event.node;
      var cat = graph.getNodeAttribute(nodeId, 'category');

      if (viewMode === 'overview' && cat === 'file') {
        enterContents(nodeId);
      } else {
        enterFocus(nodeId);
      }
    });

    // Click empty canvas → go back
    renderer.on('clickStage', function () {
      if (viewMode === 'focus') {
        if (focusedFile) {
          enterContents(focusedFile);
        } else {
          enterOverview();
        }
      } else if (viewMode === 'contents') {
        enterOverview();
      }
    });

    // Keyboard
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        enterOverview();
      } else if (e.key === 'f' && !e.ctrlKey && !e.metaKey && e.target === document.body) {
        renderer.getCamera().animate({ x: 0.5, y: 0.5, ratio: 1 }, { duration: 300 });
      }
    });

    // Start in overview
    enterOverview();
    return renderer;
  }

  // --- Boot ---
  function boot() {
    showLoadingScreen();
    buildCategoryLegend();
    populateStatusBar();
    setTimeout(function () {
      try { initGraph(); } catch (e) { console.error('fs2 graph-viewer init error:', e); }
      hideLoadingScreen();
    }, 100);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
