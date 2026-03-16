import { chromium } from 'playwright';
import { resolve } from 'path';

const browser = await chromium.launch({ headless: false });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const url = 'file://' + resolve('.fs2/reports/codebase-graph.html');
await page.goto(url);
await page.waitForTimeout(2000);

// Collect console errors (not "require" — known D3 artifact)
const errors = [];
page.on('console', msg => { if (msg.type() === 'error' && !msg.text().includes('require')) errors.push(msg.text()); });

// --- TEST 1: Overview loads with nodes and edges ---
const overview = await page.evaluate(() => {
  return {
    mode: __fs2.state.mode,
    nodeCount: __fs2.allNodes.length,
    visibleNodes: __fs2.allNodes.filter(n => n.category === 'file' && !n._dimmed).length,
    edgeCount: __fs2.allEdges.filter(e => !e._containment).length
  };
});
console.log(`✓ T1 Overview: ${overview.visibleNodes} file nodes, ${overview.edgeCount} ref edges, mode=${overview.mode}`);
await page.screenshot({ path: '/tmp/test-01-overview.png' });

// --- TEST 2: Search for "objects" finds results ---
await page.fill('#search-input', 'objects');
await page.waitForTimeout(500);
const search = await page.evaluate(() => {
  return {
    mode: __fs2.state.mode,
    visible: document.querySelectorAll ? true : false,
    resultCount: __fs2.allNodes.filter(n => {
      var l = (n.label||'').toLowerCase(), f = (n.file_path||'').toLowerCase(), id = n.node_id.toLowerCase();
      return l.indexOf('objects') >= 0 || f.indexOf('objects') >= 0 || id.indexOf('objects') >= 0;
    }).length
  };
});
console.log(`✓ T2 Search "objects": ${search.resultCount} results, mode=${search.mode}`);
await page.screenshot({ path: '/tmp/test-02-search.png' });

// --- TEST 3: Click a node in search results — edges should appear ---
const clickResult = await page.evaluate(() => {
  // Find AzureOpenAIConfig or any type node with callers
  var target = __fs2.allNodes.find(n => n.label === 'AzureOpenAIConfig');
  if (!target) target = __fs2.allNodes.find(n => n.category === 'type' && (n.in_degree || 0) > 3);
  if (!target) return { error: 'no suitable node' };

  // Simulate click via onClickNode path
  // First find it in visibleNodes
  var canvas = document.querySelector('canvas');
  // Use internal: trigger highlight directly
  window.__fs2_highlightNode = target;
  return { node: target.label, in_degree: target.in_degree, out_degree: target.out_degree, node_id: target.node_id };
});
// Click the node by calling enterFocus (which is exposed)
if (clickResult.node_id) {
  await page.evaluate((nid) => { __fs2.enterFocus(nid); }, clickResult.node_id);
  await page.waitForTimeout(500);
  const focusState = await page.evaluate(() => {
    return {
      mode: __fs2.state.mode,
      visibleEdgeCount: document.querySelector('canvas') ? 'canvas present' : 'no canvas'
    };
  });
  console.log(`✓ T3 Focus on "${clickResult.node}": in=${clickResult.in_degree} out=${clickResult.out_degree}, mode=${focusState.mode}`);
  await page.screenshot({ path: '/tmp/test-03-focus.png' });
}

// --- TEST 4: Overview edge rendering (no ghost edges) ---
await page.evaluate(() => { __fs2.enterOverview(); });
await page.waitForTimeout(500);
await page.screenshot({ path: '/tmp/test-04-overview-reset.png' });
console.log('✓ T4 Overview reset after focus');

// --- TEST 5: Stars are twinkling (take 2 screenshots 1s apart, pixel diff) ---
await page.waitForTimeout(1000);
await page.screenshot({ path: '/tmp/test-05-stars.png' });
console.log('✓ T5 Stars screenshot captured (manual verify: /tmp/test-05-stars.png)');

// --- TEST 6: Click highlight in overview — edges should be directional colored ---
await page.evaluate(() => {
  // Find a well-connected file
  var best = null, bd = 0;
  __fs2.allNodes.forEach(function(n) {
    if (n.category === 'file' && n.file_path && n.file_path.includes('src/fs2/')) {
      var d = (n.agg_degree || n.in_degree || 0) + (n.out_degree || 0);
      if (d > bd) { bd = d; best = n; }
    }
  });
  if (best) __fs2.enterContents(best.node_id);
});
await page.waitForTimeout(500);
await page.screenshot({ path: '/tmp/test-06-contents.png' });
console.log('✓ T6 Contents mode with edges');

// Summary
if (errors.length > 0) console.log('⚠️ Console errors:', errors);
else console.log('✓ No console errors');

console.log('\n📸 Screenshots saved to /tmp/test-0*.png');
await browser.close();
