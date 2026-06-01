import Plotly from 'plotly.js-dist-min';

export function renderDonut(container, kpis) {
  const values = [kpis.connected, kpis.disconnected, kpis.batteryLow];
  const labels = ['Connectés', 'Déconnectés', 'Batterie faible'];
  const colors = ['#7DC242', '#e05252', '#e0a834'];

  const trace = {
    values,
    labels,
    type: 'pie',
    hole: 0.5,
    marker: { colors },
    textinfo: 'percent',
    textfont: { color: '#f0f0f0', size: 11 },
  };

  const layout = {
    paper_bgcolor: '#0a0a0a',
    plot_bgcolor: '#0a0a0a',
    font: { color: '#f0f0f0', family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', size: 12 },
    showlegend: true,
    legend: { bgcolor: 'transparent', x: 0, y: 0.5 },
    margin: { l: 10, r: 10, t: 10, b: 10 },
  };

  Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
}
