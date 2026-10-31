// Executes the actual inline dashboard script with browser boundary substitutes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('dashboard/index.html', 'utf8');
const elements = {};
const context = vm.createContext({
  console,
  getComputedStyle: () => ({getPropertyValue: () => '#fff'}),
  document: {
    documentElement: {},
    querySelectorAll: () => [],
    getElementById: id => elements[id] ||= {
      innerHTML: '', textContent: '', insertAdjacentHTML() {},
      getBoundingClientRect: () => ({width: 640}),
      getContext: () => new Proxy({}, {get: () => () => {}}),
    },
  },
  window: {addEventListener() {}},
  EventSource: class { constructor() { context.stream = this; } },
  fetch: async path => ({ok: true, json: async () => path === '/nodes' ? [
    {id: 'node-A', name: 'A'}, {id: 'node-B', name: 'B'}
  ] : []}),
});
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
setImmediate(() => {
  const frame = {id:'node-A', name:'A', ts:2000, temp:25, hum:50, lux:400, anomaly:false};
  context.stream.onmessage({data: JSON.stringify(frame)});
  context.stream.onmessage({data: JSON.stringify([frame])}); // reconnect snapshot
  context.stream.onmessage({data: JSON.stringify({...frame, ts:1000, temp:99})});
  assert.equal(vm.runInContext("state['node-A'].hist.temp.length", context), 1);
  assert.equal(vm.runInContext("state['node-A'].last.temp", context), 25);
  assert.notEqual(vm.runInContext("nodeColor('node-A')", context), vm.runInContext("nodeColor('node-B')", context));
  context.stream.onerror();
  assert.match(elements.statusText.textContent, /重连/);
  console.log('dashboard ingest, colors and reconnect status passed');
});
