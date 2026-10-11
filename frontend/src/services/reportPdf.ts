import { jsPDF } from 'jspdf';
import { Report } from '../types/report';

/** jsPDF's built-in fonts are Latin-1 only: map common symbols to ASCII instead of printing garbage. */
export const pdfSafe = (s: string): string =>
  s.replace(/→/g, '->').replace(/±/g, '+/-').replace(/[–—]/g, '-').replace(/[“”]/g, '"').replace(/[‘’]/g, "'")
    .replace(/≥/g, '>=').replace(/≤/g, '<=').replace(/…/g, '...').replace(/[^\x00-\xFF]/g, '?');

const pct = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : 'n/a');

/** Builds the PDF from the report JSON only (no demo constants, no values that are not in the report). */
export function buildReportPdf(report: Report): jsPDF {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' });
  const W = doc.internal.pageSize.getWidth();
  const H = doc.internal.pageSize.getHeight();
  const M = 40;
  const CW = W - 2 * M;
  let y = M;

  const ensure = (h: number) => { if (y + h > H - M) { doc.addPage(); y = M; } };
  const para = (text: string, size = 9, style: 'normal' | 'bold' = 'normal', color: [number, number, number] = [30, 41, 59]) => {
    doc.setFont('helvetica', style);
    doc.setFontSize(size);
    doc.setTextColor(...color);
    const lines = doc.splitTextToSize(pdfSafe(text), CW) as string[];
    for (const line of lines) { ensure(size + 4); doc.text(line, M, y); y += size + 3; }
  };

  para(report.title, 15, 'bold', [15, 23, 42]);
  y += 2;
  const flags = [
    report.is_hypothetical ? 'HYPOTHETICAL SCENARIO (user assumptions, not observed data)' : 'REPORTED EVENT',
    report.is_simulated_data ? 'SIMULATED DATA (mock LLM / fixture articles)' : null,
  ].filter(Boolean).join('  |  ');
  para(flags, 8, 'bold', [180, 83, 9]);
  para(`Report ${report.report_id} | ${report.kind} source ${report.source_id} | created ${report.created_at} | ${report.generator}`, 7, 'normal', [100, 116, 139]);
  para('Scores are heuristic rankings, not probabilities. Nothing in this report is investment advice.', 7, 'normal', [100, 116, 139]);
  y += 6;

  report.sections.forEach((s, i) => {
    ensure(40);
    doc.setDrawColor(226, 232, 240);
    doc.line(M, y, W - M, y);
    y += 12;
    para(`${i + 1}. ${s.title}  [${s.status.toUpperCase()}]`, 11, 'bold', [15, 23, 42]);
    if (s.status === 'unavailable') para(`Not available: ${s.unavailable_reason}`, 9, 'normal', [71, 85, 105]);
    if (s.narrative) para(s.narrative);
    if (s.key === 'ml_predictions' && Array.isArray(s.data.assets) && s.status !== 'unavailable') {
      para('Model estimates (5 trading days):', 8, 'bold');
      s.data.assets.forEach((a: any) => para(
        `${a.symbol}: ${a.estimated_return_pct === null ? 'unavailable' : pct(a.estimated_return_pct)}` +
        (a.interval_80_pct ? `  (80% range ${pct(a.interval_80_pct[0])} to ${pct(a.interval_80_pct[1])})` : ''), 8));
    }
    if (Array.isArray(s.data.paths) && s.data.paths.length) {
      para('Pathways:', 8, 'bold');
      s.data.paths.slice(0, 6).forEach((p: any) => para(
        `- ${(p.node_labels ?? p.node_ids ?? []).join(' -> ')} (support ${typeof p.path_score === 'number' ? p.path_score.toFixed(2) : 'n/a'})`, 8));
    }
    s.limitations.filter(Boolean).forEach((l) => para(`Limitation: ${l}`, 8, 'normal', [146, 64, 14]));
    if (s.citations.length) {
      para('Sources:', 8, 'bold');
      s.citations.slice(0, 15).forEach((c) => para(`[${c.ref}] ${c.label}${c.url ? ` - ${c.url}` : ''}`, 7, 'normal', [71, 85, 105]));
      if (s.citations.length > 15) para(`+ ${s.citations.length - 15} more sources in the online report`, 7, 'normal', [100, 116, 139]);
    }
    y += 4;
  });
  ensure(30);
  para(`Versions: ${JSON.stringify(report.versions)}`, 6, 'normal', [148, 163, 184]);
  return doc;
}

export function downloadReportPdf(report: Report): void {
  buildReportPdf(report).save(`${report.report_id}.pdf`);
}
