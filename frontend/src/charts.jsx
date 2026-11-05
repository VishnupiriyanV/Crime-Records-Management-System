// Small SVG charts drawn by hand; colours come from the theme variables so dark mode just works.

const shortMonth = (key) => new Date(`${key}-01T00:00:00`).toLocaleString('en', { month: 'short' });

// one horizontal bar per row, with the count at the end
export function Bars({ rows, label, value, title }) {
  const max = Math.max(1, ...rows.map((r) => r[value]));
  const rowHeight = 30;
  return (
    <svg className="chart" viewBox={`0 0 420 ${rows.length * rowHeight + 4}`} role="img" aria-label={title}>
      {rows.map((r, i) => {
        const y = i * rowHeight + 2;
        const width = (r[value] / max) * 200;
        return (
          <g key={r[label]}>
            <text x="0" y={y + 17} className="chart-label">{r[label]}</text>
            <rect x="170" y={y + 4} width={Math.max(width, 1)} height="16" className="chart-bar" />
            <text x={170 + width + 8} y={y + 17} className="chart-value">{r[value]}</text>
          </g>
        );
      })}
    </svg>
  );
}

// a line for complaints per month, with a dot and a count on each point
export function Line({ points, title }) {
  const width = 420, height = 170, left = 28, bottom = 24, top = 14;
  const max = Math.max(4, ...points.map((p) => p.total));
  const step = (width - left - 8) / Math.max(points.length - 1, 1);
  const x = (i) => left + i * step;
  const y = (n) => top + (height - top - bottom) * (1 - n / max);
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.total)}`).join(' ');
  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={left} x2={width - 8} y1={y(max * f)} y2={y(max * f)} className="chart-grid" />
          <text x={left - 6} y={y(max * f) + 4} textAnchor="end" className="chart-value">{Math.round(max * f)}</text>
        </g>
      ))}
      <path d={path} className="chart-line" />
      {points.map((p, i) => (
        <g key={p.month}>
          <circle cx={x(i)} cy={y(p.total)} r="3" className="chart-dot"><title>{`${p.month}: ${p.total}`}</title></circle>
          {(i % 2 === 0 || points.length < 7) && <text x={x(i)} y={height - 6} textAnchor="middle" className="chart-value">{shortMonth(p.month)}</text>}
        </g>
      ))}
    </svg>
  );
}
