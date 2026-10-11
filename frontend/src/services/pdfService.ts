import { jsPDF } from 'jspdf';
import { FinancialEvent } from '../types/event';
import { GraphNodeData, GraphEdgeData, GroundingLogicContent } from '../types/graph';
import { RelationshipEvidenceItem } from '../types/evidence';
import { MarketAnalysisData } from '../types/market';

export interface PdfExportOptions {
  event: FinancialEvent;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  groundingLogic: GroundingLogicContent | null;
  propagationPaths: any[];
  evidence: RelationshipEvidenceItem[];
  marketData?: MarketAnalysisData | null;
}

export async function generateAnalysisPdf(options: PdfExportOptions): Promise<void> {
  const { event, nodes, edges, groundingLogic, propagationPaths, evidence, marketData } = options;
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'pt',
    format: 'a4',
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 40;
  const contentWidth = pageWidth - margin * 2;
  let y = margin;

  const checkPageBreak = (requiredHeight: number) => {
    if (y + requiredHeight > pageHeight - margin) {
      doc.addPage();
      y = margin;
      // Header on subsequent pages
      doc.setFontSize(8);
      doc.setTextColor(148, 163, 184);
      doc.text(`XYZ FINANCIAL INTELLIGENCE — ${event.headline}`, margin, y);
      doc.setDrawColor(226, 232, 240);
      doc.line(margin, y + 6, pageWidth - margin, y + 6);
      y += 24;
    }
  };

  // 1. Cover / Header Banner
  doc.setFillColor(37, 99, 235); // Royal Blue #2563EB
  doc.rect(margin, y, contentWidth, 6, 'F');
  y += 20;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(37, 99, 235);
  doc.text('XYZ FINANCIAL INTELLIGENCE', margin, y);

  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(100, 116, 139);
  doc.text(`DATE: ${new Date().toLocaleDateString('en-GB')} · DEMO DATA: FICTIONAL, NOT BACKEND RESULTS`, margin + 200, y);
  y += 20;

  // Title
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(15, 23, 42);
  const splitHeadline = doc.splitTextToSize(event.headline, contentWidth);
  doc.text(splitHeadline, margin, y);
  y += splitHeadline.length * 20 + 8;

  // Meta bar
  doc.setFontSize(9);
  doc.setTextColor(71, 85, 105);
  const metaLine = `Category: ${event.category}  |  Domain: ${event.domain}  |  Region: ${event.region}  |  Model: ${event.modelInfo?.name || 'XYZ-CORE'}`;
  doc.text(metaLine, margin, y);
  y += 16;

  // Summary box
  doc.setFillColor(248, 250, 252);
  doc.setDrawColor(226, 232, 240);
  doc.roundedRect(margin, y, contentWidth, 54, 4, 4, 'FD');
  doc.setFontSize(9);
  doc.setFont('helvetica', 'italic');
  doc.setTextColor(51, 65, 85);
  const splitSummary = doc.splitTextToSize(`Executive Briefing: ${event.summary}`, contentWidth - 20);
  doc.text(splitSummary, margin + 10, y + 18);
  y += 66;

  // 2. Scenario Metric Impact Pills
  if (event.modelInfo) {
    checkPageBreak(50);
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Modeled Scenario Shocks', margin, y);
    y += 14;

    const pills = [
      { label: 'Transit time', val: event.modelInfo.transitTimeChange || '+4 days' },
      { label: 'Freight cost', val: event.modelInfo.freightCostChange || '+12.0%' },
      { label: 'Importer margin', val: event.modelInfo.importerMarginChange || '-1.8 pp' },
      { label: 'Carrier yield', val: event.modelInfo.carrierYieldChange || '+6.0%' },
    ];

    const pillWidth = (contentWidth - 30) / 4;
    pills.forEach((p, idx) => {
      const px = margin + idx * (pillWidth + 10);
      doc.setFillColor(241, 245, 249);
      doc.roundedRect(px, y, pillWidth, 32, 3, 3, 'F');
      doc.setFontSize(8);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(100, 116, 139);
      doc.text(p.label, px + 8, y + 12);
      doc.setFontSize(10);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(30, 41, 59);
      doc.text(p.val, px + 8, y + 26);
    });
    y += 46;
  }

  // 3. Knowledge Graph Topology Summary
  checkPageBreak(120);
  doc.setFontSize(11);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(30, 41, 59);
  doc.text(`Event Impact Network Graph (${nodes.length} Entities / ${edges.length} Relationships)`, margin, y);
  y += 16;

  // Table header
  doc.setFillColor(241, 245, 249);
  doc.rect(margin, y, contentWidth, 18, 'F');
  doc.setFontSize(8);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(71, 85, 105);
  doc.text('Relationship (Source → Target)', margin + 10, y + 12);
  doc.text('Mechanism Type', margin + 260, y + 12);
  doc.text('Confidence Score', margin + 400, y + 12);
  y += 22;

  edges.forEach((edge) => {
    checkPageBreak(20);
    const sourceNode = nodes.find((n) => n.id === edge.source);
    const targetNode = nodes.find((n) => n.id === edge.target);
    const conf = edge.confidenceScore ? `${Math.round(edge.confidenceScore * 100)}%` : 'Unavailable';

    doc.setFontSize(8);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(30, 41, 59);
    doc.text(`${sourceNode?.label || edge.source}  →  ${targetNode?.label || edge.target}`, margin + 10, y + 10);
    doc.text(edge.label || edge.relationType, margin + 260, y + 10);
    doc.text(conf, margin + 400, y + 10);
    doc.setDrawColor(241, 245, 249);
    doc.line(margin, y + 16, margin + contentWidth, y + 16);
    y += 18;
  });
  y += 14;

  // 4. Propagation Paths
  if (propagationPaths && propagationPaths.length > 0) {
    checkPageBreak(100);
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Causal Propagation Paths', margin, y);
    y += 16;

    propagationPaths.forEach((path, i) => {
      checkPageBreak(65);
      doc.setFillColor(248, 250, 252);
      doc.roundedRect(margin, y, contentWidth, 52, 3, 3, 'F');

      const chainStr = path.nodes.map((n: any) => n.label).join('  →  ');
      doc.setFontSize(8.5);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(37, 99, 235);
      doc.text(`Path ${i + 1}: ${chainStr}`, margin + 10, y + 14);

      doc.setFontSize(8);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(71, 85, 105);
      const splitMech = doc.splitTextToSize(path.mechanism, contentWidth - 20);
      doc.text(splitMech, margin + 10, y + 28);
      y += 60;
    });
    y += 10;
  }

  // 5. Grounding Logic Explanation
  if (groundingLogic) {
    checkPageBreak(140);
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text(`Grounding Logic: ${groundingLogic.nodeTitle} (${groundingLogic.modeledMetric})`, margin, y);
    y += 16;

    const sections = [
      { title: '01 / The Causal Link', body: groundingLogic.causalLink },
      { title: '02 / Where the Impact Goes', body: groundingLogic.impactFlow },
      { title: '03 / Supporting Evidence', body: groundingLogic.graphSupport },
      { title: 'Key Uncertainty & Limitations', body: groundingLogic.keyUncertainty },
    ];

    sections.forEach((sec) => {
      checkPageBreak(40);
      doc.setFontSize(8);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(51, 65, 85);
      doc.text(sec.title, margin + 10, y);
      y += 12;

      doc.setFont('helvetica', 'normal');
      doc.setTextColor(71, 85, 105);
      const lines = doc.splitTextToSize(sec.body, contentWidth - 20);
      doc.text(lines, margin + 10, y);
      y += lines.length * 11 + 8;
    });
  }

  // 6. Supporting Evidence & Sources
  if (evidence && evidence.length > 0) {
    checkPageBreak(100);
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Key Supporting Evidence Citations', margin, y);
    y += 16;

    evidence.forEach((item) => {
      if (item.extractedArticles && item.extractedArticles.length > 0) {
        item.extractedArticles.forEach((art) => {
          checkPageBreak(50);
          doc.setFontSize(8);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(15, 23, 42);
          doc.text(`[${art.sourceOutlet}] ${art.headline}`, margin + 10, y);
          y += 12;

          doc.setFont('helvetica', 'italic');
          doc.setTextColor(71, 85, 105);
          const quote = art.passage ? `"${art.passage}"` : '[Original passage was not provided by source API]';
          const splitQuote = doc.splitTextToSize(quote, contentWidth - 20);
          doc.text(splitQuote, margin + 10, y);
          y += splitQuote.length * 11 + 6;

          doc.setFont('helvetica', 'normal');
          doc.setFontSize(7.5);
          doc.setTextColor(148, 163, 184);
          doc.text(`Source URL: ${art.url}`, margin + 10, y);
          y += 14;
        });
      }
    });
  }

  // 7. Market Historical Data Observations
  if (marketData && marketData.assets.length > 0) {
    checkPageBreak(90);
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Market Observations & Asset Returns', margin, y);
    y += 16;

    const asset = marketData.assets[0];
    doc.setFontSize(8.5);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(51, 65, 85);
    doc.text(`Primary Linked Asset: ${asset.name} (${asset.symbol}) · Exchange: ${asset.exchange}`, margin + 10, y);
    y += 14;

    const returns = marketData.returns[asset.assetId] || [];
    if (returns.length > 0) {
      returns.forEach((r) => {
        checkPageBreak(18);
        doc.setFontSize(8);
        doc.text(`${r.window}: ${r.returnPercentStr}  (${r.status})`, margin + 10, y);
        y += 12;
      });
      y += 8;
    }

    doc.setFontSize(7.5);
    doc.setTextColor(148, 163, 184);
    const limLines = doc.splitTextToSize(marketData.limitations, contentWidth - 20);
    doc.text(limLines, margin + 10, y);
    y += limLines.length * 10 + 10;
  }

  // Footer Disclaimer
  checkPageBreak(40);
  doc.setDrawColor(226, 232, 240);
  doc.line(margin, y, pageWidth - margin, y);
  y += 14;
  doc.setFontSize(7);
  doc.setTextColor(148, 163, 184);
  doc.text('DISCLAIMER: Generated by XYZ Financial Intelligence Platform. Fictional scenario models for illustrative research only. Not investment advice.', margin, y);

  // Save the PDF
  const filename = `${event.id}_impact_analysis_report.pdf`;
  doc.save(filename);
}
