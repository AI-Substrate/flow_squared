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
  var focusedFile = null;    // file node_id for contents mode
  var hoveredNode = null;
  var neighborSet = null;    // Set of neighbor node_ids when focused
  var renderer = null;
  var graph = null;

  // --- Helpers ---
  function formatNumber(n) {
    return (n || 0).toLocaleString();
  }

  function updateStatusShowing(count) {
    var el = document.getElementById('status-showing');
    if (el) el.textContent = 'Showing ' + formatNumber(count);
  }

  function updateViewLabel(label) {
    var el = document.getElementById('status-view');
    if (el) el.textContent = label;
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
    var attrs = graph.getNodeAttributes(node);
    var cat = attrs.category;

    if (viewMode === 'overview') {
      // Only show file nodes
      if (cat !== 'file') return null;
      // Hover effect
      if (hoveredNode === node) { res.size = data.size * 1.5; res.zIndex = 1; }
      return res;
    }

    if (viewMode === 'contents') {
      // Show the focused file + its direct children
      if (node === focusedFile) {
        res.size = data.size * 1.2;
        res.zIndex = 1;
        return res;
      }
      var parentId = attrs.parentNodeId;
      if (parentId === focusedFile) {
        if (hoveredNode === node) { res.size = data.size * 1.5; res.zIndex = 1; }
        return res;
      }
      // Also show sibling files (dimmed) for context
      if (cat === 'file') {
        res.color = '#2a2e3a';
        res.label = '';
        res.size = data.size * 0.5;
        return res;
      }
      return null;
    }

    if (viewMode === 'focus') {
      if (node === focusedNode) {
        res.size = data.size * 1.5;
        res.zIndex = 2;
        return res;
      }
      if (neighborSet && neighborSet.has(node)) {
        if (hoveredNode === node) { res.size = data.size * 1.3; }
        return res;
      }
      // Dim everything else
      res.color = '#1e293b';
      res.label = '';
      res.size = 2;
      return res;
    }

    return res;
  }

  // --- View Mode: Edge Reducer ---
  function edgeReducer(edge, data) {
    if (viewMode === 'overview' || viewMode === 'contents') {
      return null; // No edges in overview/contents
    }
    if (viewMode === 'focus' && focusedNode) {
      var source = graph.source(edge);
      var target = graph.target(edge);
      if (source === focusedNode || target === focusedNode) {
        return Object.assign({}, data, { hidden: false, size: 1.5, color: '#f59e0b' });
      }
    }
    return null; // Hide all other edges
  }

  // --- View Mode Transitions ---
  function enterOverview() {
    viewMode = 'overview';
    focusedNode = null;
    focusedFile = null;
    neighborSet = null;
    updateViewLabel('Overview');
    var fileCount = 0;
    graph.forEachNode(function (n, a) { if (a.category === 'file') fileCount++; });
    updateStatusShowing(fileCount);
    renderer.refresh();
  }

  function enterContents(fileNodeId) {
    viewMode = 'contents';
    focusedFile = fileNodeId;
    focusedNode = null;
    neighborSet = null;
    var fileName = graph.getNodeAttribute(fileNodeId, 'label') || fileNodeId;
    updateViewLabel('File: ' + fileName);
    var count = 1;
    graph.forEachNode(function (n, a) {
      if (a.parentNodeId === fileNodeId) count++;
    });
    updateStatusShowing(count);

    // Animate camera to the file node
    var attrs = graph.getNodeAttributes(fileNodeId);
    renderer.getCamera().animate({ x: attrs.x, y: attrs.y, ratio: 0.3 }, { duration: 400 });
    renderer.refresh();
  }

  function enterFocus(nodeId) {
    viewMode = 'focus';
    focusedNode = nodeId;
    focusedFile = null;

    // Build neighbor set
    neighborSet = new Set();
    try {
      graph.forEachInNeighbor(nodeId, function (neighbor) { neighborSet.add(neighbor); });
      graph.forEachOutNeighbor(nodeId, function (neighbor) { neighborSet.add(neighbor); });
    } catch (e) { /* node may not exist */ }

    var nodeName = graph.getNodeAttribute(nodeId, 'label') || nodeId;
    updateViewLabel('Focus: ' + nodeName);
    updateStatusShowing(neighborSet.size + 1);

    // Animate camera
    var attrs = graph.getNodeAttributes(nodeId);
    renderer.getCamera().animate({ x: attrs.x, y: attrs.y, ratio: 0.15 }, { duration: 400 });
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
            hidden: e.hidden || false,
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
      labelRenderedSizeThreshold: 5,
      labelFont: 'Inter, sans-serif',
      labelSize: 12,
      labelColor: { color: '#e2e8f0' },
      labelWeight: '500',
      defaultNodeType: 'circle',
      defaultEdgeType: 'arrow',
      minCameraRatio: 0.01,
      maxCameraRatio: 20,
      stagePadding: 50,
      zoomDuration: 200,
      allowInvalidContainer: true,
    });

    // Set reducers
    renderer.setSetting('nodeReducer', nodeReducer);
    renderer.setSetting('edgeReducer', edgeReducer);

    // Hover
    renderer.on('enterNode', function (event) {
      hoveredNode = event.node;
      renderer.refresh();
    });
    renderer.on('leaveNode', function () {
      hoveredNode = null;
      renderer.refresh();
    });

    // Click node
    renderer.on('clickNode', function (event) {
      var nodeId = event.node;
      var attrs = graph.getNodeAttributes(nodeId);

      if (viewMode === 'overview' && attrs.category === 'file') {
        enterContents(nodeId);
      } else if (viewMode === 'contents' || viewMode === 'focus') {
        enterFocus(nodeId);
      } else {
        enterFocus(nodeId);
      }
    });

    // Click empty canvas → back to overview
    renderer.on('clickStage', function () {
      if (viewMode === 'focus') {
        // If we came from contents, go back to contents
        if (focusedFile) {
          enterContents(focusedFile);
        } else {
          enterOverview();
        }
      } else if (viewMode === 'contents') {
        enterOverview();
      }
    });

    // Keyboard: Esc → back, f → fit
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        enterOverview();
      } else if (e.key === 'f' && !e.ctrlKey && !e.metaKey) {
        renderer.getCamera().animate({ x: 0.5, y: 0.5, ratio: 1 }, { duration: 300 });
      }
    });

    // Start in overview mode
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
