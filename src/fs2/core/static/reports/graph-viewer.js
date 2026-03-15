/**
 * graph-viewer.js — Sigma.js 2 graph renderer for fs2 codebase reports
 *
 * Reads GRAPH_DATA (embedded by Jinja2), creates a Graphology graph,
 * initializes Sigma.js on #sigma-container, renders nodes + edges.
 *
 * DYK-07: Straight arrow edges (no curves in Phase 2)
 * DYK-08: Node colors come pre-set from Python — no JS color map
 */

(function () {
  'use strict';

  // --- Helpers ---
  function formatNumber(n) {
    return (n || 0).toLocaleString();
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
    setTimeout(function () {
      screen.style.display = 'none';
    }, 500);
  }

  // --- Category Legend ---
  function buildCategoryLegend() {
    var container = document.getElementById('category-legend');
    if (!container || typeof METADATA === 'undefined') return;

    var cats = METADATA.categories || {};
    // Derive category colors from node data (Python is single source of truth — DYK-08)
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

  // --- Main: Initialize Sigma.js ---
  function initGraph() {
    if (typeof GRAPH_DATA === 'undefined' || typeof graphology === 'undefined' || typeof Sigma === 'undefined') {
      console.error('fs2 graph-viewer: Missing GRAPH_DATA, graphology, or Sigma');
      return;
    }

    var data = GRAPH_DATA;
    var graph = new graphology.Graph({ multi: true, type: 'directed' });

    // Add nodes
    var nodes = data.nodes || [];
    nodes.forEach(function (n) {
      try {
        graph.addNode(n.node_id, {
          x: n.x || 0,
          y: n.y || 0,
          size: n.size || 4,
          color: n.color || '#9ca3af',
          label: n.label || n.name || '',
          category: n.category || 'other',
          filePath: n.file_path || '',
        });
      } catch (e) {
        // Skip duplicate nodes
      }
    });

    // Add edges
    var edges = data.edges || [];
    edges.forEach(function (e) {
      try {
        if (graph.hasNode(e.source) && graph.hasNode(e.target)) {
          graph.addEdgeWithKey(e.id, e.source, e.target, {
            color: e.color || '#f59e0b',
            size: e.hidden ? 0 : 0.5,
            type: 'arrow',
            hidden: e.hidden || false,
          });
        }
      } catch (err) {
        // Skip duplicate edges
      }
    });

    // Initialize Sigma renderer
    var container = document.getElementById('sigma-container');
    if (!container) return;

    var renderer = new Sigma(graph, container, {
      renderLabels: true,
      labelRenderedSizeThreshold: 6,
      labelFont: 'Inter, sans-serif',
      labelSize: 12,
      labelColor: { color: '#e2e8f0' },
      labelWeight: '500',
      defaultNodeType: 'circle',
      defaultEdgeType: 'arrow',
      edgeLabelFont: 'Inter, sans-serif',
      minCameraRatio: 0.02,
      maxCameraRatio: 20,
      stagePadding: 40,
      zoomDuration: 200,
      allowInvalidContainer: true,
    });

    // Basic hover: enlarge node on hover
    var hoveredNode = null;
    renderer.on('enterNode', function (event) {
      hoveredNode = event.node;
      renderer.refresh();
    });
    renderer.on('leaveNode', function () {
      hoveredNode = null;
      renderer.refresh();
    });

    // Node reducer for hover effect
    renderer.setSetting('nodeReducer', function (node, data) {
      var res = Object.assign({}, data);
      if (hoveredNode === node) {
        res.size = data.size * 1.5;
        res.zIndex = 1;
      }
      return res;
    });

    return renderer;
  }

  // --- Boot sequence ---
  function boot() {
    showLoadingScreen();
    buildCategoryLegend();
    populateStatusBar();

    // Small delay to let loading screen render before heavy graph init
    setTimeout(function () {
      try {
        initGraph();
      } catch (e) {
        console.error('fs2 graph-viewer init error:', e);
      }
      hideLoadingScreen();
    }, 100);
  }

  // Run on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
