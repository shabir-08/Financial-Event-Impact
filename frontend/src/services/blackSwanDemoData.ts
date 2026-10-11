import {
  BlackSwanScenarioPreset,
  BlackSwanNode3D,
  BlackSwanEdge3D,
  ImpactPathway,
  SimulationTimelineStage,
  SimulationResponse,
  HistoricalObservationPoint
} from '../types/blackSwan';

/**
 * 5 Hypothetical Scenario Presets with customizable shock parameters
 */
export const BLACK_SWAN_PRESETS: BlackSwanScenarioPreset[] = [
  {
    id: 'global_oil_supply_shock',
    name: 'Global Oil Supply Shock',
    category: 'Energy & Commodities',
    description: 'Hypothetical 20% spike in Brent crude resulting from major maritime chokepoint shutdown or sudden OPEC+ supply curtailment.',
    channels: ['Crude Oil Benchmarks', 'Import Tariffs', 'Headline CPI', 'Currency Pass-Through'],
    isHistoricalTemplate: true,
    assumptionStatus: 'Historical Calibrated',
    parameters: [
      {
        id: 'crude_oil_change_pct',
        label: 'Brent Crude Shock',
        unit: '%',
        defaultValue: 20,
        min: -30,
        max: 80,
        step: 5,
        description: 'Direct percentage shift in spot crude oil price assumptions.',
        tooltip: 'India imports ~85% of its crude requirements, creating immediate current account and margin pressure.'
      },
      {
        id: 'usd_inr_change_pct',
        label: 'USD/INR Depreciation',
        unit: '%',
        defaultValue: 3.0,
        min: -5,
        max: 15,
        step: 0.5,
        description: 'Estimated currency depreciation against the US Dollar.',
        tooltip: 'Elevated import oil bills expand current account deficit, triggering INR weakness.'
      },
      {
        id: 'global_inflation_change_pct',
        label: 'Headline Inflation Shock',
        unit: 'pp',
        defaultValue: 1.5,
        min: 0,
        max: 5,
        step: 0.25,
        description: 'Direct contribution to domestic CPI basket via fuel & transport.',
        tooltip: 'Translates to fuel price increases and second-order price adjustments in logistics.'
      }
    ]
  },
  {
    id: 'geopolitical_crisis',
    name: 'Major Geopolitical Crisis',
    category: 'Geopolitics & Trade Routes',
    description: 'Regional conflict disrupting naval trade routes, escalating marine war-risk insurance and forcing Cape of Good Hope circumnavigation.',
    channels: ['Voyage Transit Days', 'Container Freight Rates', 'Bunker Fuel Surcharges'],
    isHistoricalTemplate: false,
    assumptionStatus: 'Hypothetical Scenario',
    parameters: [
      {
        id: 'shipping_cost_change_pct',
        label: 'Ocean Freight Rate Shock',
        unit: '%',
        defaultValue: 25,
        min: -10,
        max: 100,
        step: 5,
        description: 'Surge in standard twenty-foot equivalent container spot tariffs.',
        tooltip: 'Reflects constrained liner capacity and elevated risk premiums.'
      },
      {
        id: 'transit_delay_days',
        label: 'Vessel Transit Delay',
        unit: 'days',
        defaultValue: 8,
        min: 1,
        max: 20,
        step: 1,
        description: 'Average voyage prolongation around alternate oceanic routes.',
        tooltip: 'Ties up international fleet capacity, creating destination container deficits.'
      },
      {
        id: 'disruption_duration_months',
        label: 'Disruption Horizon',
        unit: 'months',
        defaultValue: 3,
        min: 1,
        max: 12,
        step: 1,
        description: 'Projected duration before normal diplomatic transit resumes.',
        tooltip: 'Determines whether inventories can buffer the landed cost shock.'
      }
    ]
  },
  {
    id: 'interest_rate_shock',
    name: 'Interest-Rate Shock',
    category: 'Monetary Policy',
    description: 'Stubborn sticky inflation triggers sudden 75 bps benchmark rate hike cycle across central banks, raising funding and mortgage costs.',
    channels: ['RBI Repo Rate', '10Y Sovereign Yield', 'Corporate Borrowing Spreads', 'Bank NIMs'],
    isHistoricalTemplate: true,
    assumptionStatus: 'Provisional Model Assumption',
    parameters: [
      {
        id: 'repo_rate_change_bps',
        label: 'RBI Repo Rate Hike',
        unit: 'bps',
        defaultValue: 75,
        min: 25,
        max: 250,
        step: 25,
        description: 'Immediate upward revision to policy repo rate.',
        tooltip: 'Drives short-term money market benchmarks and bank marginal cost of lending (MCLR).'
      },
      {
        id: 'gsec_10y_change_bps',
        label: '10Y G-Sec Yield Shift',
        unit: 'bps',
        defaultValue: 45,
        min: 0,
        max: 150,
        step: 5,
        description: 'Sovereign benchmark bond yield shift.',
        tooltip: 'Impacts treasury mark-to-market valuations for public and private Indian lenders.'
      },
      {
        id: 'credit_spread_change_bps',
        label: 'Corporate Credit Spread',
        unit: 'bps',
        defaultValue: 35,
        min: 0,
        max: 120,
        step: 5,
        description: 'Widening risk premium for corporate debt issuance.',
        tooltip: 'Elevates refinancing overhead for capital-intensive infrastructure and industrials.'
      }
    ]
  },
  {
    id: 'tariff_trade_war',
    name: 'Trade War / Tariff Shock',
    category: 'Protectionism & Trade',
    description: 'Imposition of sudden 15% reciprocal import duties on steel, chemicals, electronics, and automotive components.',
    channels: ['Bilateral Tariffs', 'Export Realizations', 'Supply Chain Diversion'],
    isHistoricalTemplate: false,
    assumptionStatus: 'Hypothetical Scenario',
    parameters: [
      {
        id: 'tariff_change_pct',
        label: 'Global Tariff Surcharge',
        unit: '%',
        defaultValue: 15,
        min: 5,
        max: 45,
        step: 2.5,
        description: 'Ad valorem tariff increase on target industrial goods.',
        tooltip: 'Increases price of imported capital machinery and intermediate components.'
      },
      {
        id: 'export_volume_drop_pct',
        label: 'Export Volume Contraction',
        unit: '%',
        defaultValue: 8,
        min: 0,
        max: 25,
        step: 1,
        description: 'Estimated dampening of domestic outbound shipping orders.',
        tooltip: 'Reflects retaliatory barrier enforcement across key export corridors.'
      }
    ]
  },
  {
    id: 'pandemic_supply_chain',
    name: 'Pandemic / Supply-Chain Disruption',
    category: 'Systemic Health & Logistics',
    description: 'Strict regional quarantine restrictions closing key hub ports, doubling container turnaround dwell times.',
    channels: ['Port Congestion', 'Factory Utilization', 'Inventory Stock-Outs'],
    isHistoricalTemplate: true,
    assumptionStatus: 'Historical Calibrated',
    parameters: [
      {
        id: 'port_dwell_time_days',
        label: 'Port Turnaround Dwell',
        unit: 'days',
        defaultValue: 12,
        min: 2,
        max: 30,
        step: 2,
        description: 'Average delay per vessel at container berths.',
        tooltip: 'Prevents punctual delivery of raw materials and finished components.'
      },
      {
        id: 'industrial_output_change_pct',
        label: 'Manufacturing Capacity Drop',
        unit: '%',
        defaultValue: -10,
        min: -30,
        max: 0,
        step: 2,
        description: 'Estimated drop in factory floor operating throughput.',
        tooltip: 'Directly impacts manufacturing revenue and quarterly sales run-rates.'
      }
    ]
  }
];

/**
 * Historical time-series points for Indian assets during significant market shocks
 */
const INDIGO_HISTORICAL: HistoricalObservationPoint[] = [
  { date: 'T-15d', value: 3820, benchmarkValue: 24500, eventPeriod: 'pre' },
  { date: 'T-10d', value: 3890, benchmarkValue: 24650, eventPeriod: 'pre' },
  { date: 'T-5d', value: 3850, benchmarkValue: 24700, eventPeriod: 'pre' },
  { date: 'Event', value: 3620, benchmarkValue: 24200, eventPeriod: 'event' },
  { date: 'T+5d', value: 3480, benchmarkValue: 24050, eventPeriod: 'post' },
  { date: 'T+10d', value: 3410, benchmarkValue: 23900, eventPeriod: 'post' },
  { date: 'T+15d', value: 3490, benchmarkValue: 24100, eventPeriod: 'post' },
  { date: 'T+30d', value: 3580, benchmarkValue: 24350, eventPeriod: 'post' },
];

const RELIANCE_HISTORICAL: HistoricalObservationPoint[] = [
  { date: 'T-15d', value: 2920, benchmarkValue: 24500, eventPeriod: 'pre' },
  { date: 'T-10d', value: 2950, benchmarkValue: 24650, eventPeriod: 'pre' },
  { date: 'T-5d', value: 2940, benchmarkValue: 24700, eventPeriod: 'pre' },
  { date: 'Event', value: 3080, benchmarkValue: 24200, eventPeriod: 'event' },
  { date: 'T+5d', value: 3140, benchmarkValue: 24050, eventPeriod: 'post' },
  { date: 'T+10d', value: 3190, benchmarkValue: 23900, eventPeriod: 'post' },
  { date: 'T+15d', value: 3160, benchmarkValue: 24100, eventPeriod: 'post' },
  { date: 'T+30d', value: 3120, benchmarkValue: 24350, eventPeriod: 'post' },
];

const NIFTY_HISTORICAL: HistoricalObservationPoint[] = [
  { date: 'T-15d', value: 24500, benchmarkValue: 24500, eventPeriod: 'pre' },
  { date: 'T-10d', value: 24650, benchmarkValue: 24650, eventPeriod: 'pre' },
  { date: 'T-5d', value: 24700, benchmarkValue: 24700, eventPeriod: 'pre' },
  { date: 'Event', value: 24200, benchmarkValue: 24200, eventPeriod: 'event' },
  { date: 'T+5d', value: 24050, benchmarkValue: 24050, eventPeriod: 'post' },
  { date: 'T+10d', value: 23900, benchmarkValue: 23900, eventPeriod: 'post' },
  { date: 'T+15d', value: 24100, benchmarkValue: 24100, eventPeriod: 'post' },
  { date: 'T+30d', value: 24350, benchmarkValue: 24350, eventPeriod: 'post' },
];

/**
 * Generate a complete 4-layer 3D graph based on the active scenario and parameters
 */
export function generateScenarioGraph(
  scenarioId: string,
  parameters: Record<string, number>
): { nodes: BlackSwanNode3D[]; edges: BlackSwanEdge3D[] } {
  const crudeShock = parameters.crude_oil_change_pct ?? 20;
  const inrShock = parameters.usd_inr_change_pct ?? 3.0;

  // Layer 1: Events (z: -180)
  // Layer 2: Economic Variables (z: -60)
  // Layer 3: Sectors (z: 60)
  // Layer 4: Indian Companies & Markets (z: 180)

  const nodes: BlackSwanNode3D[] = [
    // LAYER 1: EVENTS (Red / Coral)
    {
      id: 'bs_evt_trigger',
      label: 'Global Oil Shock',
      sublabel: `Brent +${crudeShock}%`,
      layer: 1,
      layerName: 'Events',
      category: 'event',
      position3D: { x: 0, y: 15, z: -180 },
      impactDirection: 'negative',
      shockMagnitude: `+${crudeShock}%`,
      description: 'Sudden curtailment of crude export volumes driving global spot benchmark volatility.',
      evidenceStatus: 'OBSERVED',
      confidenceScore: 0.94,
      evidenceCount: 4,
      limitations: 'Assumes sustained shock duration exceeding 30 trading sessions.'
    },

    // LAYER 2: ECONOMIC VARIABLES (Cyan / Blue)
    {
      id: 'bs_var_crude',
      label: 'Crude Oil Prices',
      sublabel: `$${(82 * (1 + crudeShock / 100)).toFixed(1)}/bbl`,
      layer: 2,
      layerName: 'Economic Variables',
      category: 'variable',
      position3D: { x: -80, y: 35, z: -60 },
      impactDirection: 'negative',
      shockMagnitude: `+${crudeShock}%`,
      description: 'Direct procurement cost benchmark for Indian refiners and downstream fuel buyers.',
      evidenceStatus: 'REPORTED',
      confidenceScore: 0.96,
      evidenceCount: 6,
      limitations: 'Hedging contracts provide temporary 60-day lag on physical realization.'
    },
    {
      id: 'bs_var_usdinr',
      label: 'USD / INR Rate',
      sublabel: `₹${(83.5 * (1 + inrShock / 100)).toFixed(2)}`,
      layer: 2,
      layerName: 'Economic Variables',
      category: 'variable',
      position3D: { x: 0, y: -25, z: -60 },
      impactDirection: 'negative',
      shockMagnitude: `+${inrShock}%`,
      description: 'Indian Rupee exchange rate depreciation under expanded oil import bill.',
      evidenceStatus: 'OBSERVED',
      confidenceScore: 0.91,
      evidenceCount: 5,
      limitations: 'RBI foreign exchange reserve market intervention may smooth extreme moves.'
    },
    {
      id: 'bs_var_inflation',
      label: 'Domestic CPI Inflation',
      sublabel: '+1.5 pp contribution',
      layer: 2,
      layerName: 'Economic Variables',
      category: 'variable',
      position3D: { x: 80, y: 35, z: -60 },
      impactDirection: 'negative',
      shockMagnitude: '+1.5 pp',
      description: 'Upstream freight and diesel costs propagating into wholesale and retail baskets.',
      evidenceStatus: 'INFERRED',
      confidenceScore: 0.88,
      evidenceCount: 3,
      limitations: 'Government fuel excise duty buffers could moderate retail fuel station prices.'
    },

    // LAYER 3: SECTORS (Muted Green)
    {
      id: 'bs_sec_aviation',
      label: 'Aviation Sector',
      sublabel: 'Fuel = 40% OPEX',
      layer: 3,
      layerName: 'Sectors',
      category: 'sector',
      position3D: { x: -110, y: 40, z: 60 },
      impactDirection: 'negative',
      shockMagnitude: '-3.8 pp EBITDA',
      description: 'Aviation turbine fuel (ATF) expense expansion directly squeezes passenger carrier operating margin.',
      evidenceStatus: 'OBSERVED',
      confidenceScore: 0.92,
      evidenceCount: 4,
      limitations: 'Passenger load factors and dynamic pricing algorithms provide partial yield defense.'
    },
    {
      id: 'bs_sec_oilgas',
      label: 'Oil & Gas Refining',
      sublabel: 'Crack spreads widen',
      layer: 3,
      layerName: 'Sectors',
      category: 'sector',
      position3D: { x: -35, y: -30, z: 60 },
      impactDirection: 'positive',
      shockMagnitude: 'GRM +$2.5/bbl',
      description: 'Upstream exploration and export-oriented refining complexes capture elevated gross refining margins (GRMs).',
      evidenceStatus: 'REPORTED',
      confidenceScore: 0.89,
      evidenceCount: 3,
      limitations: 'Domestic retail fuel marketing margins may experience temporary subsidy absorption.'
    },
    {
      id: 'bs_sec_banking',
      label: 'Banking & NBFCs',
      sublabel: 'Cost of funds ↑',
      layer: 3,
      layerName: 'Sectors',
      category: 'sector',
      position3D: { x: 45, y: -30, z: 60 },
      impactDirection: 'mixed',
      shockMagnitude: '+35 bps yield',
      description: 'Higher inflation expectations delay rate cuts, maintaining elevated loan yields alongside higher deposit costs.',
      evidenceStatus: 'INFERRED',
      confidenceScore: 0.84,
      evidenceCount: 2,
      limitations: 'Credit quality of retail and MSME segments may feel debt service stress if prolonged.'
    },
    {
      id: 'bs_sec_consumer',
      label: 'Paints & Consumer Chem',
      sublabel: 'Titanium dioxide / resins',
      layer: 3,
      layerName: 'Sectors',
      category: 'sector',
      position3D: { x: 110, y: 40, z: 60 },
      impactDirection: 'negative',
      shockMagnitude: '-1.9 pp gross margin',
      description: 'Crude derivatives represent ~50% of raw material input costs for industrial coatings and decorative paints.',
      evidenceStatus: 'OBSERVED',
      confidenceScore: 0.90,
      evidenceCount: 3,
      limitations: 'Seasonal monsoon stocking and promotional discounts alter short-term absorption.'
    },

    // LAYER 4: INDIAN COMPANIES AND MARKETS (Muted Purple)
    {
      id: 'bs_asset_indigo',
      label: 'InterGlobe Aviation (IndiGo)',
      sublabel: 'INDIGO · Equity',
      layer: 4,
      layerName: 'Indian Companies & Markets',
      category: 'company',
      position3D: { x: -125, y: 45, z: 180 },
      impactDirection: 'negative',
      shockMagnitude: 'Severe margin pressure',
      symbol: 'INDIGO',
      description: 'India’s largest domestic carrier with high operational sensitivity to domestic ATF price revisions.',
      evidenceStatus: 'REPORTED',
      confidenceScore: 0.91,
      evidenceCount: 4,
      historicalObservations: INDIGO_HISTORICAL,
      historicalWindowName: 'Around crude price shocks (30-day window)',
      limitations: 'Market share dominance allows tactical fare surcharges.'
    },
    {
      id: 'bs_asset_reliance',
      label: 'Reliance Industries (RIL)',
      sublabel: 'RELIANCE · Equity',
      layer: 4,
      layerName: 'Indian Companies & Markets',
      category: 'company',
      position3D: { x: -45, y: -35, z: 180 },
      impactDirection: 'positive',
      shockMagnitude: 'Export refinery upside',
      symbol: 'RELIANCE',
      description: 'Jamnagar mega-refinery exports diesel and gasoline into European and Asian markets at elevated crack spreads.',
      evidenceStatus: 'REPORTED',
      confidenceScore: 0.93,
      evidenceCount: 5,
      historicalObservations: RELIANCE_HISTORICAL,
      historicalWindowName: 'Around crude price shocks (30-day window)',
      limitations: 'Offset by consumer retail and telecommunications sensitivity to overall inflation.'
    },
    {
      id: 'bs_asset_nifty',
      label: 'NIFTY 50 Index',
      sublabel: 'NIFTY50 · Benchmark',
      layer: 4,
      layerName: 'Indian Companies & Markets',
      category: 'index',
      position3D: { x: 45, y: -35, z: 180 },
      impactDirection: 'negative',
      shockMagnitude: 'Multiple re-rating risk',
      symbol: 'NIFTY50',
      description: 'Broad market Indian equity benchmark heavily weighted toward financial services and consumer goods.',
      evidenceStatus: 'OBSERVED',
      confidenceScore: 0.89,
      evidenceCount: 6,
      historicalObservations: NIFTY_HISTORICAL,
      historicalWindowName: 'Around crude price shocks (30-day window)',
      limitations: 'High energy weight (RIL, ONGC) partially hedges headline index decline.'
    },
    {
      id: 'bs_asset_asianpaints',
      label: 'Asian Paints',
      sublabel: 'ASIANPAINT · Equity',
      layer: 4,
      layerName: 'Indian Companies & Markets',
      category: 'company',
      position3D: { x: 125, y: 45, z: 180 },
      impactDirection: 'negative',
      shockMagnitude: 'Raw material inflation',
      symbol: 'ASIANPAINT',
      description: 'Leading decorative coatings enterprise dependent on petrochemical monomer and phthalic anhydride inputs.',
      evidenceStatus: 'OBSERVED',
      confidenceScore: 0.90,
      evidenceCount: 3,
      limitations: 'Premium brand pricing power allows gradual price pass-through over 2-3 quarters.'
    }
  ];

  // Inter-layer Directed Relationships
  const edges: BlackSwanEdge3D[] = [
    // Layer 1 -> Layer 2
    {
      id: 'bse_evt_crude',
      source: 'bs_evt_trigger',
      target: 'bs_var_crude',
      relationLabel: 'elevates spot benchmark',
      relationType: 'direct_transmission',
      evidenceStatus: 'REPORTED',
      supportScore: 0.95,
      mechanismDescription: 'Physical crude supply constraints immediately bid up ICE Brent prompt contracts.'
    },
    {
      id: 'bse_evt_usdinr',
      source: 'bs_evt_trigger',
      target: 'bs_var_usdinr',
      relationLabel: 'widens CAD deficit',
      relationType: 'macroeconomic_drag',
      evidenceStatus: 'OBSERVED',
      supportScore: 0.92,
      mechanismDescription: 'Higher dollar-denominated oil import bills pressure domestic currency reserves.'
    },
    {
      id: 'bse_evt_inflation',
      source: 'bs_evt_trigger',
      target: 'bs_var_inflation',
      relationLabel: 'feeds transportation costs',
      relationType: 'price_pass_through',
      evidenceStatus: 'INFERRED',
      supportScore: 0.87,
      mechanismDescription: 'Fuel surcharges filter into wholesale transport logistics and farm gate distribution.'
    },

    // Layer 2 -> Layer 3
    {
      id: 'bse_crude_aviation',
      source: 'bs_var_crude',
      target: 'bs_sec_aviation',
      relationLabel: 'inflates jet fuel OPEX',
      relationType: 'direct_cost_shock',
      evidenceStatus: 'OBSERVED',
      supportScore: 0.94,
      mechanismDescription: 'Aviation turbine fuel accounts for 35% - 40% of domestic airline operating expenses.'
    },
    {
      id: 'bse_crude_oilgas',
      source: 'bs_var_crude',
      target: 'bs_sec_oilgas',
      relationLabel: 'expands refining spreads',
      relationType: 'margin_enhancement',
      evidenceStatus: 'REPORTED',
      supportScore: 0.90,
      mechanismDescription: 'Complex refiners capture higher middle-distillate crack spreads on global markets.'
    },
    {
      id: 'bse_usdinr_banking',
      source: 'bs_var_usdinr',
      target: 'bs_sec_banking',
      relationLabel: 'tightens money market liquidity',
      relationType: 'monetary_channel',
      evidenceStatus: 'INFERRED',
      supportScore: 0.85,
      mechanismDescription: 'RBI forex intervention absorbs systemic rupee liquidity, nudging call money rates higher.'
    },
    {
      id: 'bse_crude_consumer',
      source: 'bs_var_crude',
      target: 'bs_sec_consumer',
      relationLabel: 'increases chemical monomers',
      relationType: 'input_cost_inflation',
      evidenceStatus: 'OBSERVED',
      supportScore: 0.91,
      mechanismDescription: 'Solvents, resins, and packaging materials trace pricing directly to petrochemical feedstocks.'
    },

    // Layer 3 -> Layer 4
    {
      id: 'bse_aviation_indigo',
      source: 'bs_sec_aviation',
      target: 'bs_asset_indigo',
      relationLabel: 'compresses EBITDAR margin',
      relationType: 'sector_equity_pass_through',
      evidenceStatus: 'REPORTED',
      supportScore: 0.93,
      mechanismDescription: 'IndiGo absorbs domestic ATF price escalation with limited immediate ticket fare pass-through.'
    },
    {
      id: 'bse_oilgas_reliance',
      source: 'bs_sec_oilgas',
      target: 'bs_asset_reliance',
      relationLabel: 'boosts O2C operating profit',
      relationType: 'sector_equity_pass_through',
      evidenceStatus: 'REPORTED',
      supportScore: 0.92,
      mechanismDescription: 'RIL’s Oil-to-Chemicals (O2C) segment benefits from enhanced fuel export margins.'
    },
    {
      id: 'bse_banking_nifty',
      source: 'bs_sec_banking',
      target: 'bs_asset_nifty',
      relationLabel: 'drags 33% index weight',
      relationType: 'index_drag',
      evidenceStatus: 'OBSERVED',
      supportScore: 0.88,
      mechanismDescription: 'Financial services represent one-third of NIFTY weight; higher funding costs dampen earnings growth.'
    },
    {
      id: 'bse_consumer_asianpaints',
      source: 'bs_sec_consumer',
      target: 'bs_asset_asianpaints',
      relationLabel: 'pressures gross margins',
      relationType: 'sector_equity_pass_through',
      evidenceStatus: 'OBSERVED',
      supportScore: 0.89,
      mechanismDescription: 'Raw material inflation contracts operating margin before price hikes take effect.'
    }
  ];

  return { nodes, edges };
}

/**
 * Ranked propagation pathways for the active scenario
 */
export const DEMO_IMPACT_PATHWAYS: ImpactPathway[] = [
  {
    id: 'path_oil_indigo',
    name: 'Oil Shock → Crude → Aviation → IndiGo',
    fromEventId: 'bs_evt_trigger',
    toAssetId: 'bs_asset_indigo',
    nodeIds: ['bs_evt_trigger', 'bs_var_crude', 'bs_sec_aviation', 'bs_asset_indigo'],
    edgeIds: ['bse_evt_crude', 'bse_crude_aviation', 'bse_aviation_indigo'],
    transmissionSummary: 'Direct energy shock inflating jet fuel input costs, compressing operating EBITDAR of domestic air carriers.',
    supportScore: 0.93
  },
  {
    id: 'path_oil_reliance',
    name: 'Oil Shock → Crude → Refining → Reliance Industries',
    fromEventId: 'bs_evt_trigger',
    toAssetId: 'bs_asset_reliance',
    nodeIds: ['bs_evt_trigger', 'bs_var_crude', 'bs_sec_oilgas', 'bs_asset_reliance'],
    edgeIds: ['bse_evt_crude', 'bse_crude_oilgas', 'bse_oilgas_reliance'],
    transmissionSummary: 'Global distillate crack spread expansion driving gross refining margin uplift for export-oriented coastal refiners.',
    supportScore: 0.91
  },
  {
    id: 'path_oil_nifty',
    name: 'Oil Shock → USD/INR → Banking Liquidity → NIFTY 50',
    fromEventId: 'bs_evt_trigger',
    toAssetId: 'bs_asset_nifty',
    nodeIds: ['bs_evt_trigger', 'bs_var_usdinr', 'bs_sec_banking', 'bs_asset_nifty'],
    edgeIds: ['bse_evt_usdinr', 'bse_usdinr_banking', 'bse_banking_nifty'],
    transmissionSummary: 'Current account deficit pressure triggering central bank liquidity absorption, increasing banking funding overhead.',
    supportScore: 0.87
  },
  {
    id: 'path_oil_asianpaints',
    name: 'Oil Shock → Crude → Chemicals → Asian Paints',
    fromEventId: 'bs_evt_trigger',
    toAssetId: 'bs_asset_asianpaints',
    nodeIds: ['bs_evt_trigger', 'bs_var_crude', 'bs_sec_consumer', 'bs_asset_asianpaints'],
    edgeIds: ['bse_evt_crude', 'bse_crude_consumer', 'bse_consumer_asianpaints'],
    transmissionSummary: 'Monomer and solvent price increases pressuring gross margins of decorative paints and coatings.',
    supportScore: 0.89
  }
];

/**
 * Conceptual simulation timeline stages
 */
export const DEMO_TIMELINE_STAGES: SimulationTimelineStage[] = [
  {
    id: 'stage_1_trigger',
    stepNumber: 1,
    title: 'Event Shock Initiated',
    shortLabel: 'Event Shock',
    description: 'Hypothetical geopolitical supply cut or chokepoint restriction is instituted.',
    layerHighlight: 1,
    involvedNodeIds: ['bs_evt_trigger']
  },
  {
    id: 'stage_2_transmission',
    stepNumber: 2,
    title: 'Economic Variables Transmit',
    shortLabel: 'Variables',
    description: 'Crude benchmark, currency exchange rate, and headline inflation absorb immediate shock.',
    layerHighlight: 2,
    involvedNodeIds: ['bs_var_crude', 'bs_var_usdinr', 'bs_var_inflation']
  },
  {
    id: 'stage_3_sectors',
    stepNumber: 3,
    title: 'Sector Exposure Manifests',
    shortLabel: 'Sectors',
    description: 'Aviation, oil refining, banking, and consumer coatings experience divergent margin pressure.',
    layerHighlight: 3,
    involvedNodeIds: ['bs_sec_aviation', 'bs_sec_oilgas', 'bs_sec_banking', 'bs_sec_consumer']
  },
  {
    id: 'stage_4_assets',
    stepNumber: 4,
    title: 'Indian Markets & Assets Impact',
    shortLabel: 'Assets & Indices',
    description: 'IndiGo, Reliance, Asian Paints, and NIFTY 50 reflect valuation and margin re-ratings.',
    layerHighlight: 4,
    involvedNodeIds: ['bs_asset_indigo', 'bs_asset_reliance', 'bs_asset_nifty', 'bs_asset_asianpaints']
  },
  {
    id: 'stage_5_historical',
    stepNumber: 5,
    title: 'Historical Context Grounding',
    shortLabel: 'Historical Context',
    description: 'Empirical market observations from previous supply shocks ground the modeled transmission.',
    layerHighlight: 4,
    involvedNodeIds: ['bs_asset_indigo', 'bs_asset_reliance', 'bs_asset_nifty']
  }
];

/**
 * Standard default simulation response
 */
export function getInitialSimulationResponse(
  scenarioId: string = 'global_oil_supply_shock',
  parameters: Record<string, number> = {
    crude_oil_change_pct: 20,
    usd_inr_change_pct: 3.0,
    global_inflation_change_pct: 1.5
  }
): SimulationResponse {
  const scenario = BLACK_SWAN_PRESETS.find(s => s.id === scenarioId) || BLACK_SWAN_PRESETS[0];
  const { nodes, edges } = generateScenarioGraph(scenarioId, parameters);

  return {
    simulation_id: `sim_${Date.now()}`,
    scenario,
    submitted_parameters: parameters,
    graph: { nodes, edges },
    impact_paths: DEMO_IMPACT_PATHWAYS,
    timeline_stages: DEMO_TIMELINE_STAGES,
    predictions: [], // ML model has NOT been built yet - explicitly empty
    model_status: 'not_available',
    model_message: 'Quantitative market predictions are not available yet. Graph-based impact analysis is available.',
    warnings: [
      'Hypothetical scenario parameters reflect user-configured stress assumptions.',
      'Numerical returns require a trained ML model; only causal graph propagation is currently active.'
    ],
    is_demo: true,
    created_at: new Date().toISOString()
  };
}
