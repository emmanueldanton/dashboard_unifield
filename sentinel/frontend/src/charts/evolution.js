import Plotly from 'plotly.js-dist-min';

const LAYOUT_BASE = {
  paper_bgcolor: '#0a0a0a',
  plot_bgcolor: '#0a0a0a',
  font: { color: '#f0f0f0', family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', size: 12 },
  xaxis: { gridcolor: '#262626', linecolor: '#262626', tickcolor: '#262626' },
  yaxis: { gridcolor: '#262626', linecolor: '#262626', tickcolor: '#262626' },
  legend: { bgcolor: 'transparent', bordercolor: '#262626', borderwidth: 1 },
  margin: { l: 50, r: 20, t: 20, b: 40 },
};

export function renderEvolution(container, snapshots) {
  if (!snapshots || snapshots.length === 0) {
    container.innerHTML = '<div class="empty-state">Aucun snapshot disponible — en attente du premier cycle scheduler.</div>';
    return;
  }

  const ts = snapshots.map(s => new Date(s.ts));
  const traces = [
    { x: ts, y: snapshots.map(s => s.connected), name: 'Connectés', type: 'scatter', mode: 'lines+markers', line: { color: '#7DC242', width: 2 }, marker: { size: 4 } },
    { x: ts, y: snapshots.map(s => s.disconnected), name: 'Déconnectés', type: 'scatter', mode: 'lines+markers', line: { color: '#e05252', width: 2 }, marker: { size: 4 } },
    { x: ts, y: snapshots.map(s => s.battery_low), name: 'Batterie faible', type: 'scatter', mode: 'lines+markers', line: { color: '#e0a834', width: 2, dash: 'dot' }, marker: { size: 4 } },
  ];

  Plotly.newPlot(container, traces, { ...LAYOUT_BASE }, { responsive: true, displayModeBar: false });
}
