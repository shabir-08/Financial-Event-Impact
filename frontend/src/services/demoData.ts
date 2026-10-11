import { FinancialEvent } from '../types/event';
import { GraphNodeData, GraphEdgeData, GroundingLogicContent } from '../types/graph';
import { MarketAnalysisData } from '../types/market';
import { RelationshipEvidenceItem } from '../types/evidence';
import { SavedAnalysesSummary } from '../types/saved';
import { UserProfile } from '../types/auth';

export const DEMO_USER: UserProfile = {
  id: 'usr_harshad',
  username: 'Harshad P',
  name: 'Harshad Patankar',
  email: 'harshad.patankar@xyz.finance',
  role: 'Senior Research Analyst',
  organization: 'XYZ Research Team',
  avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80',
};

export const DEMO_EVENTS: FinancialEvent[] = [
  {
    id: 'evt_strait_disruption',
    title: 'Strait disruption sends freight costs higher',
    headline: 'Strait disruption sends freight costs higher',
    summary: "A hypothetical shipping disruption tests the world's supply chains. Trace the ripple effects from longer voyages to importer margins and carrier yields.",
    category: 'Global Trade',
    domain: 'Trade',
    region: 'Global',
    publishedAt: '2026-10-11T09:00:00Z',
    timeAgo: '2 hrs ago',
    readTime: '6 MIN READ',
    impact: 'High',
    imageUrl: '/images/strait-disruption.png',
    imageCaption: 'Shipping lanes are the starting point for a wider economic chain reaction. Illustrative imagery.',
    isFeatured: true,
    exposureWatch: [
      { sector: 'Shipping', type: 'positive', impactDescription: 'Carrier yields benefit from tighter capacity.' },
      { sector: 'Importers', type: 'negative', impactDescription: 'Higher landed costs put margins under pressure.' },
      { sector: 'Energy', type: 'positive', impactDescription: 'Longer voyages increase bunker-fuel demand.' }
    ],
    modelInfo: {
      name: 'MODEL XYZ-TRADE',
      version: 'v1.0',
      transitTimeChange: '+4 days',
      freightCostChange: '+12.0%',
      importerMarginChange: '-1.8 pp',
      carrierYieldChange: '+6.0%'
    }
  },
  {
    id: 'evt_bunker_fuel',
    title: 'Extra sailing days drive bunker-fuel demand higher',
    headline: 'Extra sailing days drive bunker-fuel demand higher',
    summary: 'Rerouted voyages add thousands of nautical miles, translating directly into elevated fuel consumption per cargo unit.',
    category: 'Energy / Bunker Fuel',
    domain: 'Energy',
    region: 'Global',
    publishedAt: '2026-10-11T08:30:00Z',
    timeAgo: '3 hrs ago',
    readTime: '4 MIN READ',
    impact: 'High',
    imageUrl: '/images/bunker-fuel-tanker.png',
    imageCaption: 'Tanker voyages on Cape of Good Hope routes.',
    isFeatured: false
  },
  {
    id: 'evt_carrier_yields',
    title: 'Tighter capacity lifts carrier yields across key lanes',
    headline: 'Tighter capacity lifts carrier yields across key lanes',
    summary: 'Capacity absorbed by longer voyages reduces effective supply, giving carriers pricing power in spot negotiations.',
    category: 'Shipping / Carrier Yields',
    domain: 'Transport',
    region: 'Asia',
    publishedAt: '2026-10-11T08:45:00Z',
    timeAgo: '2 hrs ago',
    readTime: '5 MIN READ',
    impact: 'Medium',
    imageUrl: '/images/carrier-yields-deck.png',
    imageCaption: 'Container vessel loading operations.',
    isFeatured: false
  },
  {
    id: 'evt_importer_margins',
    title: 'Landed costs put importer margins under pressure',
    headline: 'Landed costs put importer margins under pressure',
    summary: 'Higher freight rates erode the cushion between import price and shelf price. Companies with thin margins feel it first.',
    category: 'Importers / Margins',
    domain: 'Trade',
    region: 'EU',
    publishedAt: '2026-10-11T08:15:00Z',
    timeAgo: '3 hrs ago',
    readTime: '5 MIN READ',
    impact: 'High',
    imageUrl: '/images/importer-margins-port.png',
    imageCaption: 'Rotterdam terminal container staging area.',
    isFeatured: false
  },
  {
    id: 'evt_big_picture',
    title: 'One disruption. A network of consequences.',
    headline: 'One disruption. A network of consequences.',
    summary: 'Follow the connections between shipping, logistics, working capital and consumers in an interconnected global trade network.',
    category: 'Commodity Shock',
    domain: 'Trade',
    region: 'Global',
    publishedAt: '2026-10-11T08:00:00Z',
    timeAgo: '4 hrs ago',
    readTime: '7 MIN READ',
    impact: 'Medium',
    isFeatured: false
  },
  {
    id: 'evt_retail_margins',
    title: 'Retail margins face a second-order test',
    headline: 'Retail margins face a second-order test',
    summary: 'Our model traces how higher landed costs could reach earnings over the next quarter as seasonal contracts reset.',
    category: 'Equities',
    domain: 'Banking',
    region: 'USA',
    publishedAt: '2026-10-11T07:45:00Z',
    timeAgo: '4 hrs ago',
    readTime: '3 MIN READ',
    impact: 'Medium',
    isFeatured: false
  },
  {
    id: 'evt_brent_opec',
    title: 'Brent up 12% on OPEC+ output cut',
    headline: 'Brent up 12% on OPEC+ output cut',
    summary: 'Crude benchmark surges following unexpected production quotas, sparking cost concerns across aviation and energy-intensive manufacturing.',
    category: 'Commodity Shock',
    domain: 'Energy',
    region: 'Global',
    publishedAt: '2026-10-11T07:00:00Z',
    timeAgo: '5 hrs ago',
    readTime: '6 MIN READ',
    impact: 'High',
    imageUrl: '/images/bunker-fuel-tanker.png',
    isFeatured: false
  }
];

export const DEMO_GRAPH_NODES: GraphNodeData[] = [
  {
    id: 'node_trigger',
    label: 'Strait disruption',
    sublabel: 'Transit +4 days',
    tag: 'INITIATING EVENT',
    category: 'trigger',
    entityCategory: 'event',
    exposure: 'negative',
    metric: 'Transit +4 days',
    confidenceScore: 0.94,
    impactDirection: 'negative',
    relatedEventTitle: 'Strait disruption sends freight costs higher',
    downstreamEffects: [
      'Forced circumnavigation via Cape of Good Hope (+3,500 nm)',
      'Global effective fleet capacity absorption of ~9% TEU'
    ],
    limitations: 'Disruption duration remains volatile and dependent on geopolitical resolutions.',
    evidenceCount: 3,
    knowledgeBaseCount: 1,
    x: 140,
    y: 140,
    description: 'Initial geopolitical naval chokepoint restriction enforcing immediate maritime transit diversion.'
  },
  {
    id: 'node_voyages',
    label: 'Longer voyages',
    sublabel: 'Route extension',
    tag: 'LOGISTICS VARIABLE',
    category: 'transmission',
    entityCategory: 'variable',
    exposure: 'neutral',
    metric: '+4 to 12 days',
    confidenceScore: 0.92,
    impactDirection: 'neutral',
    relatedEventTitle: 'Strait disruption sends freight costs higher',
    downstreamEffects: [
      'Elevated bunker fuel consumption across regional bunkering ports',
      'Shortage of available vessel tonnage on East-West trade loops'
    ],
    limitations: 'Liner cruising speed adjustments (speeding up or slow-steaming) may buffer schedule variance.',
    evidenceCount: 3,
    knowledgeBaseCount: 1,
    x: 340,
    y: 210,
    description: 'Merchant vessels diverted around southern African capes, adding 10 to 14 sailing days per voyage.'
  },
  {
    id: 'node_bunker',
    label: 'Bunker fuel',
    sublabel: 'Demand ↑',
    tag: 'ENERGY VARIABLE',
    category: 'adjacent_energy',
    entityCategory: 'variable',
    exposure: 'positive',
    metric: 'Liftings +45%',
    confidenceScore: 0.89,
    impactDirection: 'positive',
    relatedEventTitle: 'Strait disruption sends freight costs higher',
    downstreamEffects: [
      'Tightening VLSFO fuel availability in Durban, Mauritius, and Las Palmas',
      'Refining margins widen on heavy distillate crack spreads'
    ],
    limitations: 'Fuel inventory buffer at bunkering hubs varies by regional terminal.',
    evidenceCount: 2,
    knowledgeBaseCount: 1,
    x: 270,
    y: 390,
    description: 'Extended sea mileage drives incremental high-sulfur and VLSFO marine fuel burn per completed loop.'
  },
  {
    id: 'node_freight',
    label: 'Freight costs',
    sublabel: '+12.0% modeled',
    tag: 'PRICING VARIABLE',
    category: 'selected_cost',
    entityCategory: 'variable',
    exposure: 'selected',
    metric: '+12.0% modeled',
    confidenceScore: 0.91,
    impactDirection: 'negative',
    relatedEventTitle: 'Strait disruption sends freight costs higher',
    downstreamEffects: [
      'Carrier yields expand +6.0% via spot rate surcharges',
      'Importer gross margins compress -1.8 pp through landed cost increases'
    ],
    limitations: 'Contractual long-term liner pricing buffers immediate spot surge for blue-chip shippers.',
    evidenceCount: 4,
    knowledgeBaseCount: 1,
    x: 550,
    y: 230,
    description: 'Artificial fleet capacity constraints trigger immediate spot container rate escalation across major shipping lanes.'
  },
  {
    id: 'node_carrier',
    label: 'Carrier yields',
    sublabel: '+6.0% modeled',
    tag: 'MARITIME SECTOR',
    category: 'first_order_sector',
    entityCategory: 'sector',
    exposure: 'positive',
    metric: '+6.0% modeled',
    confidenceScore: 0.85,
    impactDirection: 'positive',
    relatedEventTitle: 'Strait disruption sends freight costs higher',
    downstreamEffects: [
      'Container liner EBITDA estimates revised higher',
      'Emergency transit surcharge institution ($1,200/FEU)'
    ],
    limitations: 'Offset by incremental bunker fuel burn expenses and repositioning costs.',
    evidenceCount: 2,
    knowledgeBaseCount: 1,
    x: 760,
    y: 150,
    description: 'Ocean carrier operators capture higher freight yields as shipper competition for slots intensifies.'
  },
  {
    id: 'node_importer',
    label: 'Importer margins',
    sublabel: '-1.8 pp modeled',
    tag: 'RETAIL SECTOR',
    category: 'second_order_sector',
    entityCategory: 'sector',
    exposure: 'negative',
    metric: '-1.8 pp modeled',
    confidenceScore: 0.88,
    impactDirection: 'negative',
    relatedEventTitle: 'Strait disruption sends freight costs higher',
    downstreamEffects: [
      'Working capital absorption in expanded inventory safety buffers',
      'Selective retail shelf price adjustments with 3-month lag'
    ],
    limitations: 'Retailers with pre-stocked seasonal domestic inventories experience delayed margin impact.',
    evidenceCount: 3,
    knowledgeBaseCount: 1,
    x: 770,
    y: 370,
    description: 'Wholesale importers absorb inflated landed shipping tariffs, leading to compressed operating margins.'
  },
  {
    id: 'node_maersk',
    label: 'A.P. Moller-Maersk',
    sublabel: 'Liner Operator',
    tag: 'COMPANY / OPERATOR',
    category: 'asset',
    entityCategory: 'company',
    exposure: 'positive',
    metric: '+5.4% modeled EBIT',
    confidenceScore: 0.86,
    impactDirection: 'positive',
    relatedEventTitle: 'Strait disruption sends freight costs higher',
    downstreamEffects: [
      'Full year fleet utilization guided near maximum capacity',
      'Positive contract renegotiation leverage on transpacific corridors'
    ],
    limitations: 'Exposure subject to network re-routing agility and port dwell times.',
    evidenceCount: 2,
    knowledgeBaseCount: 1,
    x: 970,
    y: 150,
    description: 'Global ocean container liner benefiting from sustained freight rate increases and slot tightness.'
  },
  {
    id: 'node_retailers',
    label: 'Consumer Retailers',
    sublabel: 'Importers & Big Box',
    tag: 'COMPANY / RETAIL',
    category: 'asset',
    entityCategory: 'company',
    exposure: 'negative',
    metric: '-120 bps margin',
    confidenceScore: 0.84,
    impactDirection: 'negative',
    relatedEventTitle: 'Strait disruption sends freight costs higher',
    downstreamEffects: [
      'Downside revisions to discretionary retail operating income',
      'Inventory replenishment stock-out risks before promotional calendar'
    ],
    limitations: 'Discretionary suppliers face lower price elasticity than essential staple retailers.',
    evidenceCount: 2,
    knowledgeBaseCount: 0,
    x: 970,
    y: 370,
    description: 'Global retail corporations facing margin compression from freight surcharges and transit delays.'
  }
];

export const DEMO_GRAPH_EDGES: GraphEdgeData[] = [
  {
    id: 'edge_trigger_voyages',
    source: 'node_trigger',
    target: 'node_voyages',
    label: 'reroutes',
    relationType: 'reroutes',
    confidenceScore: 0.94,
    evidenceCount: 3,
    isObserved: true
  },
  {
    id: 'edge_voyages_bunker',
    source: 'node_voyages',
    target: 'node_bunker',
    label: 'adds demand',
    relationType: 'adds_demand',
    confidenceScore: 0.89,
    evidenceCount: 2,
    isObserved: true
  },
  {
    id: 'edge_voyages_freight',
    source: 'node_voyages',
    target: 'node_freight',
    label: 'raises',
    relationType: 'raises',
    confidenceScore: 0.91,
    evidenceCount: 4,
    isObserved: true
  },
  {
    id: 'edge_freight_carrier',
    source: 'node_freight',
    target: 'node_carrier',
    label: 'supports yields',
    relationType: 'supports_yields',
    confidenceScore: 0.85,
    evidenceCount: 2,
    isObserved: false
  },
  {
    id: 'edge_freight_importer',
    source: 'node_freight',
    target: 'node_importer',
    label: 'pressures margins',
    relationType: 'pressures_margins',
    confidenceScore: 0.88,
    evidenceCount: 3,
    isObserved: false
  },
  {
    id: 'edge_carrier_maersk',
    source: 'node_carrier',
    target: 'node_maersk',
    label: 'expands EBIT',
    relationType: 'supports_yields',
    confidenceScore: 0.86,
    evidenceCount: 2,
    isObserved: false
  },
  {
    id: 'edge_importer_retailers',
    source: 'node_importer',
    target: 'node_retailers',
    label: 'squeezes margin',
    relationType: 'pressures_margins',
    confidenceScore: 0.84,
    evidenceCount: 2,
    isObserved: false
  }
];

export const DEMO_GROUNDING_LOGIC: Record<string, GroundingLogicContent> = {
  node_freight: {
    nodeId: 'node_freight',
    nodeTitle: 'Freight costs',
    modeledMetric: '+12.0% / scenario assumption',
    causalLink: 'In this fictional scenario, a strait disruption adds four days to voyages. Longer round trips tie up vessels, reducing effective shipping capacity. We model freight costs rising 12% as a result.',
    impactFlow: 'Higher freight costs flow into importer landed costs. With only partial pass-through to customers, the scenario models a 1.8 percentage-point margin decline. Carriers see a 6% yield uplift instead.',
    graphSupport: 'Brief A defines the route change. Brief B connects capacity to freight costs. Brief C translates those costs into sector exposure. The arrows encode assumed mechanisms, not verified causal findings.',
    keyUncertainty: 'Duration, spare vessel capacity and customer pass-through could change the outcome. These inputs are illustrative, not forecasts.',
    disclaimer: 'AI-generated scenario explanation. Review assumptions before using any conclusion.'
  },
  node_trigger: {
    nodeId: 'node_trigger',
    nodeTitle: 'Strait disruption',
    modeledMetric: 'Transit +4 days / trigger point',
    causalLink: 'Geopolitical closure or severe naval checkpoint delays require immediate vessel diversion across southern capes.',
    impactFlow: 'Adds immediate voyage duration, impacting liner schedule integrity and vessel turnaround windows across world hubs.',
    graphSupport: 'Derived from initial scenario briefing and maritime route optimization models.',
    keyUncertainty: 'Disruption duration remains volatile and dependent on geopolitical resolutions.',
    disclaimer: 'Scenario simulation parameters. Not investment advice.'
  },
  node_voyages: {
    nodeId: 'node_voyages',
    nodeTitle: 'Longer voyages',
    modeledMetric: 'Route extension / transit delay',
    causalLink: 'Vessels bypassing restricted waters are forced to transit extended maritime routes, adding approximately 3,000 to 4,500 nautical miles.',
    impactFlow: 'Ties up container tonnage in transit, reducing effective weekly sailings between Asia and Europe.',
    graphSupport: 'Calculated via global route routing matrix and historical bypass operations.',
    keyUncertainty: 'Vessel cruising speed adjustments (speeding up or slow-steaming) may buffer delay.',
    disclaimer: 'Assumed average route divergence across key commercial liner services.'
  },
  node_bunker: {
    nodeId: 'node_bunker',
    nodeTitle: 'Bunker fuel',
    modeledMetric: 'Demand ↑ / fuel consumption',
    causalLink: 'Longer sailing distances and accelerated cruising speeds directly increase fuel burn per standard twenty-foot equivalent unit (TEU).',
    impactFlow: 'Boosts regional bunkering volume at intermediate refueling ports like Singapore, Mauritius, and Gibraltar.',
    graphSupport: 'Empirical marine propulsion fuel burn curves cross-referenced against voyage duration.',
    keyUncertainty: 'Variations in heavy fuel oil (VLSFO) vs marine gasoil pricing elasticity.',
    disclaimer: 'Illustrative fuel requirement delta modeled on typical ultra-large container ships.'
  },
  node_carrier: {
    nodeId: 'node_carrier',
    nodeTitle: 'Carrier yields',
    modeledMetric: '+6.0% modeled / revenue enhancement',
    causalLink: 'Constrained supply of effective slot capacity shifts pricing power toward container shipping alliances, elevating spot and short-term contract rates.',
    impactFlow: 'Increases average revenue per TEU transported, bolstering top-line carrier earnings in the short run.',
    graphSupport: 'Correlation observed during historical maritime chokepoint closures.',
    keyUncertainty: 'Contract renegotiation lag and shipper resistance to bunker adjustment factor (BAF) surcharges.',
    disclaimer: 'Based on synthetic market equilibrium model.'
  },
  node_importer: {
    nodeId: 'node_importer',
    nodeTitle: 'Importer margins',
    modeledMetric: '-1.8 pp modeled / margin compression',
    causalLink: 'Rising ocean transport tariffs raise landed product costs for finished goods, consumer discretionary items, and capital equipment.',
    impactFlow: 'Companies with fixed retail commitments or tight gross margins suffer compressed EBITDA percentages before price adjustments take effect.',
    graphSupport: 'Aggregated supply-chain cost pass-through studies across European and North American retail groups.',
    keyUncertainty: 'Inventories already in domestic warehouses offer temporary buffer.',
    disclaimer: 'Illustrative macro sensitivity. Individual company performance varies.'
  }
};

export const DEMO_PROPAGATION_PATHS = [
  {
    id: 'path_1',
    title: 'Strait disruption → Importer margins',
    nodes: [
      { label: 'Strait disruption', tag: 'Trigger', metric: 'Transit +4 days', status: 'trigger' },
      { label: 'Longer voyages', tag: 'Transmission', metric: '+4 days', status: 'transmission' },
      { label: 'Freight costs', tag: 'Cost', metric: '+12.0%', status: 'selected' },
      { label: 'Importer margins', tag: 'Sector', metric: '-1.8 pp', status: 'negative' }
    ],
    mechanism: 'Maritime chokepoint diversion absorbs effective fleet capacity, raising spot freight rates which are passed down to importer balance sheets as inflated landed costs.',
    evidenceCount: 3,
    confidence: '88% confidence',
    assetAffected: 'Retail & Consumer Goods Importers'
  },
  {
    id: 'path_2',
    title: 'Strait disruption → Carrier yields',
    nodes: [
      { label: 'Strait disruption', tag: 'Trigger', metric: 'Transit +4 days', status: 'trigger' },
      { label: 'Longer voyages', tag: 'Transmission', metric: '+4 days', status: 'transmission' },
      { label: 'Freight costs', tag: 'Cost', metric: '+12.0%', status: 'selected' },
      { label: 'Carrier yields', tag: 'Sector', metric: '+6.0%', status: 'positive' }
    ],
    mechanism: 'Slot shortage shifts market power to ocean carriers, who capture higher freight rates per container transported.',
    evidenceCount: 2,
    confidence: '85% confidence',
    assetAffected: 'Global Container Shipping Operators'
  },
  {
    id: 'path_3',
    title: 'Strait disruption → Bunker fuel demand',
    nodes: [
      { label: 'Strait disruption', tag: 'Trigger', metric: 'Transit +4 days', status: 'trigger' },
      { label: 'Longer voyages', tag: 'Transmission', metric: '+4 days', status: 'transmission' },
      { label: 'Bunker fuel', tag: 'Energy', metric: 'Demand ↑', status: 'positive' }
    ],
    mechanism: 'Longer mileage requires greater metric tons of bunker fuel per completed journey.',
    evidenceCount: 2,
    confidence: '89% confidence',
    assetAffected: 'Marine Bunker Suppliers'
  }
];

export const DEMO_EVIDENCE_RELATIONSHIPS: RelationshipEvidenceItem[] = [
  {
    id: 'rel_crude_fuel',
    sourceLabel: 'Crude +12%',
    targetLabel: 'Fuel costs',
    relationString: 'Crude +12% → Fuel costs',
    extractedCount: 2,
    knowledgeBaseCount: 0,
    hasNoEvidence: false,
    extractedArticles: [
      {
        id: 'art_1',
        sourceOutlet: 'EXAMPLE NEWSWIRE',
        publishedAt: '14 Sep 2026, 08:42 IST',
        headline: 'Carriers brace for higher fuel bills after crude surge',
        url: 'https://news.example.com/markets/2026/09/14/carriers-fuel-bills',
        passage: 'Jet fuel costs rose sharply on Monday as Brent crude jumped 12%, with carriers warning that a higher fuel bill would squeeze margins across the airline sector.',
        highlightedTokens: [
          { text: 'Jet fuel costs rose sharply on Monday as ', isEntity: false },
          { text: 'Brent crude jumped 12%', isEntity: true },
          { text: ', with carriers warning that a higher ', isEntity: false },
          { text: 'fuel', isEntity: true },
          { text: ' bill would squeeze margins across the ', isEntity: false },
          { text: 'airline', isEntity: true },
          { text: ' sector.', isEntity: false }
        ],
        eventTitle: 'Brent up 12% on OPEC+ output cut',
        relationshipLabel: 'Crude +12% → Fuel costs'
      }
    ],
    knowledgeBaseEntries: []
  },
  {
    id: 'rel_fuel_airlines',
    sourceLabel: 'Fuel costs',
    targetLabel: 'Airlines',
    relationString: 'Fuel costs → Airlines',
    extractedCount: 2,
    knowledgeBaseCount: 1,
    hasNoEvidence: false,
    propagationPathDescription: 'Seen in 1 propagation path · 3 evidence items (2 extracted, 1 knowledge base)',
    pathTokens: ['Crude +12%', 'Fuel costs', 'Airlines', 'IndiGo'],
    extractedArticles: [
      {
        id: 'art_2',
        sourceOutlet: 'EXAMPLE NEWSWIRE',
        publishedAt: '14 Sep 2026, 08:42 IST',
        headline: 'Carriers brace for higher fuel bills after crude surge',
        url: 'https://news.example.com/markets/2026/09/14/carriers-fuel-bills',
        passage: 'Jet fuel costs rose sharply on Monday as Brent crude jumped 12%, with carriers warning that a higher fuel bill would squeeze margins across the airline sector.',
        highlightedTokens: [
          { text: 'Jet fuel costs rose sharply on Monday as ', isEntity: false },
          { text: 'Brent crude jumped 12%', isEntity: true },
          { text: ', with carriers warning that a higher ', isEntity: false },
          { text: 'fuel', isEntity: true },
          { text: ' bill would squeeze margins across the ', isEntity: false },
          { text: 'airline', isEntity: true },
          { text: ' sector.', isEntity: false }
        ],
        eventTitle: 'Brent up 12% on OPEC+ output cut',
        relationshipLabel: 'Fuel costs → Airlines'
      },
      {
        id: 'art_3',
        sourceOutlet: 'SAMPLE MARKETS DAILY',
        publishedAt: '14 Sep 2026, 11:15 IST',
        headline: 'Airline shares slip as oil jumps on supply cut',
        url: 'https://markets.example.org/equities/airline-shares-oil-jump',
        passage: null, // missing passage demonstration
        eventTitle: 'Brent up 12% on OPEC+ output cut',
        entityLabel: 'Airlines'
      }
    ],
    knowledgeBaseEntries: [
      {
        id: 'kb_1',
        entryCode: 'Entry KB-0000 (placeholder)',
        title: 'Fuel is one of the largest operating costs for airlines',
        relationshipType: 'sector cost dependency',
        rationale: 'Introduced as an inferred link in this event. Aviation fuel typically represents 25% to 35% of airline operational expenditures depending on fleet age and hedging ratios.'
      }
    ]
  },
  {
    id: 'rel_crude_inflation',
    sourceLabel: 'Crude +12%',
    targetLabel: 'Inflation',
    relationString: 'Crude +12% → Inflation',
    extractedCount: 0,
    knowledgeBaseCount: 1,
    hasNoEvidence: false,
    extractedArticles: [],
    knowledgeBaseEntries: [
      {
        id: 'kb_2',
        entryCode: 'Entry KB-0012',
        title: 'Energy price increases propagate to headline consumer inflation',
        relationshipType: 'macroeconomic transmission',
        rationale: 'Primary energy inputs influence headline consumer price index baskets directly through transportation fuels and electricity generation costs.'
      }
    ]
  },
  {
    id: 'rel_inflation_rates',
    sourceLabel: 'Inflation',
    targetLabel: 'Rates',
    relationString: 'Inflation → Rates',
    extractedCount: 0,
    knowledgeBaseCount: 1,
    hasNoEvidence: false,
    extractedArticles: [],
    knowledgeBaseEntries: [
      {
        id: 'kb_3',
        entryCode: 'Entry KB-0015',
        title: 'Central banks respond to sticky inflation with policy rate tightening',
        relationshipType: 'monetary policy reaction function',
        rationale: 'Taylor rule dynamics indicate monetary authorities raise nominal benchmark rates when inflation expectations exceed inflation targets.'
      }
    ]
  },
  {
    id: 'rel_rates_realestate',
    sourceLabel: 'Rates',
    targetLabel: 'Real estate',
    relationString: 'Rates → Real estate',
    extractedCount: 0,
    knowledgeBaseCount: 0,
    hasNoEvidence: true,
    extractedArticles: [],
    knowledgeBaseEntries: [],
    unsupportedMessage: 'No article passages and no knowledge-base entries were returned for this relationship. Treat it as unsupported. Nothing has been written in to fill the gap.'
  },
  {
    id: 'rel_strait_voyages',
    sourceLabel: 'Strait disruption',
    targetLabel: 'Longer voyages',
    relationString: 'Strait disruption → Longer voyages',
    extractedCount: 2,
    knowledgeBaseCount: 1,
    hasNoEvidence: false,
    propagationPathDescription: 'Seen in 3 propagation paths · Primary maritime choke transit reroute',
    pathTokens: ['Strait disruption', 'Longer voyages', 'Freight costs', 'Importer margins'],
    extractedArticles: [
      {
        id: 'art_strait_1',
        sourceOutlet: 'MARITIME INTELLIGENCE WEEKLY',
        publishedAt: '15 Sep 2026, 09:15 UTC',
        headline: 'Containerships divert around Cape of Good Hope as strait closure enters Day 4',
        url: 'https://shipping.example.com/analysis/2026/09/cape-rerouting',
        passage: 'Major container liners began vectoring ultra-large vessels around southern Africa on Tuesday, adding 3,500 nautical miles and 10 to 14 days of sea time to standard Asia-North Europe rotations.',
        highlightedTokens: [
          { text: 'Major container liners began vectoring ultra-large vessels around southern Africa on Tuesday, adding ', isEntity: false },
          { text: '3,500 nautical miles and 10 to 14 days of sea time', isEntity: true },
          { text: ' to standard ', isEntity: false },
          { text: 'Asia-North Europe rotations', isEntity: true },
          { text: '.', isEntity: false }
        ],
        eventTitle: 'Strait disruption sends freight costs higher',
        relationshipLabel: 'Strait disruption → Longer voyages'
      }
    ],
    knowledgeBaseEntries: [
      {
        id: 'kb_strait_1',
        entryCode: 'Entry KB-0041',
        title: 'Geopolitical maritime chokepoints enforce circumnavigation routes',
        relationshipType: 'logistical geography',
        rationale: 'Vessel passage denial at primary straits compels navigation via alternative capes, adding 30-40% effective transit duration.'
      }
    ]
  },
  {
    id: 'rel_voyages_freight',
    sourceLabel: 'Longer voyages',
    targetLabel: 'Freight costs',
    relationString: 'Longer voyages → Freight costs',
    extractedCount: 2,
    knowledgeBaseCount: 1,
    hasNoEvidence: false,
    propagationPathDescription: 'Seen in 2 propagation paths · Fleet capacity absorption',
    pathTokens: ['Longer voyages', 'Freight costs', 'Importer margins'],
    extractedArticles: [
      {
        id: 'art_freight_1',
        sourceOutlet: 'GLOBAL LOGISTICS MONITOR',
        publishedAt: '15 Sep 2026, 14:30 UTC',
        headline: 'Spot container benchmark jumps 18% as extended sea voyages absorb vessel capacity',
        url: 'https://logistics.example.org/freight/spot-index-surge',
        passage: 'The World Container Index rose 18% week-on-week as longer voyages absorbed an estimated 9% of global active TEU capacity, creating immediate equipment deficits at origin hubs.',
        highlightedTokens: [
          { text: 'The World Container Index rose 18% week-on-week as ', isEntity: false },
          { text: 'longer voyages', isEntity: true },
          { text: ' absorbed an estimated 9% of global active TEU capacity, driving up ', isEntity: false },
          { text: 'freight costs', isEntity: true },
          { text: '.', isEntity: false }
        ],
        eventTitle: 'Strait disruption sends freight costs higher',
        relationshipLabel: 'Longer voyages → Freight costs'
      }
    ],
    knowledgeBaseEntries: [
      {
        id: 'kb_freight_1',
        entryCode: 'Entry KB-0052',
        title: 'Effective container supply elasticity is negative during sustained transit delays',
        relationshipType: 'shipping economics',
        rationale: 'Every additional sailing day ties up container inventory in transit, producing artificial spot container shortages that accelerate pricing power for ocean carriers.'
      }
    ]
  },
  {
    id: 'rel_freight_importers',
    sourceLabel: 'Freight costs',
    targetLabel: 'Importer margins',
    relationString: 'Freight costs → Importer margins',
    extractedCount: 2,
    knowledgeBaseCount: 1,
    hasNoEvidence: false,
    propagationPathDescription: 'Downstream corporate margin compression',
    pathTokens: ['Freight costs', 'Importer margins', 'Retail Discretionary'],
    extractedArticles: [
      {
        id: 'art_imp_1',
        sourceOutlet: 'FINANCIAL TIMES',
        publishedAt: '16 Sep 2026, 07:00 BST',
        headline: 'Retailers face quarterly margin squeeze as shipping surcharges bite',
        url: 'https://ft.example.com/content/retail-margin-squeeze-freight',
        passage: 'Apparel and electronics importers warned of a 150 to 220 basis point erosion in gross margins if ocean freight rates remain elevated past the upcoming peak inventory stocking window.',
        highlightedTokens: [
          { text: 'Apparel and electronics importers warned of a ', isEntity: false },
          { text: '150 to 220 basis point erosion in gross margins', isEntity: true },
          { text: ' if ', isEntity: false },
          { text: 'ocean freight rates', isEntity: true },
          { text: ' remain elevated.', isEntity: false }
        ],
        eventTitle: 'Strait disruption sends freight costs higher',
        relationshipLabel: 'Freight costs → Importer margins'
      }
    ],
    knowledgeBaseEntries: [
      {
        id: 'kb_imp_1',
        entryCode: 'Entry KB-0063',
        title: 'Wholesale landed price passthrough lag',
        relationshipType: 'microeconomic pricing delay',
        rationale: 'Retail contract prices are renegotiated semi-annually, preventing immediate passthrough of sudden container surcharges.'
      }
    ]
  },
  {
    id: 'rel_freight_carriers',
    sourceLabel: 'Freight costs',
    targetLabel: 'Carrier yields',
    relationString: 'Freight costs → Carrier yields',
    extractedCount: 1,
    knowledgeBaseCount: 1,
    hasNoEvidence: false,
    propagationPathDescription: 'Operating leverage for liner shipping companies',
    pathTokens: ['Freight costs', 'Carrier yields', 'Maersk / Hapag-Lloyd'],
    extractedArticles: [
      {
        id: 'art_car_1',
        sourceOutlet: 'SHIPPING ANALYST BRIEFING',
        publishedAt: '16 Sep 2026, 11:20 CET',
        headline: 'Carrier EBITDA estimates revised upwards as emergency surcharges take effect',
        url: 'https://shippinganalyst.example.com/briefing/carrier-yields',
        passage: 'Ocean carriers instituted contingency surcharges of $1,200 per forty-foot box, providing immediate margin expansion above incremental fuel bunker burn rates.',
        highlightedTokens: [
          { text: 'Ocean carriers instituted contingency surcharges of $1,200 per box, providing immediate ', isEntity: false },
          { text: 'carrier yield expansion', isEntity: true },
          { text: '.', isEntity: false }
        ],
        eventTitle: 'Strait disruption sends freight costs higher',
        relationshipLabel: 'Freight costs → Carrier yields'
      }
    ],
    knowledgeBaseEntries: [
      {
        id: 'kb_car_1',
        entryCode: 'Entry KB-0071',
        title: 'Liner operating leverage under supply constraint',
        relationshipType: 'industrial organization',
        rationale: 'Fixed cost fleet structure generates disproportionate operating cash flow as spot rates exceed breakeven thresholds.'
      }
    ]
  },
  {
    id: 'rel_voyages_bunker',
    sourceLabel: 'Longer voyages',
    targetLabel: 'Bunker fuel demand',
    relationString: 'Longer voyages → Bunker fuel demand',
    extractedCount: 2,
    knowledgeBaseCount: 0,
    hasNoEvidence: false,
    propagationPathDescription: 'Fuel consumption scaling with transit distance',
    pathTokens: ['Longer voyages', 'Bunker fuel demand', 'Singapore / Rotterdam Hubs'],
    extractedArticles: [
      {
        id: 'art_bunker_1',
        sourceOutlet: 'BUNKER MARKET REVIEW',
        publishedAt: '16 Sep 2026, 15:40 SGT',
        headline: 'Bunker demand surges in South African and Mauritian ports as ships reroute',
        url: 'https://bunkers.example.com/market/durban-bunker-surge',
        passage: 'Very Low Sulfur Fuel Oil (VLSFO) liftings in Durban and Port Louis jumped 45% week-on-week as diverted merchant ships refueled ahead of longer oceanic crossings.',
        highlightedTokens: [
          { text: 'VLSFO liftings in Durban jumped 45% as ', isEntity: false },
          { text: 'diverted ships refueled', isEntity: true },
          { text: ' during ', isEntity: false },
          { text: 'longer voyages', isEntity: true },
          { text: '.', isEntity: false }
        ],
        eventTitle: 'Strait disruption sends freight costs higher',
        relationshipLabel: 'Longer voyages → Bunker fuel demand'
      }
    ],
    knowledgeBaseEntries: []
  },
  {
    id: 'rel_bunker_refineries',
    sourceLabel: 'Bunker fuel',
    targetLabel: 'Refinery margins',
    relationString: 'Bunker fuel → Refinery margins',
    extractedCount: 0,
    knowledgeBaseCount: 1,
    hasNoEvidence: false,
    propagationPathDescription: 'Product crack spread widening',
    pathTokens: ['Bunker fuel', 'Refinery margins', 'Valero / Neste'],
    extractedArticles: [],
    knowledgeBaseEntries: [
      {
        id: 'kb_ref_1',
        entryCode: 'Entry KB-0089',
        title: 'Middle distillate crack spreads respond to maritime fuel deficits',
        relationshipType: 'refinery economics',
        rationale: 'Refining configurations shift crude runs toward marine diesel and low-sulfur heavy distillates, expanding clean crack spreads.'
      }
    ]
  },
  {
    id: 'rel_port_inventory',
    sourceLabel: 'Port congestion',
    targetLabel: 'Inventory buffer',
    relationString: 'Port congestion → Inventory buffer',
    extractedCount: 0,
    knowledgeBaseCount: 0,
    hasNoEvidence: true,
    propagationPathDescription: 'Supply chain lead-time volatility buffer stock',
    pathTokens: ['Port congestion', 'Inventory buffer'],
    extractedArticles: [],
    knowledgeBaseEntries: [],
    unsupportedMessage: 'No empirical article citations or verified knowledge-base axioms were found for port congestion transmission to retail inventory buffer stock in the current dataset.'
  }
];

export const DEMO_MARKET_DATA: MarketAnalysisData = {
  eventId: 'evt_brent_opec',
  eventHeadline: 'Brent up 12% on OPEC+ output cut',
  eventDate: '14 Sep 2026',
  assets: [
    {
      assetId: 'ast_indigo',
      name: 'IndiGo (InterGlobe Aviation)',
      symbol: 'INDIGO',
      assetType: 'Equity',
      exchange: 'NSE',
      dataProvider: 'Example provider',
      currency: 'INR',
      latestObservation: 'Close · 9 Oct 2026, 15:30 IST',
      dataFreshness: 'Not live · last close, 2 days ago',
      availability: 'Available',
      availabilityNote: 'daily prices returned for full selected range'
    },
    {
      assetId: 'ast_ongc',
      name: 'Oil and Natural Gas Corporation',
      symbol: 'ONGC',
      assetType: 'Equity',
      exchange: 'NSE',
      dataProvider: 'Example provider',
      currency: 'INR',
      latestObservation: 'Close · 9 Oct 2026, 15:30 IST',
      dataFreshness: 'Not live · last close, 2 days ago',
      availability: 'Partial',
      availabilityNote: '3 trading days missing due to exchange maintenance'
    },
    {
      assetId: 'ast_nifty_realty',
      name: 'Nifty Realty Index',
      symbol: 'NIFTY REALTY',
      assetType: 'Index',
      exchange: 'NSE',
      dataProvider: 'Example provider',
      currency: 'INR',
      latestObservation: 'Observation unavailable',
      dataFreshness: 'No coverage',
      availability: 'Unavailable',
      availabilityNote: 'No history returned. Cause: provider coverage.'
    }
  ],
  selectedAssetId: 'ast_indigo',
  priceHistory: {
    ast_indigo: [
      { date: '2026-09-01', displayDate: '1 Sep', close: 4860 },
      { date: '2026-09-03', displayDate: '3 Sep', close: 4840 },
      { date: '2026-09-05', displayDate: '5 Sep', close: 4880 },
      { date: '2026-09-08', displayDate: '8 Sep', close: 4860 },
      { date: '2026-09-10', displayDate: '10 Sep', close: 4890 },
      { date: '2026-09-12', displayDate: '12 Sep', close: 4875 },
      { date: '2026-09-14', displayDate: '14 Sep', close: 4880, isEventDate: true, isInEventWindow: true },
      { date: '2026-09-15', displayDate: '15 Sep', close: 4850, isInEventWindow: true },
      { date: '2026-09-17', displayDate: '17 Sep', close: 4810, isInEventWindow: true },
      { date: '2026-09-19', displayDate: '19 Sep', close: 4780, isInEventWindow: true },
      { date: '2026-09-21', displayDate: '21 Sep', close: 4760, isInEventWindow: true },
      // Missing observations gap: 21 Sep to 28 Sep
      { date: '2026-09-23', displayDate: '23 Sep', close: null, isMissing: true },
      { date: '2026-09-25', displayDate: '25 Sep', close: null, isMissing: true },
      { date: '2026-09-27', displayDate: '27 Sep', close: null, isMissing: true },
      { date: '2026-09-28', displayDate: '28 Sep', close: 4740 },
      { date: '2026-09-30', displayDate: '30 Sep', close: 4720 },
      { date: '2026-10-02', displayDate: '2 Oct', close: 4750 },
      { date: '2026-10-05', displayDate: '5 Oct', close: 4760 },
      { date: '2026-10-07', displayDate: '7 Oct', close: 4730 },
      { date: '2026-10-09', displayDate: '9 Oct', close: 4740 }
    ],
    ast_ongc: [
      { date: '2026-09-01', displayDate: '1 Sep', close: 295 },
      { date: '2026-09-08', displayDate: '8 Sep', close: 298 },
      { date: '2026-09-14', displayDate: '14 Sep', close: 302, isEventDate: true, isInEventWindow: true },
      { date: '2026-09-17', displayDate: '17 Sep', close: 312, isInEventWindow: true },
      { date: '2026-09-21', displayDate: '21 Sep', close: 318, isInEventWindow: true },
      { date: '2026-09-28', displayDate: '28 Sep', close: 322 },
      { date: '2026-10-05', displayDate: '5 Oct', close: 326 },
      { date: '2026-10-09', displayDate: '9 Oct', close: 330 }
    ],
    ast_nifty_realty: []
  },
  returns: {
    ast_indigo: [
      { window: '1 trading day', returnVal: -0.63, returnPercentStr: '-0.63%', status: 'Complete' },
      { window: '3 trading days', returnVal: -1.84, returnPercentStr: '-1.84%', status: 'Complete' },
      { window: '5 trading days', returnVal: -2.50, returnPercentStr: '-2.50%', status: 'Complete' },
      { window: '20 trading days', returnVal: null, returnPercentStr: 'Not available', status: 'Not available', statusNote: '19 of 20 days observed' }
    ],
    ast_ongc: [
      { window: '1 trading day', returnVal: 3.31, returnPercentStr: '+3.31%', status: 'Complete' },
      { window: '3 trading days', returnVal: 5.29, returnPercentStr: '+5.29%', status: 'Complete' },
      { window: '5 trading days', returnVal: 6.82, returnPercentStr: '+6.82%', status: 'Complete' },
      { window: '20 trading days', returnVal: null, returnPercentStr: 'Not available', status: 'Not available', statusNote: '17 of 20 days observed' }
    ]
  },
  similarEvents: [
    {
      title: 'OPEC+ surprise output cut',
      sampleDate: 'Sample date: 2 Apr 2023',
      assetSymbol: 'IndiGo',
      observedReturn: '-2.1%',
      windowLabel: '(5d)'
    },
    {
      title: 'Crude supply disruption',
      sampleDate: 'Sample date: 14 Sep 2019',
      assetSymbol: 'IndiGo',
      observedReturn: '-4.3%',
      windowLabel: '(5d)'
    }
  ],
  limitations: 'Limitations: different fuel price levels, overlapping market-wide moves, and small sample size. These are observed movements, not evidence that the event caused them.',
  dataAvailabilityCards: [
    {
      assetId: 'ast_indigo',
      assetName: 'IndiGo',
      status: 'Available',
      details: 'Daily prices returned for the full selected range.'
    },
    {
      assetId: 'ast_ongc',
      assetName: 'ONGC',
      status: 'Partial',
      details: '3 trading days missing. Cause: missing observations. Gaps are shown, never filled in.'
    },
    {
      assetId: 'ast_nifty_realty',
      assetName: 'Nifty Realty',
      status: 'Unavailable',
      details: 'No history returned. Cause: provider coverage.'
    }
  ]
};

export const DEMO_SAVED_ANALYSES: SavedAnalysesSummary = {
  persistenceConfirmed: true,
  totalCount: 6,
  completeCount: 3,
  partialCount: 1,
  failedCount: 1,
  runningCount: 1,
  records: [
    {
      id: 'sav_1',
      userGivenName: 'Q4 oil shock review',
      originalEventTitle: 'Brent up 12% on OPEC+ output cut',
      eventId: 'evt_brent_opec',
      category: 'Commodity shock',
      analysedAt: '11 Oct 2026, 09:10',
      status: 'Complete',
      nodesCount: 13,
      pathsCount: 4,
      evidenceStatus: 'Available',
      historicalDataStatus: 'Partial'
    },
    {
      id: 'sav_2',
      originalEventTitle: 'Central bank holds rates, signals caution',
      eventId: 'evt_rates_hold',
      category: 'Interest-rate decision',
      analysedAt: '9 Oct 2026, 16:42',
      status: 'Complete',
      nodesCount: 9,
      pathsCount: 3,
      evidenceStatus: 'Partial',
      historicalDataStatus: 'Available'
    },
    {
      id: 'sav_3',
      originalEventTitle: 'New import duty on electronics proposed',
      eventId: 'evt_import_duty',
      category: 'Regulatory change',
      analysedAt: '7 Oct 2026, 11:05',
      status: 'Complete',
      nodesCount: 11,
      pathsCount: 3,
      evidenceStatus: 'Available',
      historicalDataStatus: 'Unavailable'
    },
    {
      id: 'sav_4',
      originalEventTitle: 'Port strike disrupts container shipping',
      eventId: 'evt_port_strike',
      category: 'Geopolitical',
      analysedAt: '3 Oct 2026, 08:30',
      status: 'Partial',
      nodesCount: 6,
      pathsCount: 2,
      evidenceStatus: 'Unavailable',
      historicalDataStatus: 'Unavailable'
    },
    {
      id: 'sav_5',
      originalEventTitle: 'Metals prices fall on demand worries',
      eventId: 'evt_metals_fall',
      category: 'Commodity shock',
      analysedAt: '30 Sep 2026, 14:18',
      status: 'Failed',
      nodesCount: null,
      pathsCount: null,
      evidenceStatus: null,
      historicalDataStatus: null
    },
    {
      id: 'sav_6',
      originalEventTitle: 'Currency swings after trade data release',
      eventId: 'evt_currency_swings',
      category: 'Macro data',
      analysedAt: '30 Sep 2026, 10:02',
      status: 'Running',
      nodesCount: null,
      pathsCount: null,
      evidenceStatus: null,
      historicalDataStatus: null
    }
  ]
};
